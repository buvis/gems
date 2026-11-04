from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from braid.domain.model import (
    AGENT_NAME,
    BraidError,
    Mode,
    Result,
    Settings,
    _expand_user,
    _present,
    _resolved,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class KiroRegistration:
    root: Path
    agents: tuple[str, ...] = ()


@dataclass(frozen=True)
class KiroAgentEdit:
    path: Path
    before: bytes
    after: bytes | None


def select_kiro(settings: Settings, previous: KiroRegistration | None) -> KiroRegistration | None:
    if not settings.project_kiro:
        return previous
    requested = settings.enable_kiro or settings.kiro_root is not None or bool(settings.kiro_agents)
    if previous is None and not requested:
        if settings.forget_kiro_agents:
            raise BraidError("Kiro has no registered custom agents to forget")
        return None
    root = _resolved(settings.kiro_root or (previous.root if previous else Path.home() / ".kiro"))
    if previous is not None and root != _resolved(previous.root):
        raise BraidError(f"Kiro is already enrolled at {previous.root}; moving its root is unsupported")
    agents = set(previous.agents if previous else ())
    for name in (*settings.kiro_agents, *settings.forget_kiro_agents):
        if not AGENT_NAME.fullmatch(name):
            raise BraidError(f"invalid Kiro agent name: {name!r}; use a filename without .json")
    if set(settings.kiro_agents) & set(settings.forget_kiro_agents):
        raise BraidError("cannot enroll and forget the same Kiro agent")
    missing = set(settings.forget_kiro_agents) - agents
    if missing:
        raise BraidError(f"Kiro agents are not registered: {', '.join(sorted(missing))}")
    agents.update(settings.kiro_agents)
    agents.difference_update(settings.forget_kiro_agents)
    return KiroRegistration(root=root, agents=tuple(sorted(agents)))


def prepare_kiro_agents(registration: KiroRegistration, agents_root: Path) -> tuple[KiroAgentEdit, ...]:
    """Read every selected config before any links or configs change."""
    skill_glob = registration.root / "skills" / "*" / "SKILL.md"
    try:
        resource = "skill://~/" + skill_glob.relative_to(Path.home()).as_posix()
    except ValueError:
        resource = "skill://" + skill_glob.as_posix()
    equivalent = {_resolved(skill_glob), _resolved(agents_root / "skills" / "*" / "SKILL.md")}

    def covers_personal_skills(item: object) -> bool:
        if not isinstance(item, str) or not item.startswith("skill://"):
            return False
        path = _expand_user(item[len("skill://") :])
        # Relative resources follow the chat's project, not this Braid invocation.
        return path.is_absolute() and _resolved(path) in equivalent

    edits: list[KiroAgentEdit] = []
    for name in registration.agents:
        path = registration.root / "agents" / f"{name}.json"
        if path.is_symlink():
            raise BraidError(f"refusing to rewrite symlinked Kiro agent config: {path}")
        try:
            before = path.read_bytes()
            config = json.loads(before)
        except (OSError, ValueError) as error:
            raise BraidError(f"cannot read Kiro agent {path}: {error}") from error
        if not isinstance(config, dict) or not isinstance(config.get("resources", []), list):
            raise BraidError(f"Kiro agent must be a JSON object with a resources array: {path}")
        resources = config.get("resources", [])
        covered = any(covers_personal_skills(item) for item in resources)
        after = None
        if not covered:
            config["resources"] = [*resources, resource]
            after = (json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        edits.append(KiroAgentEdit(path=path, before=before, after=after))
    return tuple(edits)


def sync_kiro_agent(
    edit: KiroAgentEdit,
    backup_root: Path,
    mode: Mode,
    result: Result,
    emit: Callable[[str], None],
) -> None:
    if edit.after is None:
        result.current += 1
        return
    result.drift += 1
    if mode is not Mode.SYNC:
        verb = "MISMATCH RESOURCE" if mode is Mode.CHECK else "WOULD CONFIGURE"
        emit(f"{verb} {edit.path}")
        return
    temporary: Path | None = None
    backup = backup_root / "agents" / edit.path.name
    try:
        if edit.path.is_symlink() or edit.path.read_bytes() != edit.before:
            raise BraidError(f"Kiro agent changed during composition; retry: {edit.path}")
        backup.parent.mkdir(parents=True, exist_ok=True)
        if _present(backup):
            raise BraidError(f"refusing to overwrite Kiro agent backup: {backup}")
        shutil.copy2(edit.path, backup)
        result.backed_up += 1
        emit(f"BACKUP {edit.path} -> {backup}")
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=edit.path.parent, prefix=f".{edit.path.name}.braid-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(edit.after)
        shutil.copymode(edit.path, temporary)
        if edit.path.is_symlink() or edit.path.read_bytes() != edit.before:
            raise BraidError(f"Kiro agent changed during composition; retry: {edit.path}")
        os.replace(temporary, edit.path)
        temporary = None
    except OSError as error:
        raise BraidError(f"cannot configure Kiro agent {edit.path}: {error}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    result.configured += 1
    emit(f"CONFIGURE {edit.path}")
