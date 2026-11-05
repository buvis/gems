from __future__ import annotations

import importlib
import json
import os
import shutil
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from buvis.pybase.filesystem.atomic_write import atomic_write_text

from braid.domain.kiro import (
    KiroAgentEdit,
    KiroRegistration,
    prepare_kiro_agents,
    select_kiro,
    sync_kiro_agent,
)
from braid.domain.model import (
    AGENT_NAME,
    SKILL_NAME,
    STATE_VERSION,
    BraidError,
    Mode,
    Result,
    Settings,
    _absolute,
    _expand_user,
    _present,
    _resolved,
    is_legacy_skills_source,
)
from braid.domain.rules import RuleState, discover_rules, sync_rules

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

__all__ = [
    "STATE_VERSION",
    "BraidError",
    "ComposeRequest",
    "KiroAgentEdit",
    "KiroRegistration",
    "Mode",
    "Result",
    "Settings",
    "State",
    "create_directory_link",
    "create_file_link",
    "discover_inventory",
    "prepare_kiro_agents",
    "read_configured_sources",
    "read_ignored",
    "resolve_settings",
    "run",
    "select_kiro",
    "sync_kiro_agent",
]


@dataclass(frozen=True)
class State:
    union: dict[str, str]
    hosts: dict[str, dict[str, str]]
    kiro: KiroRegistration | None = None
    rules: RuleState | None = None

    @classmethod
    def empty(cls) -> State:
        return cls(union={}, hosts={})

    def as_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": STATE_VERSION,
            "union": self.union,
            "hosts": self.hosts,
        }
        if self.kiro is not None:
            payload["kiro"] = {"root": str(self.kiro.root), "agents": list(self.kiro.agents)}
        if self.rules is not None:
            payload["rules"] = self.rules.as_json()
        return payload


@dataclass(frozen=True)
class ComposeRequest:
    agents_root: Path
    claude_root: Path
    config_root: Path
    sources: tuple[Path, ...] = ()
    policies: tuple[Path, ...] = ()
    mode: Mode = Mode.SYNC
    project_claude: bool = True
    enable_kiro: bool = False
    kiro_root: Path | None = None
    kiro_agents: tuple[str, ...] = ()
    forget_kiro_agents: tuple[str, ...] = ()
    project_kiro: bool = True


@dataclass(frozen=True)
class _Pass:
    """What every link pass of one run shares."""

    mode: Mode
    platform: str
    result: Result
    emit: Callable[[str], None]


@dataclass(frozen=True)
class _Projection:
    """One destination root to bring in line with ``desired``."""

    desired: dict[str, Path]
    previous: dict[str, str]
    destination_root: Path
    backup_root: Path
    backup_category: str
    preserve_real_sources: bool
    entry_suffix: str = ""
    file_links: bool = False


@dataclass(frozen=True)
class _OrphanScope:
    """What the orphan scan compares the disk against."""

    inventory: dict[str, Path]
    eligible: dict[str, Path]
    previous: State
    kiro: KiroRegistration | None


def _discard(_line: str) -> None:
    """Default emit: the domain never writes to a stream itself."""


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise BraidError(f"cannot read {path}: {error}") from error


def _skill_name(skill_directory: Path) -> str:
    skill_file = skill_directory / "SKILL.md"
    lines = _read_lines(skill_file)

    if not lines or lines[0] != "---":
        raise BraidError(f"invalid skill frontmatter: {skill_file}")
    for line in lines[1:]:
        if line == "---":
            break
        match = SKILL_NAME.fullmatch(line)
        if match:
            name = match.group(1)
            if name != skill_directory.name:
                raise BraidError(f"skill name {name!r} does not match directory {skill_directory.name!r}")
            return name
    raise BraidError(f"missing valid name in {skill_file}")


def _skills_directory(source: Path) -> Path | None:
    source = _resolved(source)
    nested = source / "skills"
    if nested.is_dir():
        return nested
    if is_legacy_skills_source(source):
        return source
    if (source / "rules").is_dir() or (source / "hosts").is_dir():
        return None
    raise BraidError(f"source has no skills, rules or hosts directory: {source}")


def discover_inventory(sources: Iterable[Path]) -> dict[str, Path]:
    inventory: dict[str, Path] = {}
    owners: dict[str, Path] = {}
    seen_sources: set[Path] = set()

    for configured_source in sources:
        source = _skills_directory(configured_source)
        if source is None or source in seen_sources:
            continue
        seen_sources.add(source)
        for candidate in sorted(source.iterdir(), key=lambda path: path.name):
            if candidate.is_symlink():
                continue
            if candidate.name.startswith(".") or not candidate.is_dir():
                continue
            if not (candidate / "SKILL.md").is_file():
                continue
            name = _skill_name(candidate)
            resolved_candidate = _resolved(candidate)
            if name in inventory and inventory[name] != resolved_candidate:
                raise BraidError(f"duplicate skill name {name!r}: {owners[name]} and {configured_source}")
            inventory[name] = resolved_candidate
            owners[name] = _resolved(configured_source)
    return inventory


def read_configured_sources(config_root: Path) -> tuple[Path, ...]:
    sources_directory = _expand_user(config_root) / "sources.d"
    if not sources_directory.is_dir():
        return ()

    sources: list[Path] = []
    for source_file in sorted(sources_directory.iterdir(), key=lambda path: path.name):
        if not source_file.is_file() or source_file.name.startswith("."):
            continue
        for raw_line in _read_lines(source_file):
            value = raw_line.split("#", 1)[0].strip()
            if not value:
                continue
            expanded = _expand_user(value)
            if not expanded.is_absolute():
                expanded = source_file.parent / expanded
            sources.append(expanded.resolve(strict=False))
    return tuple(sources)


def read_ignored(policy_files: Iterable[Path]) -> set[str]:
    ignored: set[str] = set()
    for policy_file in policy_files:
        if not policy_file.is_file():
            continue
        for raw_line in _read_lines(policy_file):
            value = raw_line.split("#", 1)[0].strip()
            if value:
                ignored.add(value)
    return ignored


def _create_junction(target: str, destination: str) -> None:
    # Direct Win32 call, never cmd.exe: path metacharacters (&, |, ^) stay literal.
    # _winapi is CPython-private and Windows-only (no public junction API exists),
    # so it is imported at call time.
    importlib.import_module("_winapi").CreateJunction(target, destination)


def create_directory_link(
    destination: Path,
    target: Path,
    *,
    platform: str = os.name,
    junction: Callable[[str, str], None] = _create_junction,
) -> str:
    try:
        os.symlink(str(target), str(destination), target_is_directory=True)
        return "symlink"
    except OSError as error:
        if platform != "nt" or getattr(error, "winerror", None) not in {5, 1314}:
            raise BraidError(f"cannot link {destination} -> {target}: {error}") from error

    try:
        junction(str(target), str(destination))
    except OSError as error:
        raise BraidError(f"cannot create junction {destination} -> {target}: {error}") from error
    return "junction"


def create_file_link(
    destination: Path,
    target: Path,
    *,
    platform: str = os.name,
    hard_link: Callable[[str, str], None] = os.link,
) -> str:
    try:
        os.symlink(str(target), str(destination))
        return "symlink"
    except OSError as error:
        if platform != "nt" or getattr(error, "winerror", None) not in {5, 1314}:
            raise BraidError(f"cannot link {destination} -> {target}: {error}") from error

    try:
        hard_link(str(target), str(destination))
    except OSError as error:
        raise BraidError(f"cannot create hard link {destination} -> {target}: {error}") from error
    return "hardlink"


def _points_to(path: Path, target: Path, platform: str) -> bool:
    if path.is_symlink():
        raw_target = Path(os.readlink(path))
        if not raw_target.is_absolute():
            raw_target = path.parent / raw_target
        return _resolved(raw_target) == _resolved(target)
    if platform == "nt" and path.is_dir():
        return _resolved(path) == _resolved(target)
    if platform == "nt" and path.is_file():
        try:
            return os.path.samefile(path, target)
        except OSError:
            return False
    return False


def _load_state(path: Path) -> State:
    if not path.is_file():
        return State.empty()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BraidError(f"cannot read Braid state {path}: {error}") from error
    if not isinstance(payload, dict) or payload.get("version") != STATE_VERSION:
        raise BraidError(f"unsupported Braid state version in {path}")
    union = payload.get("union")
    hosts = payload.get("hosts")
    if not isinstance(union, dict) or not isinstance(hosts, dict):
        raise BraidError(f"invalid Braid state schema in {path}")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in union.items()):
        raise BraidError(f"invalid union state in {path}")
    normalized_hosts: dict[str, dict[str, str]] = {}
    for host, links in hosts.items():
        if not isinstance(host, str) or not isinstance(links, dict):
            raise BraidError(f"invalid host state in {path}")
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in links.items()):
            raise BraidError(f"invalid host link state in {path}")
        normalized_hosts[host] = dict(links)
    kiro = None
    if "kiro" in payload:
        registration = payload["kiro"]
        if (
            not isinstance(registration, dict)
            or not isinstance(registration.get("root"), str)
            or not Path(registration["root"]).is_absolute()
            or not isinstance(registration.get("agents"), list)
            or not all(isinstance(name, str) and AGENT_NAME.fullmatch(name) for name in registration["agents"])
        ):
            raise BraidError(f"invalid Kiro registration in {path}")
        kiro = KiroRegistration(root=Path(registration["root"]), agents=tuple(sorted(set(registration["agents"]))))
    rules = RuleState.from_json(payload["rules"], path) if "rules" in payload else None
    return State(union=dict(union), hosts=normalized_hosts, kiro=kiro, rules=rules)


def _write_state(path: Path, state: State) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(state.as_json(), indent=2, sort_keys=True) + "\n")
    except OSError as error:
        raise BraidError(f"cannot write Braid state {path}: {error}") from error


def _backup(
    path: Path,
    root: Path,
    category: str,
    result: Result,
    emit: Callable[[str], None],
) -> None:
    backup = root / category / path.name
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(backup))
    result.backed_up += 1
    emit(f"BACKUP {path} -> {backup}")


def _remove_owned_link(path: Path, target: Path, platform: str) -> None:
    if path.is_symlink():
        path.unlink()
        return
    if platform == "nt" and path.is_dir() and _points_to(path, target, platform):
        os.rmdir(path)
        return
    if platform == "nt" and path.is_file() and _points_to(path, target, platform):
        path.unlink()
        return
    raise BraidError(f"refusing to remove changed or unowned path: {path}")


def _report_orphan_links(
    root: Path,
    owner_roots: Iterable[Path],
    recorded: set[str],
    result: Result,
    emit: Callable[[str], None],
) -> None:
    """Report links into an owner root that the manifest does not record; never touch them."""
    if not root.is_dir():
        return
    owners = {_resolved(owner) for owner in owner_roots}
    try:
        for path in sorted(root.iterdir()):
            if path.name in recorded or not path.is_symlink():
                continue
            target = Path(os.readlink(path))
            if not target.is_absolute():
                target = path.parent / target
            # Judge where the link itself points: resolving its last hop would follow a union
            # link into the source tree and hide the projection that still names it.
            if owners.intersection((_resolved(target.parent) / target.name).parents):
                result.drift += 1
                emit(f"MISMATCH ORPHAN {path}")
    except OSError as error:
        raise BraidError(f"cannot scan {root} for orphan links: {error}") from error


def _report_orphans(
    settings: Settings,
    union_root: Path,
    scope: _OrphanScope,
    result: Result,
    emit: Callable[[str], None],
) -> None:
    inventory, eligible, previous, kiro = scope.inventory, scope.eligible, scope.previous, scope.kiro
    if settings.mode is Mode.SYNC:
        return  # the manifest is not the only record of what Braid owns, but sync trusts it
    hosts = previous.hosts
    source_roots = [root for source in settings.sources if (root := _skills_directory(source)) is not None]
    scans = [(union_root, source_roots, {*inventory, *previous.union})]
    if settings.project_claude:
        claude_skills = settings.claude_root / "skills"
        scans.append((claude_skills, [union_root], {*eligible, *hosts.get("claude", {})}))
    if kiro is not None and settings.project_kiro:
        scans.append((kiro.root / "skills", [union_root], {*inventory, *hosts.get("kiro", {})}))
    for root, owner_roots, recorded in scans:
        _report_orphan_links(root, owner_roots, recorded, result, emit)


def _sync_links(projection: _Projection, run_pass: _Pass) -> dict[str, str]:
    desired = projection.desired
    destination_root, backup_root = projection.destination_root, projection.backup_root
    backup_category = projection.backup_category
    preserve_real_sources = projection.preserve_real_sources
    mode, platform, result, emit = run_pass.mode, run_pass.platform, run_pass.result, run_pass.emit
    managed: dict[str, str] = {}

    for name, target in sorted(desired.items()):
        destination = destination_root / f"{name}{projection.entry_suffix}"
        if preserve_real_sources and _absolute(destination) == _absolute(target):
            result.current += 1
            continue
        if _points_to(destination, target, platform):
            result.current += 1
            managed[name] = str(target)
            continue

        result.drift += 1
        verb = "MISMATCH" if mode is Mode.CHECK else "WOULD LINK"
        if mode is not Mode.SYNC:
            emit(f"{verb} {destination} -> {target}")
            continue

        destination_root.mkdir(parents=True, exist_ok=True)
        if _present(destination):
            _backup(destination, backup_root, backup_category, result, emit)
        link = create_file_link if projection.file_links else create_directory_link
        backend = link(destination, target, platform=platform)
        result.linked += 1
        managed[name] = str(target)
        emit(f"LINK[{backend}] {destination} -> {target}")

    _remove_stale_links(projection, run_pass)
    return managed


def _remove_stale_links(projection: _Projection, run_pass: _Pass) -> None:
    desired, previous, destination_root = projection.desired, projection.previous, projection.destination_root
    mode, platform, result, emit = run_pass.mode, run_pass.platform, run_pass.result, run_pass.emit
    for name, raw_target in sorted(previous.items()):
        if name in desired:
            continue
        destination = destination_root / f"{name}{projection.entry_suffix}"
        if not _present(destination):
            continue
        old_target = Path(raw_target)
        if not _points_to(destination, old_target, platform):
            if mode is Mode.SYNC and projection.file_links:
                result.drift += 1
                _backup(destination, projection.backup_root, projection.backup_category, result, emit)
                continue
            if mode is Mode.SYNC:
                raise BraidError(f"refusing to clean changed managed path: {destination}")
            result.drift += 1
            emit(f"MISMATCH CHANGED {destination}")
            continue
        result.drift += 1
        verb = "MISMATCH STALE" if mode is Mode.CHECK else "WOULD REMOVE"
        if mode is not Mode.SYNC:
            emit(f"{verb} {destination}")
            continue
        _remove_owned_link(destination, old_target, platform)
        result.removed += 1
        emit(f"REMOVE {destination}")


def _project_host(
    desired: dict[str, Path], previous: dict[str, str], host_root: Path, suffix: str, run_pass: _Pass
) -> dict[str, str]:
    return _sync_links(
        _Projection(
            desired=desired,
            previous=previous,
            destination_root=host_root / "skills",
            backup_root=host_root / "skills-backup" / suffix,
            backup_category="project",
            preserve_real_sources=False,
        ),
        run_pass,
    )


def _backup_suffix() -> str:
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{os.getpid()}"


def _settle_state(mode: Mode, state_path: Path, previous_state: State, next_state: State, run_pass: _Pass) -> None:
    """Count a state-only change as drift; write the state file under SYNC."""
    if next_state != previous_state and run_pass.result.drift == 0:
        run_pass.result.drift += 1
        if mode is not Mode.SYNC:
            run_pass.emit(f"MISMATCH STATE {state_path}")
    if mode is Mode.SYNC:
        _write_state(state_path, next_state)


def run(settings: Settings, emit: Callable[[str], None] = _discard) -> Result:
    inventory = discover_inventory(settings.sources)
    rule_inventory = discover_rules(settings.sources)  # before any write: a bad rule exits with nothing written
    ignored = read_ignored(settings.policy_files)
    state_path = settings.agents_root / ".braid-state.json"
    previous_state = _load_state(state_path)
    kiro = select_kiro(settings, previous_state.kiro)
    kiro_edits = prepare_kiro_agents(kiro, settings.agents_root) if kiro is not None and settings.project_kiro else ()
    suffix = _backup_suffix()
    result = Result()
    run_pass = _Pass(mode=settings.mode, platform=settings.platform, result=result, emit=emit)
    union_root = settings.agents_root / "skills"

    union = _sync_links(
        _Projection(
            desired=inventory,
            previous=previous_state.union,
            destination_root=union_root,
            backup_root=settings.agents_root / "backups" / suffix,
            backup_category="compose",
            preserve_real_sources=True,
        ),
        run_pass,
    )

    hosts = dict(previous_state.hosts)
    eligible = {name: union_root / name for name in inventory if name not in ignored}
    if settings.project_claude:
        result.ignored += len(inventory) - len(eligible)
        previous = previous_state.hosts.get("claude", {})
        hosts["claude"] = _project_host(eligible, previous, settings.claude_root, suffix, run_pass)

    if kiro is not None and settings.project_kiro:
        # Claude's plugin-duplicate exclusions do not apply to Kiro.
        everything = {name: union_root / name for name in inventory}
        hosts["kiro"] = _project_host(everything, previous_state.hosts.get("kiro", {}), kiro.root, suffix, run_pass)
        for edit in kiro_edits:
            sync_kiro_agent(edit, kiro.root / "agent-backup" / suffix, settings.mode, result, emit)

    rule_settings = replace(settings, kiro_root=kiro.root if kiro is not None and settings.project_kiro else None)
    rules_state = sync_rules(rule_settings, rule_inventory, ignored, previous_state.rules, result, emit=emit)

    _report_orphans(settings, union_root, _OrphanScope(inventory, eligible, previous_state, kiro), result, emit)

    next_state = State(union=union, hosts=hosts, kiro=kiro, rules=rules_state)
    _settle_state(settings.mode, state_path, previous_state, next_state, run_pass)
    return result


def _deduplicate(paths: Iterable[Path]) -> tuple[Path, ...]:
    result: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = _resolved(path)
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return tuple(result)


def resolve_settings(request: ComposeRequest) -> Settings:
    agents_root = _expand_user(request.agents_root)
    claude_root = _expand_user(request.claude_root)
    config_root = _expand_user(request.config_root)
    sources = _deduplicate([*read_configured_sources(config_root), *request.sources])
    if not sources:
        raise BraidError(f"no skill sources configured; add a path under {config_root / 'sources.d'} or pass --source")
    candidates = [agents_root / ".braidignore", config_root / ".braidignore"]
    for source in sources:
        policy_root = source.parent if is_legacy_skills_source(source) else source
        candidates.append(policy_root / ".braidignore")
    candidates.extend(request.policies)
    policy_files = tuple(path for path in _deduplicate(candidates) if path.is_file())
    return Settings(
        sources=sources,
        agents_root=_resolved(agents_root),
        claude_root=_resolved(claude_root),
        mode=request.mode,
        policy_files=policy_files,
        project_claude=request.project_claude,
        enable_kiro=request.enable_kiro,
        kiro_root=request.kiro_root,
        kiro_agents=request.kiro_agents,
        forget_kiro_agents=request.forget_kiro_agents,
        project_kiro=request.project_kiro,
    )
