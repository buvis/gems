# Design: 00116-braid-rules-kind-v1

## Architecture fit

braid lives in `src/tools/braid/` (ported in PRD 00115). Layers:

- `domain/model.py`: `Settings`, `Result`, `Mode`, `BraidError`, path helpers. No I/O beyond `os.path` checks.
- `domain/engine.py`: skill discovery, the link pass machinery (`_Pass`, `_Projection`, `_sync_links`, `_remove_stale_links`, `_points_to`, `_backup`, `_remove_owned_link`, `_report_orphan_links`, `create_directory_link`), the state file, and `run()`.
- `domain/kiro.py`: Kiro enrollment and agent config edits.
- `commands/compose/compose.py`: `CommandCompose` returns `CommandResult` and builds the summary line.
- `cli.py`: Click entry point, renders the command result through `console`.

Rules are a second kind beside skills. They land in a new domain module `domain/rules.py` that reuses the engine's link pass machinery unchanged in spirit: the union view, directory-host projections, backup, stale removal and orphan reporting are the same code paths with two new `_Projection` knobs (`entry_suffix`, `file_links`). The domain stays free of Click and console (AGENTS.md "library stays interface-agnostic" applies by analogy to the tool's domain layer); every line still goes through `emit`, and `CommandCompose` still returns `CommandResult`.

Import direction: `engine.py` imports `rules.py` at module top. `rules.py` imports only `model.py` at module top and imports the engine link helpers inside `sync_rules` (function-local), because the engine imports `rules` at top level and a top-level import back would be a cycle. Moving the link helpers to a new module was rejected (see Alternatives): `tests/tools/braid/test_cli.py:384` monkeypatches `braid.domain.engine.create_directory_link` and `test_check.py:142` calls `engine._report_orphan_links`, so the helpers must stay in `engine.py`.

## Module placement

New files:

- `src/tools/braid/domain/rules.py` - rule discovery, render, projection, generation, instruction links, `RuleInventory`, `RuleState`, constants.
- `tests/tools/braid/test_rules.py` - engine-level rule tests.
- `tests/tools/braid/test_rules_cli.py` - CLI summary and exit codes with rules.

Edited files:

- `src/tools/braid/domain/model.py` - `Result.generated`, `Result.unmanaged`; new `is_legacy_skills_source(source)`.
- `src/tools/braid/domain/engine.py` - `_skills_directory` relaxed; `discover_inventory` and `_report_orphans` skip rule-only sources; `_Projection.entry_suffix`/`file_links`; `create_file_link`; `_points_to` and `_remove_owned_link` gain the Windows hard-link branch; `_backup_suffix()`; `State.rules`; `_load_state` reads `rules`; `run()` calls `discover_rules` and `sync_rules`; `resolve_settings` policy root fixed for rule-only sources.
- `src/tools/braid/commands/compose/compose.py` - summary line and `metadata["unmanaged"]`.
- `src/tools/braid/cli.py` - command help and `--no-claude` help mention rules (the summary line itself is built in `compose.py`, which `cli.py` prints verbatim).
- `tests/tools/braid/helpers.py` - `make_rule`, `make_host_rule` beside the existing `make_skill`. The PRD tree names `conftest.py`, but since PRD 00115 `conftest.py` holds only the autouse isolation fixture and every builder (`make_skill`, `settings`, `enroll`) lives in `helpers.py`, which tests import as `tests.tools.braid.helpers`; plain functions in `conftest.py` are not importable that way. Same helpers, existing home.
- `tests/tools/braid/test_cli.py` - the six literal summary-line assertions (lines 55, 70, 142, 172, 204, 277) gain ` 0 generated,` after `linked,` and ` 0 unmanaged,` after `configured,`; nothing else changes. The PRD mandates the new summary fields, so these literals must move.
- `pyproject.toml` - per-file ignore `"src/tools/braid/domain/rules.py" = ["PLR0913"]` with a comment that `sync_rules`'s six-parameter signature is the PRD 00116 verbatim contract (same precedent as `src/tools/sysup/runlog.py`).
- `docs/source/tools/braid.rst` - rules section; example summary line updated.
- `README.md` - braid section and tool-table row mention rules (AGENTS.md: every CLI change updates README).
- `CHANGELOG.md` - `[Unreleased]` Added entry, text verbatim from the PRD.

## Interfaces & contracts

### `src/tools/braid/domain/model.py`

```python
@dataclass
class Result:
    linked: int = 0
    current: int = 0
    ignored: int = 0
    removed: int = 0
    backed_up: int = 0
    drift: int = 0
    configured: int = 0
    generated: int = 0
    unmanaged: int = 0


def is_legacy_skills_source(source: Path) -> bool:
    """A configured path that is itself a skills directory (PRD 00115 form)."""
    return not (source / "skills").is_dir() and source.is_dir() and source.name == "skills"
```

`source` is passed already resolved by callers.

### `src/tools/braid/domain/engine.py`

```python
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
```

- `discover_inventory(sources)`: a `None` from `_skills_directory` contributes no skills (skip the source); everything else unchanged.
- `_report_orphans`: `source_roots` keeps only the non-`None` results of `_skills_directory`.
- `resolve_settings`: `policy_root = source.parent if is_legacy_skills_source(source) else source` (was `source if (source / "skills").is_dir() else source.parent`; identical for every PRD 00115 source, correct for rule-only sources).

```python
@dataclass(frozen=True)
class _Projection:
    desired: dict[str, Path]
    previous: dict[str, str]
    destination_root: Path
    backup_root: Path
    backup_category: str
    preserve_real_sources: bool
    entry_suffix: str = ""      # destination = destination_root / f"{name}{entry_suffix}"
    file_links: bool = False    # True: create_file_link, False: create_directory_link
```

`_remove_stale_links` gains one branch for file-link projections: when `projection.file_links` and a stale destination no longer `_points_to` its recorded target, SYNC moves it aside with `_backup(destination, projection.backup_root, projection.backup_category, result, emit)` (counts `result.drift += 1`, emits the existing `BACKUP` line) instead of raising "refusing to clean changed managed path"; CHECK/DRY_RUN keep the existing `MISMATCH CHANGED {destination}`. Reason: on Windows a recorded hard link cannot be proven ours once its source `RULE.md` is deleted or rewritten (`samefile` against a dangling union link fails), and a backup never destroys a user file. Directory projections (skills) keep the raise.

`_sync_links` and `_remove_stale_links` compute every destination as `destination_root / f"{name}{projection.entry_suffix}"`; `_sync_links` calls `create_file_link(destination, target, platform=platform)` when `projection.file_links` else `create_directory_link(destination, target, platform=platform)` (still looked up as a module global so the `test_cli.py:384` monkeypatch keeps working). Managed/state keys stay the bare `name`.

```python
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
```

Added to `__all__`. Report line on success: `LINK[symlink] ...` or `LINK[hardlink] ...` (same `LINK[{backend}] {destination} -> {target}` format as directories).

`_points_to(path, target, platform)` gains, after the existing `platform == "nt" and path.is_dir()` branch:

```python
    if platform == "nt" and path.is_file():
        try:
            return os.path.samefile(path, target)
        except OSError:
            return False
```

`_remove_owned_link(path, target, platform)` gains, before the final raise:

```python
    if platform == "nt" and path.is_file() and _points_to(path, target, platform):
        path.unlink()
        return
```

Neither branch can match a skill link (skill targets are directories).

```python
def _backup_suffix() -> str:
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{os.getpid()}"
```

`run()` uses it in place of its inline suffix; `sync_rules` calls it once per run for rule backups (a separate timestamp directory under the same backup roots; both are unique per run).

```python
@dataclass(frozen=True)
class State:
    union: dict[str, str]
    hosts: dict[str, dict[str, str]]
    kiro: KiroRegistration | None = None
    rules: RuleState | None = None
```

- `State.as_json()`: unchanged keys, plus `payload["rules"] = self.rules.as_json()` only when `self.rules is not None`.
- `_load_state`: when `"rules" in payload`, `rules = RuleState.from_json(payload["rules"], path)`; absent → `None`. `version` stays `STATE_VERSION == 1`.
- `run()` order:
  1. `inventory = discover_inventory(settings.sources)`
  2. `rule_inventory = discover_rules(settings.sources)` (before any write, so duplicate/invalid/unreadable rules exit 2 with nothing written)
  3. existing ignored/state/kiro/skill union/Claude/Kiro passes, unchanged
  4. `rule_settings = replace(settings, kiro_root=kiro.root if kiro is not None and settings.project_kiro else None)`; `rules_state = sync_rules(rule_settings, rule_inventory, ignored, previous_state.rules, result, emit)`
  5. `_report_orphans(...)` (skills), unchanged
  6. `next_state = State(union=union, hosts=hosts, kiro=kiro, rules=rules_state)`; state drift/write unchanged.

  `rule_settings.kiro_root` is the effective Kiro root: non-`None` exactly when Kiro is enrolled and projected this run.

### `src/tools/braid/domain/rules.py`

```python
RULE_NAME = re.compile(r"[a-z0-9-]+")
KNOWN_HOSTS: tuple[str, ...] = ("claude", "kiro", "codex", "copilot", "pi", "gemini")
SINGLE_FILE_HOSTS: tuple[str, ...] = ("codex", "copilot", "pi", "gemini")
DIRECTORY_HOSTS: tuple[str, ...] = ("claude", "kiro")
HOST_INSTRUCTION_PATHS: dict[str, Path] = {      # relative to Path.home()
    "codex": Path(".codex") / "AGENTS.md",
    "copilot": Path(".copilot") / "copilot-instructions.md",
    "pi": Path(".pi") / "agent" / "AGENTS.md",
    "gemini": Path(".gemini") / "GEMINI.md",
}
GENERATED_HEADER = "<!-- Generated by braid. Edit the rule sources, not this file. -->"
GENERATED_LIMIT = 32768


@dataclass(frozen=True)
class RuleInventory:
    shared: dict[str, Path]               # name -> resolved rule directory
    hosts: dict[str, dict[str, Path]]     # host -> name -> resolved rule directory; only hosts with rules

    @property
    def empty(self) -> bool:
        return not self.shared and not self.hosts


@dataclass(frozen=True)
class RuleState:
    union: dict[str, str]                 # name -> source rule dir
    hosts: dict[str, dict[str, str]]      # host -> name -> source rule dir
    projected: dict[str, dict[str, str]]  # "claude" | "kiro" -> name -> union-view RULE.md path
    generated: dict[str, str]             # single-file host -> generated AGENTS.md path
    instructions: dict[str, str]          # single-file host -> host instruction link path

    @classmethod
    def empty(cls) -> RuleState: ...       # all five empty dicts

    def as_json(self) -> dict[str, Any]:   # the five keys, always all present
        ...

    @classmethod
    def from_json(cls, payload: object, path: Path) -> RuleState:
        """Raise BraidError(f"invalid rules state in {path}") unless payload is a dict holding
        exactly-typed union/generated/instructions: dict[str, str] and
        hosts/projected: dict[str, dict[str, str]], all five keys present,
        hosts keys in KNOWN_HOSTS, projected keys in DIRECTORY_HOSTS,
        generated/instructions keys in SINGLE_FILE_HOSTS."""


def discover_rules(sources: Iterable[Path]) -> RuleInventory: ...
def render_host_file(shared: Mapping[str, Path], host_rules: Mapping[str, Path]) -> str: ...
def sync_rules(
    settings: Settings,
    inventory: RuleInventory,
    ignored: set[str],
    previous: RuleState | None,
    result: Result,
    emit: Callable[[str], None],
) -> RuleState | None: ...
```

`__all__` = `DIRECTORY_HOSTS`, `GENERATED_HEADER`, `GENERATED_LIMIT`, `HOST_INSTRUCTION_PATHS`, `KNOWN_HOSTS`, `SINGLE_FILE_HOSTS`, `RuleInventory`, `RuleState`, `discover_rules`, `render_host_file`, `sync_rules`.

#### `discover_rules(sources)` contract

- Iterate `sources` in order; `source = _resolved(configured)`; skip a resolved source already seen; skip `is_legacy_skills_source(source)` (a configured `skills` directory contributes skills only).
- Shared rules: candidates in `source / "rules"` (if a directory), sorted by name.
- Host rules: entries in `source / "hosts"` (if a directory), sorted by name. Skip names starting with `.`, non-directories and symlinks. Any other entry whose name is not in `KNOWN_HOSTS` → `BraidError(f"unknown host directory: {entry}")`. For a known host, candidates in `entry / "rules"` (if a directory), sorted by name.
- A candidate is skipped when it is a symlink, its name starts with `.`, it is not a directory, or `candidate / "RULE.md"` is not a file. Otherwise its name must `RULE_NAME.fullmatch`, else `BraidError(f"invalid rule name {candidate.name!r}: {candidate}")`.
- Each kept candidate's `RULE.md` is read once as UTF-8 (`_read_rule`, below) so a non-UTF-8 or unreadable file fails discovery before any write.
- Duplicates: a shared name already shared, or a host name equal to any shared name (in any order of discovery), or a host name already in that host's map → `BraidError(f"duplicate rule name {name!r}: {first_source} and {configured}")`, where `first_source` is the resolved configured source that first claimed the name. A shared rule discovered after a same-named host rule is the same error. Rule names never collide with skill names (separate namespace).
- Dict insertion order = source position, then name (sorted within each directory). `render_host_file` relies on it.

```python
def _read_rule(rule_file: Path) -> str:
    try:
        return rule_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise BraidError(f"cannot read {rule_file}: {error}") from error
```

#### `render_host_file(shared, host_rules)` contract

`bodies = [_read_rule(d / "RULE.md").rstrip() for d in (*shared.values(), *host_rules.values())]`; drop empty bodies; return `"\n\n".join([GENERATED_HEADER, *bodies]) + "\n"`. Output: header line, blank line, bodies separated by one blank line, exactly one trailing newline; with no rules it is `GENERATED_HEADER + "\n"`. Callers pass eligible (non-ignored) maps in inventory order.

#### `sync_rules(...)` contract

Returns `None` (and touches nothing, emits nothing, changes no counter) when `inventory.empty and previous is None`. Otherwise `previous = previous or RuleState.empty()`, `suffix = _backup_suffix()`, `run_pass = _Pass(mode=settings.mode, platform=settings.platform, result=result, emit=emit)`, and in this order:

1. **Union views, create/refresh only** (`preserve_real_sources=True`, `backup_root=settings.agents_root / "backups" / suffix`):
   - shared: `desired=inventory.shared`, `previous=previous.union`, `destination_root=settings.agents_root / "rules"`, `backup_category="rules"`.
   - per host in `sorted(set(inventory.hosts) | set(previous.hosts))`: `desired=inventory.hosts.get(host, {})`, `previous=previous.hosts.get(host, {})`, `destination_root=settings.agents_root / "hosts" / host / "rules"`, `backup_category=f"hosts/{host}/rules"`. Hosts whose resulting map is empty are left out of the next state.
   - Each union projection is built once with the full `previous` (kept for step 3b), but `_sync_links` is called with `dataclasses.replace(projection, previous={n: t for n, t in projection.previous.items() if n in projection.desired})`, so this step removes nothing. Reason: a directory-host link points into the union view; on Windows a hard-link fallback is judged with `os.path.samefile` against the union-view `RULE.md`, which fails once the union link is gone, and `_remove_stale_links` would then raise "refusing to clean changed managed path". Creation still needs the union first (a hard link needs an existing target).
   - Ignored names stay in both union views.
2. **Eligibility**: `eligible_shared = {n: p for n, p in inventory.shared.items() if n not in ignored}`; `eligible_host(h)` likewise over `inventory.hosts.get(h, {})`. For each host projection that runs (step 3 Claude when projected, step 3 Kiro when projected, step 4 for each of the four single-file hosts), `result.ignored += len({n for n in (*inventory.shared, *inventory.hosts.get(host, {})) if n in ignored})`.
3. **Directory hosts** (file links, `entry_suffix=".md"`, `file_links=True`, `preserve_real_sources=False`, `backup_category="project"`). Desired targets are union-view files: shared `settings.agents_root / "rules" / n / "RULE.md"`, host `settings.agents_root / "hosts" / host / "rules" / n / "RULE.md"`.
   - Claude when `settings.project_claude`: desired = eligible shared + eligible `claude` rules; `destination_root=settings.claude_root / "rules"`; `backup_root=settings.claude_root / "rules-backup" / suffix`; `previous=previous.projected.get("claude", {})`. With `--no-claude`, `previous.projected["claude"]` (if any) is carried over unchanged.
   - Kiro when `settings.project_kiro and settings.kiro_root is not None`: desired = eligible shared + eligible `kiro` rules; `destination_root=settings.kiro_root / "steering"`; `backup_root=settings.kiro_root / "steering-backup" / suffix`; `previous=previous.projected.get("kiro", {})`. With `--no-kiro` (`project_kiro` false), `previous.projected["kiro"]` is carried over unchanged. Kiro not enrolled → no `kiro` key.
   - Unrecorded files in these directories are never touched (only `desired` and `previous` names are visited).
   3b. **Union stale removal**: after both directory hosts, call `_remove_stale_links(projection, run_pass)` for every union projection from step 1 with its full `previous`. Report lines for removed union links therefore follow the directory-host lines.
4. **Generated files**, for `host in SINGLE_FILE_HOSTS` (always, every run): `content = render_host_file(eligible_shared, eligible_host(host))`, `path = settings.agents_root / "hosts" / host / "AGENTS.md"`, `expected = content.encode("utf-8")`.
   - current bytes = `path.read_bytes()` when `path.is_file()`, else `None`; an `OSError` → `BraidError(f"cannot read {path}: {error}")`.
   - equal → `result.current += 1`, record `generated[host] = str(path)`.
   - differ: `result.drift += 1`; CHECK → emit `MISMATCH GENERATED {path}`; DRY_RUN → emit `WOULD GENERATE {path}`; SYNC → `path.parent.mkdir(parents=True, exist_ok=True)`; if `_present(path)` and `previous.generated.get(host) != str(path)` (a file braid never generated), `_backup(path, settings.agents_root / "backups" / suffix, f"generated/{host}", result, emit)` first; then `atomic_write_bytes(path, expected)` (OSError → `BraidError(f"cannot write {path}: {error}")`), `result.generated += 1`, emit `GENERATE {path}`, record. CHECK/DRY_RUN do not record.
   - then, in every mode, when `len(expected) > GENERATED_LIMIT`: `result.drift += 1`, emit `MISMATCH OVERSIZE {path} is {len(expected)} bytes; limit 32768`.
5. **Host instruction links**, for `host in SINGLE_FILE_HOSTS`: `link = Path.home() / HOST_INSTRUCTION_PATHS[host]`, `host_root = Path.home() / HOST_INSTRUCTION_PATHS[host].parts[0]`, `target = settings.agents_root / "hosts" / host / "AGENTS.md"`, `recorded = previous.instructions.get(host) == str(link)`.
   - `not host_root.is_dir()` → skip silently, not recorded, no counter.
   - `_points_to(link, target, platform)` → `result.current += 1`, record.
   - `regenerated` = the set of hosts whose generated file step 4 wrote in this run (SYNC only; empty in CHECK/DRY_RUN).
   - `owned = recorded and (link.is_symlink() or (platform == "nt" and link.is_file() and host in regenerated))` - a recorded path is braid's while it is still a symlink, or, on Windows, the regular file of a hard-link fallback that this run's own regeneration just detached (the atomic write gave the generated file a new inode). A recorded Windows regular file that is not `samefile` with the target in a run that did not regenerate is someone else's file.
   - `_present(link) and not owned` → `result.unmanaged += 1`, emit `UNMANAGED {link}`, never modified or backed up, not drift. The previous record, if any, is carried over unchanged (`instructions[host] = previous.instructions[host]`), so replacing a managed link with a real file does not change state and CHECK stays exit 0. If a run dies between step 4 and step 5 on Windows, the detached hard link reads UNMANAGED on the next run: the safe direction, never a destroyed file.
   - otherwise (absent, or owned but no longer pointing at `target`): `result.drift += 1`; CHECK → emit `MISMATCH {link} -> {target}`; DRY_RUN → emit `WOULD LINK {link} -> {target}`; SYNC → `link.parent.mkdir(parents=True, exist_ok=True)`; if `_present(link)`: `_backup(link, settings.agents_root / "backups" / suffix, f"instructions/{host}", result, emit)`; `backend = create_file_link(link, target, platform=platform)`; `result.linked += 1`; emit `LINK[{backend}] {link} -> {target}`; record `instructions[host] = str(link)`. CHECK/DRY_RUN do not record.
6. **Orphans** (CHECK and DRY_RUN only, `_report_orphan_links`): `layout = [s for s in resolved deduped sources if not is_legacy_skills_source(s)]`.
   - `settings.agents_root / "rules"`, owners `[s / "rules" for s in layout]`, recorded `{*inventory.shared, *previous.union}`.
   - for each host in `KNOWN_HOSTS`: `settings.agents_root / "hosts" / host / "rules"`, owners `[s / "hosts" / host / "rules" for s in layout]`, recorded `{*inventory.hosts.get(host, {}), *previous.hosts.get(host, {})}`.
   - Claude when projected: `settings.claude_root / "rules"`, owners `[settings.agents_root / "rules", settings.agents_root / "hosts", *[s / "rules" for s in layout], *[s / "hosts" / h / "rules" for s in layout for h in KNOWN_HOSTS]]`, recorded `{f"{n}.md" for n in {*claude_desired, *previous.projected.get("claude", {})}}`.
   - Kiro when projected: same owners against `settings.kiro_root / "steering"` with the Kiro names.
   - Why the source rule dirs are owners: `_report_orphan_links` judges `_resolved(target.parent) / target.name`. For a skill link the target's parent is the plain union root; for a rule file link (`agents_root/rules/<n>/RULE.md`) the parent is the union symlink itself, which resolves into the source tree, so only the source rule directories can match. The union roots stay as owners for links whose union entry no longer exists. `_report_orphan_links` itself is unchanged. Hard links (Windows fallback) are not symlinks and are not scanned: an unrecorded hard link has no target to judge. Accepted, Windows-only.
   - Test: a stray `~/.claude/rules/stray.md` symlink to `~/.agents/rules/<n>/RULE.md` reports `MISMATCH ORPHAN` under CHECK.
7. Return `RuleState(union=..., hosts=..., projected=..., generated=..., instructions=...)`.

The engine helpers come in through one function-local import at the top of `sync_rules`:
`from braid.domain.engine import _backup, _backup_suffix, _Pass, _points_to, _Projection, _remove_stale_links, _report_orphan_links, _sync_links, create_file_link` with a comment naming the cycle it avoids.

### `src/tools/braid/commands/compose/compose.py`

Summary line (exact):

```
braid: {linked} linked, {generated} generated, {current} current, {ignored} ignored, {removed} removed, {backed_up} backed up, {configured} configured, {unmanaged} unmanaged, {drift} {change_label}
```

`metadata = {"drift": result.drift, "unmanaged": result.unmanaged, "exit_code": exit_code}`; the error branch adds `"unmanaged": 0`. Exit code rule unchanged: `1` only in CHECK with `drift > 0`; `UNMANAGED` never raises it.

### Report lines (new)

| line | when |
|---|---|
| `GENERATE {path}` | SYNC wrote a generated file |
| `WOULD GENERATE {path}` | DRY_RUN, generated file differs |
| `MISMATCH GENERATED {path}` | CHECK, generated file differs |
| `MISMATCH OVERSIZE {path} is {n} bytes; limit 32768` | any mode, content > 32768 bytes |
| `UNMANAGED {path}` | any mode, host instruction path present and not recorded |
| `LINK[hardlink] {dest} -> {target}` | SYNC, Windows file-symlink denied (winerror 5/1314) |

Existing `LINK[...]`, `WOULD LINK`, `MISMATCH ... -> ...`, `MISMATCH STALE`, `WOULD REMOVE`, `REMOVE`, `MISMATCH CHANGED`, `MISMATCH ORPHAN`, `BACKUP` keep their formats for rule links.

### State file shape (when any rule projection exists)

```json
{
  "version": 1,
  "union": {"...": "..."},
  "hosts": {"...": {}},
  "rules": {
    "union": {"safety": "/src/a/rules/safety"},
    "hosts": {"codex": {"codex-only": "/src/a/hosts/codex/rules/codex-only"}},
    "projected": {"claude": {"safety": "/home/.agents/rules/safety/RULE.md"}},
    "generated": {"codex": "/home/.agents/hosts/codex/AGENTS.md", "copilot": "...", "pi": "...", "gemini": "..."},
    "instructions": {"codex": "/home/.codex/AGENTS.md"}
  }
}
```

Written with the existing `json.dumps(..., indent=2, sort_keys=True)` via `atomic_write_text`.

## Data flow

```
sources.d + --source ──► resolve_settings ──► Settings
                                   │
         ┌─────────────────────────┴───────────────────────┐
 discover_inventory (skills)                   discover_rules (rules, reads RULE.md once)
         │                                                  │
 skill union + Claude/Kiro skill links         (errors here exit 2 before any write)
         │                                                  │
         └──────────► sync_rules(rule_settings, RuleInventory, ignored, previous.rules)
                         1 union views  ~/.agents/rules/<n>, ~/.agents/hosts/<h>/rules/<n>  → source dirs
                         3 directory hosts ~/.claude/rules/<n>.md, <kiro>/steering/<n>.md  → union-view RULE.md
                         4 generated   ~/.agents/hosts/<h>/AGENTS.md  ← render(eligible shared, eligible host)
                         5 instructions ~/.codex/AGENTS.md etc.  → generated file (UNMANAGED if foreign)
                         6 orphans (check/dry-run)
                                   │
                         RuleState | None ──► State.rules ──► .braid-state.json
                                   │
                         Result ──► CommandCompose summary ──► cli console
```

Directory hosts point at union views (not sources) so a rule moving between sources does not rewrite host links; the union link absorbs the move, as for skills.

## Reuse inventory

- `engine._sync_links` / `_remove_stale_links` / `_Projection` / `_Pass` (`src/tools/braid/domain/engine.py`): the whole link-diff, backup, stale-removal and report-line logic. Reused for the two union views and both directory hosts, extended by `entry_suffix` and `file_links`.
- `engine._report_orphan_links`: orphan scan for rule union roots, `~/.claude/rules`, `<kiro>/steering`.
- `engine._backup`: instruction-link backups.
- `engine._points_to`: current-link test for every rule link and instruction link (extended for Windows hard links).
- `engine.create_directory_link`: template for `create_file_link` (same winerror 5/1314 gate).
- `engine._load_state` / `_write_state`: unchanged except the `rules` key; `_write_state` already uses `atomic_write_text`.
- `buvis.pybase.filesystem.atomic_write.atomic_write_bytes(path, data)`: generated files (AGENTS.md "atomic persistence" invariant). The PRD names `atomic_write_text`, but that helper opens in text mode with `newline=None`, which writes CRLF on Windows while the drift check compares raw bytes, so the file would never converge there. `atomic_write_bytes` is the same module and the same atomic guarantee, and the bytes written are the bytes compared.
- `model._present`, `model._resolved`: existence and resolution.
- `kiro.select_kiro`: already computes the effective Kiro registration in `run()`; `sync_rules` receives its root via `replace(settings, kiro_root=...)` rather than re-selecting.
- `engine.read_ignored`: the same ignored-name set feeds rules.
- `tests/tools/braid/helpers.py` `make_skill`, `settings`, `enroll`, `kiro_root`, `read_state`: test builders, extended with `make_rule(source, name, body="...")` and `make_host_rule(source, host, name, body="...")`.
- Greps tried for a pre-existing generated-file or hard-link helper: `rg -n "os.link|hardlink|samefile" src/` (none), `rg -n "def atomic_write_text" src/lib` (found, used), `rg -n "render|generate" src/tools/braid` (none). Nothing else to reuse.

## Alternatives considered

1. **Smallest diff: rules as fake skills.** Treat `rules/<n>/RULE.md` like skills, reuse `discover_inventory` with a different marker file, project only into `~/.claude/rules` and Kiro, and skip generated files. Rejected: the PRD's core outcome is the four generated single-file host files and the unmanaged-link rule; without them Codex/Copilot/Pi/Gemini keep the hand-kept file this PRD replaces.
2. **Move link helpers into a new `domain/links.py`** and import them from both `engine.py` and `rules.py` at top level. Cleaner import graph, but it moves ~200 lines the PRD does not ask to move, and breaks two existing PRD 00115 tests that patch or call the helpers through `engine` (`test_cli.py:384`, `test_check.py:142`), which the PRD requires to keep passing unchanged.
3. **Chosen: new `rules.py` reusing engine helpers via one function-local import**, with two `_Projection` fields. Larger than option 1 by the generated-file and instruction-link steps (~120 lines) - that size is exactly the PRD's single-file host support. Kiro and the backup suffix reach `sync_rules` without widening its PRD signature: Kiro via `replace(settings, kiro_root=effective_root)`, the suffix via a shared `_backup_suffix()`.

Also rejected: a seventh `sync_rules` parameter for the Kiro registration (breaks the PRD's exported signature); keying `projected` state by `<name>.md` (the PRD shape says `{name: target}`; `entry_suffix` keeps keys bare).

## Risks & edge cases

- **Hand-made host links**: `~/.codex/AGENTS.md`, `~/.copilot/copilot-instructions.md`, `~/.pi/agent/AGENTS.md` link to `~/.claude/AGENTS.md` today. They are not recorded, so they report `UNMANAGED` and stay untouched; `--check` exit stays 0. The user removes each once to hand it over.
- **Rule named `agents` on a case-insensitive filesystem**: `~/.kiro/steering/agents.md` collides with the existing `AGENTS.md` link; per the PRD's same-name rule it is backed up to `steering-backup/<suffix>/project/` and replaced. Documented in `braid.rst`; recoverable from the backup.
- **Generated file oversize**: written anyway, drift counted every run, so `--check` fails until sources shrink. Size measured in UTF-8 bytes.
- **Windows hard links**: an atomic regeneration or a `git checkout` that rewrites `RULE.md` breaks `samefile`; the link reports drift and the next sync backs it up and relinks (instruction links: recorded → backup + relink; directory hosts: `_sync_links` backup + relink). Removing a rule from the configured sources works because directory-host stale removal (step 3) runs before union stale removal (step 3b). A rule whose source directory was deleted (dangling union link) or whose `RULE.md` was rewritten before removal fails `samefile`; the file-link branch of `_remove_stale_links` backs the old hard link up instead of raising, so sync completes and nothing is destroyed. Limit: a union link that fell back to a Windows junction (directory symlink denied) and now dangles because its source directory was deleted fails both `is_symlink()` and `is_dir()` in `engine._points_to`, so union stale removal (step 3b) raises "refusing to clean changed managed path". This is the existing PRD 00115 engine behavior for skill junctions too; rules reuse it and do not make it worse. The user removes the dangling junction by hand; dangling-junction recognition in `_points_to`/`_remove_owned_link` is a follow-up for both kinds, not part of this PRD. No CI cell runs Windows, so the `platform="nt"` tests (fallback creation, check convergence, rule removal) are the only guard.
- **All rules removed after a rule run**: `previous` is not `None`, so the pass still runs: union/projection links are removed as stale, generated files shrink to the header line, instruction links stay. `state.rules` persists (generated files exist). A skill-only setup that never had rules never gets a `rules` key.
- **Mixed legacy source**: a configured `.../skills` directory contributes skills only; its sibling `rules/` is not read. Configure the repo root instead.
- **Rollback**: the state stays `version: 1` and `rules` is optional, so reverting the code leaves a state file whose extra `rules` key the PRD 00115 loader ignores (it reads only `union`/`hosts`/`kiro`). Rule links and generated files stay on disk after a revert; they are plain symlinks/files the user can remove. No migration needed: an absent `rules` key loads as `None`.
- **Next changes likely**: (a) a third kind (e.g. agents/prompts) - the `hosts/<host>/<kind>` layout and `KNOWN_HOSTS` generalize; the per-kind code would want the same `_Projection` knobs; (b) per-host size limits other than 32768 - `GENERATED_LIMIT` is one constant, a dict keyed by host is the upgrade; (c) project-scoped (non-home) instruction files - `HOST_INSTRUCTION_PATHS` is home-relative by design, would need a root parameter. Nothing here boxes these in.

## Test strategy outline

All tests use the autouse isolation fixture (HOME = `tmp/home`), `helpers.settings(...)`, `make_skill`, and the new `make_rule` / `make_host_rule`.

`tests/tools/braid/test_rules.py` (engine level, via `run()` and `discover_rules` / `render_host_file`):

- discovery/layout: rule-only source accepted; source with none of `skills/rules/hosts` → `BraidError("source has no skills, rules or hosts directory: ...")`; invalid rule name refused; `hosts/vscode` → `unknown host directory`; shared/shared and shared/host and host/host duplicates refused (and nothing written: agents root absent); symlinked rule dir skipped; non-UTF-8 `RULE.md` refused.
- render: header exact, order by source then name, trailing whitespace stripped, single trailing newline, empty-rule case.
- the PRD-named tests: `test_skill_only_source_keeps_the_skills_state_shape` (state bytes have only `version/union/hosts`, no `rules`/`hosts` dirs under agents root, no rule lines emitted), `test_existing_host_instruction_link_is_reported_unmanaged_and_kept`, `test_ignored_rule_leaves_every_host` (still under `~/.agents/rules`, absent from `~/.claude/rules`, Kiro steering and all four generated files; `result.ignored` counts per host projection), `test_malformed_rules_state_is_refused`, `test_missing_host_root_skips_the_instruction_link`, `test_stale_generated_file_is_check_drift`, `test_oversized_generated_file_fails_check`, `test_windows_file_link_falls_back_to_hard_link` (patch `os.symlink` to raise `OSError` with `winerror = 1314` only for `RULE.md`/`AGENTS.md` targets, `platform="nt"`; assert `LINK[hardlink]`, `os.path.samefile`, and a following `--check` with 0 drift), `test_rule_removed_from_source_unlinks_from_claude_and_kiro`.
- Windows removal: `platform="nt"` with the hard-link fallback, sync, then (a) drop the rule's source from the configured sources and (b) in a second case delete the rule directory from the source; sync again → (a) `REMOVE` lines, (b) `BACKUP` of the hard link; no `BraidError` in either.
- generated collision: a pre-existing unrecorded `~/.agents/hosts/codex/AGENTS.md` is backed up under `backups/<suffix>/generated/codex/` before the first `GENERATE`; an edited, recorded generated file is overwritten without backup.
- instruction ownership: a recorded `~/.codex/AGENTS.md` replaced by a regular file (posix) → `UNMANAGED`, file untouched, record kept, and an immediate CHECK exits 0 (no `MISMATCH STATE`). On `platform="nt"`: a recorded hard link detached by this run's regeneration is backed up and relinked; a recorded regular file in a run with no regeneration that is not `samefile` with the target → `UNMANAGED`.
- orphan: stray `~/.claude/rules/stray.md` symlink into the union view → `MISMATCH ORPHAN` under CHECK.
- exit-criteria scenario: one shared, one claude, one codex rule over two sources, Claude + enrolled Kiro, host roots present → every link/file exists, state as specified, immediate `Mode.CHECK` run → `drift == 0`.

`tests/tools/braid/test_rules_cli.py` (CliRunner, same pattern as `test_cli.py`): summary line with `generated` and `unmanaged`; unmanaged host path → `--check` exit 0 with `UNMANAGED` line; duplicate rule → exit 2; stale generated file → `--check` exit 1.

Regression: `test_engine.py`, `test_check.py` unchanged and green; `test_cli.py` only the six summary literals updated. Full gate: `uv run pytest`, `uv run mypy src/lib/ src/tools/`, `uv run ruff check`, `uv run sphinx-build -W -b html docs/source docs/build/html`.

## Review log

Dispatch 1 fixed blockers: rule orphan scan could not match file links (owners extended to source rule dirs, step 6); Windows rule removal raised because union links were removed before host links (union stale removal split to step 3b); generated files never converged on Windows under `atomic_write_text` (switched to `atomic_write_bytes`).

- non-blocker (d1): a recorded instruction path that became a regular file is backed up and replaced, while the PRD says replace only "a link braid recorded". Kept: on Windows the recorded hard link is a regular file whose inode the regeneration orphans (`st_nlink == 1`), so a link-only test would turn every content change into a permanent UNMANAGED. The backup under `backups/<suffix>/instructions/<host>/` means nothing is lost.
- non-blocker (d1): one-body `sync_rules` would trip PLR0912/PLR0915. Implementer splits it into private helpers per step (e.g. `_sync_union_views`, `_sync_directory_hosts`, `_sync_generated`, `_sync_instruction_links`, `_report_rule_orphans`); the file-wide PLR0913 ignore covers their parameter counts.
- question (d1): no way to retire rules once used (`previous` keeps the pass alive, header-only files keep regenerating). Answer for docs: remove the `rules` key from `.braid-state.json` (or the state file) and the links by hand; braid.rst states it.
- question (d1): PRD "byte-identical state and output" vs the mandated summary change. Read as: state bytes identical and every emitted line except the summary identical; `test_cli.py` changes only the six summary literals.
- question (d1): instruction links always use `Path.home()` even with `--agents-root` overridden, so a scratch run can claim `~/.codex/AGENTS.md` for a throwaway root. PRD defines only home paths; braid.rst warns that `--agents-root` runs still touch home host paths.
dispatch 1 (claude): cardinal-sin 0, blocker 3, non-blocker 2, question 3

Dispatch 2 note: the first codex call could not read the repo (nested `sandbox-exec` denied under the Seatbelt profile); it was re-run with the design, PRD and engine sources inlined, and that run's findings count as dispatch 2.

Dispatch 2 fixed blockers: Windows removal after the source rule is deleted still raised (file-link stale removal now backs up instead of raising); generated-file creation could overwrite an unrecorded file (backed up first); a recorded instruction path replaced by a real file was replaced (now `owned` requires a link; posix regular file → UNMANAGED; this supersedes the d1 non-blocker decision above for posix); `_remove_stale_links` missing from the function-local import.

- blocker part rejected (d2): an unrecorded instruction link that already points at the generated file is adopted (current, recorded), which changes state once and makes that CHECK report `MISMATCH STATE`. Kept: identical to how `_sync_links` adopts a correctly-pointing unrecorded skill link after a lost state file; one sync settles it, and it can only happen when the link already targets braid's own generated file.
- non-blocker (d2): a host root removed after a recorded instruction link drops the record, so the next CHECK shows `MISMATCH STATE` once. Accepted as manifest cleanup; documented in braid.rst.
- non-blocker (d2): `render_host_file` re-reads `RULE.md` after discovery validated it, so a file changed or deleted mid-run can fail after some writes or give hosts different snapshots. Accepted: the window is one run, a failure exits 2 with the state unwritten, and the next run converges.
dispatch 2 (codex): cardinal-sin 0, blocker 4, non-blocker 2, question 0

Dispatch 3 (codex, sources inlined) fixed blockers: an UNMANAGED replacement dropped the record and made CHECK exit 1 via `MISMATCH STATE` (record now carried over); Windows ownership claimed any recorded regular file (now only a hard link this run's regeneration detached); the Windows deleted-source promise ignored dangling junctions (claim narrowed: that is the shared PRD 00115 engine limitation, recorded as a follow-up for skills and rules alike, not regressed here).

- non-blocker (d3): orphan detection misses an unrecorded host link through a union entry whose source was removed from the configuration (its parent resolves into a source no longer in `layout`). The stale union entry itself still reports drift, so CHECK still fails; the orphan line is missing only until the sync removes the entry. Accepted.
dispatch 3 (codex): cardinal-sin 0, blocker 3, non-blocker 1, question 0
