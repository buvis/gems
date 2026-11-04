# Design: 00115 braid port at parity

PRD: `docs/dev/project-management/prds/wip/00115-braid-port-skills-parity-v1.md`.
Reference: `~/git/src/github.com/buvis/agent-skills` at d535891. The PRD-relevant
files there (`src/agent_skills_braid/cli.py`, `tests/test_braid.py`,
`tests/test_braid_check.py`) are byte-identical to that checkout's HEAD 452a4e6
(`git diff --stat d535891 HEAD` over them is empty), so read them from the
working tree. Test counts were re-measured on 2026-11-04: 31 and 13, which
matches the PRD premise.

## Architecture fit

braid lands as a new gems tool under `src/tools/braid/`. It uses the standard
three layers: `cli.py` (Click adapter), `commands/compose/` (the command class
that returns `CommandResult`), and `domain/` (pure composition logic, no Click,
no console). It follows the pattern of `backup` (a single `@click.command`, not a
group, decorated with `buvis_options(settings_class=...)`) and `pinger` (a
command class with lazy imports in the handler).

Invariants that bind (AGENTS.md § Invariants):

- Atomic persistence: the Braid state file goes through
  `buvis.pybase.filesystem.atomic_write_text`. The Kiro agent rewrite keeps its
  own compare-before-replace tempfile plus `os.replace`, which is atomic but not
  a bare write.
- CommandResult discipline: `CommandCompose.execute()` never exits and never
  prints. It returns `CommandResult`, and `cli.py` maps that result to output and
  an exit code.
- All output goes through the `console` adapter. The domain emits plain strings
  through an `emit` callable. The CLI writes each report line with
  `console.console.out(line, highlight=False)`, the adapter's own Rich console
  used the way `ConsoleAdapter.nl` uses it. `Console.out` applies no markup and
  never wraps, so `LINK[symlink]` survives and a long path stays on one line even
  at the 80-column width Rich falls back to when stdout is not a TTY (cron,
  sysup, pipes). The lines are byte-identical to the reference `print`.
  `console.print(mode="raw")` was rejected because Rich wraps it.
- No cross-tool imports. braid imports only `buvis.pybase.*`, `click`, `rich`
  and the stdlib.

## Module placement

All files are new except the six edited files at the end of the list.

```text
src/tools/braid/__init__.py                  new  `from __future__ import annotations` only, as in peers (pinger, backup); --version comes from buvis_options via package metadata, so no __version__
src/tools/braid/__main__.py                  new  `from braid.cli import cli` / `cli()` under `if __name__ == "__main__":`
src/tools/braid/cli.py                       new  Click command `cli`
src/tools/braid/settings.py                  new  BraidSettings
src/tools/braid/manifest.toml                new  tool manifest, cli = true only
src/tools/braid/commands/__init__.py         new  empty (`from __future__ import annotations`)
src/tools/braid/commands/compose/__init__.py new  empty
src/tools/braid/commands/compose/compose.py  new  CommandCompose
src/tools/braid/domain/__init__.py           new  empty
src/tools/braid/domain/model.py              new  shared types and path helpers (breaks the engine<->kiro import cycle)
src/tools/braid/domain/kiro.py               new  Kiro dataclasses and the three Kiro functions
src/tools/braid/domain/engine.py             new  everything else from reference lines 1-629, plus ComposeRequest/resolve_settings (from reference main())
tests/tools/braid/__init__.py                new  empty
tests/tools/braid/conftest.py                new  autouse env + console fixtures
tests/tools/braid/helpers.py                 new  make_skill, settings, kiro_root, enroll, write_agent, read_state
tests/tools/braid/test_engine.py             new  ported test_braid.py engine cases
tests/tools/braid/test_check.py              new  ported test_braid_check.py engine cases
tests/tools/braid/test_cli.py                new  CLI cases via CliRunner
pyproject.toml                               edit scripts, wheel packages, markers
README.md                                    edit CLI list (15 -> 16), tools table, tool section
AGENTS.md                                    edit Architecture tree
docs/source/tools.rst                        edit table row + toctree entry
docs/source/tools/braid.rst                  new  tool page
CHANGELOG.md                                 edit [Unreleased] Added entry
```

Deviations from the PRD's Repository Structure tree, and why:

1. `domain/model.py` is a third domain file. `kiro.py` needs `BraidError`,
   `Mode`, `Result`, `Settings` and the path helpers. `engine.py` needs
   `KiroRegistration` (in `State`) and the Kiro functions (in `run`). Two files
   would import each other, so the shared names move to `model.py`, which
   imports neither. `engine.py` re-exports every model name, so
   `from braid.domain.engine import run, BraidError, Mode` (the Phase 0
   acceptance command) still works.
2. `tests/tools/braid/helpers.py` holds the helper functions instead of
   `conftest.py`. The suite runs with `--import-mode=importlib`, where
   `conftest.py` cannot be imported as a module. The repository precedent is
   `from tests.tools.backup.parallel_runner_helpers import ...`. `conftest.py`
   keeps the autouse fixtures that the PRD names.
3. Source and policy resolution moves from the PRD's `cli` module into
   `engine.resolve_settings`, and `CommandCompose` takes an unresolved
   `ComposeRequest` instead of resolved settings. The reason is in
   `### src/tools/braid/commands/compose/compose.py`.
4. `__init__.py` carries no `__version__`/`__all__`. No peer tool has them, and
   the reference's only use of `__version__` was `--version`, which
   `buvis_options` now supplies.

## Interfaces & contracts

### `src/tools/braid/domain/model.py`

Copy these verbatim from the reference `cli.py`, changing nothing but the
module they live in: `STATE_VERSION = 1`, `SKILL_NAME`, `AGENT_NAME`,
`class BraidError(RuntimeError)`, `class Mode(str, Enum)` (`SYNC = "sync"`,
`DRY_RUN = "dry-run"`, `CHECK = "check"`),
`@dataclass(frozen=True) class Settings` (fields and defaults exactly as the
reference, including `platform: str = os.name` and `with_mode`),
`@dataclass class Result` (`linked, current, ignored, removed, backed_up, drift,
configured`, all `int = 0`), `def _present(path: Path) -> bool`,
`def _expand_user(path: str | Path) -> Path`, `def _resolved(path: Path) -> Path`,
`def _absolute(path: Path) -> Path`.

### `src/tools/braid/domain/kiro.py`

Imports from `braid.domain.model`. Copy these verbatim:
`@dataclass(frozen=True) class KiroRegistration` (`root: Path`,
`agents: tuple[str, ...] = ()`), `@dataclass(frozen=True) class KiroAgentEdit`
(`path: Path`, `before: bytes`, `after: bytes | None`),
`def select_kiro(settings: Settings, previous: KiroRegistration | None) -> KiroRegistration | None`,
`def prepare_kiro_agents(registration: KiroRegistration, agents_root: Path) -> tuple[KiroAgentEdit, ...]`,
`def sync_kiro_agent(edit: KiroAgentEdit, backup_root: Path, mode: Mode, result: Result, emit: Callable[[str], None]) -> None`.
Bodies and messages are byte-identical, including the `tempfile.NamedTemporaryFile`
plus `shutil.copymode` plus double `read_bytes() != edit.before` check plus
`os.replace` sequence.

### `src/tools/braid/domain/engine.py`

Imports from `model` and `kiro`. It re-exports through `__all__`:
`STATE_VERSION, BraidError, Mode, Settings, Result, State, KiroRegistration,
KiroAgentEdit, ComposeRequest, discover_inventory, read_configured_sources,
read_ignored, create_directory_link, select_kiro, prepare_kiro_agents,
sync_kiro_agent, resolve_settings, run`.

Copy verbatim from the reference: `class State` (with `empty`, `as_json`),
`_skill_name`, `_skills_directory`, `discover_inventory`,
`read_configured_sources`, `read_ignored`,
`create_directory_link(destination, target, *, platform=os.name, runner=subprocess.run) -> str`,
`_points_to`, `_load_state`, `_backup`, `_remove_owned_link`,
`_report_orphan_links`, `_deduplicate`. `_report_orphans` and `_sync_links`
change signature only (see `### Ruff gate: parameter objects, no suppressions`).

Changed, with nothing else changed:

```python
def _discard(_line: str) -> None:
    """Default emit: the domain never writes to a stream itself."""


def _write_state(path: Path, state: State) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(state.as_json(), indent=2, sort_keys=True) + "\n")
    except OSError as error:
        raise BraidError(f"cannot write Braid state {path}: {error}") from error


def run(settings: Settings, emit: Callable[[str], None] = _discard) -> Result:
    ...  # reference body, unchanged
```

`atomic_write_text` is imported as
`from buvis.pybase.filesystem.atomic_write import atomic_write_text`.
The reference's `contextlib`, `tempfile` and `print` default go away from
`engine.py`. `tempfile` stays imported in `kiro.py`. The default `emit` moved
from `print` to `_discard`. This keeps the Phase 0 acceptance check
(`rg -n "print\(" src/tools/braid/domain` finds nothing) and the "no output
outside console" invariant. Every reference engine test calls `run` without
reading stdout, so no ported test sees the difference.

New, ported from the reference `main()`, without `_repository_root` and the
`repository_root` source and policy candidates:

```python
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


def resolve_settings(request: ComposeRequest) -> Settings:
    agents_root = _expand_user(request.agents_root)
    claude_root = _expand_user(request.claude_root)
    config_root = _expand_user(request.config_root)
    sources = _deduplicate([*read_configured_sources(config_root), *request.sources])
    if not sources:
        raise BraidError(
            "no skill sources configured; add a path under "
            f"{config_root / 'sources.d'} or pass --source"
        )
    candidates = [agents_root / ".braidignore", config_root / ".braidignore"]
    for source in sources:
        policy_root = source if (source / "skills").is_dir() else source.parent
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
```

`config_root` is user-expanded before the error message is built. So the default
`~/.config/braid` is reported as `<home>/.config/braid/sources.d`, the same
absolute form the reference printed for its `home / ".config" / "agent-skills"`
default.

### `src/tools/braid/settings.py`

```python
class BraidSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_BRAID_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    agents_root: Path = Path("~/.agents")
    claude_root: Path = Path("~/.claude")
    config_root: Path = Path("~/.config/braid")
    kiro_root: Path | None = None

    @field_validator("kiro_root", mode="before")
    @classmethod
    def _empty_kiro_root_is_unset(cls, value: object) -> object:
        return None if value == "" else value
```

The defaults are literal `~` paths, expanded by `resolve_settings` at run time.
They are not `Path.home()` at import time, so a test that sets `HOME` controls
them. The `field_validator` makes `BUVIS_BRAID_KIRO_ROOT=""` behave like an
unset `KIRO_ROOT` did in the reference (`if os.environ.get("KIRO_ROOT")`).
Without it, pydantic would coerce `""` to `Path(".")` and enroll the cwd. Env
names: `BUVIS_BRAID_AGENTS_ROOT`, `BUVIS_BRAID_CLAUDE_ROOT`,
`BUVIS_BRAID_CONFIG_ROOT`, `BUVIS_BRAID_KIRO_ROOT`. Nothing reads `AGENTS_ROOT`,
`CLAUDE_ROOT`, `KIRO_ROOT`, `AGENT_SKILLS_CONFIG` or `~/.config/agent-skills`.

### `src/tools/braid/commands/compose/compose.py`

```python
class CommandCompose:
    def __init__(self, request: ComposeRequest) -> None: ...

    def execute(self) -> CommandResult:
        lines: list[str] = []
        try:
            settings = resolve_settings(self.request)
            result = run(settings, lines.append)
        except (BraidError, OSError) as error:
            return CommandResult(
                success=False,
                output="\n".join(lines),
                error=f"braid: {error}",
                metadata={"drift": 0, "exit_code": 2},
            )
        change_label = "drift" if settings.mode is Mode.CHECK else "change(s)"
        lines.append(
            "braid: "
            f"{result.linked} linked, {result.current} current, {result.ignored} ignored, "
            f"{result.removed} removed, {result.backed_up} backed up, "
            f"{result.configured} configured, "
            f"{result.drift} {change_label}"
        )
        exit_code = 1 if settings.mode is Mode.CHECK and result.drift else 0
        return CommandResult(
            success=exit_code == 0,
            output="\n".join(lines),
            error=None,
            metadata={"drift": result.drift, "exit_code": exit_code},
        )
```

`OSError` is caught beside `BraidError`. Verbatim reference code lets raw
`OSError` escape from `read_configured_sources`, `read_ignored`,
`discover_inventory`, `_sync_links` (`mkdir`) and `_backup` (`shutil.move`).
In the reference that printed a traceback, after the streamed report lines.
Here, an uncaught `OSError` would also drop the buffered lines, including a
`BACKUP` line for a move that already happened. AGENTS.md also forbids
tracebacks reaching the user. So both errors map to the same exit 2 with
`braid: {error}` and keep the lines emitted so far. Exit 2 already meant "braid
failed"; this only widens which failures reach it cleanly.

The PRD writes `CommandCompose(settings)`. Its argument here is the unresolved
`ComposeRequest`, so source and policy resolution (which raises `BraidError`)
happens inside the one `try`. That gives a single `BraidError` to exit-2 mapping
and keeps resolution reusable by any later interface. `output` holds the report
lines emitted before a failure as well, so the CLI prints them before the error.
This preserves the reference order, where `emit=print` streamed them first. The
summary line is the last line of `output` on success, byte-identical to the
reference `print`.

### `src/tools/braid/cli.py`

```python
@click.command(help="Compose Agent Skills from multiple repositories and project them to hosts.")
@click.option("--dry-run", is_flag=True, help="report changes without writing")
@click.option("--check", is_flag=True, help="exit non-zero when links, resources or state drift")
@click.option("--source", "sources", multiple=True, type=click.Path(path_type=Path),
              help="additional repository root or skills directory (repeatable)")
@click.option("--policy", "policies", multiple=True, type=click.Path(path_type=Path),
              help="additional .braidignore file to load (repeatable)")
@click.option("--agents-root", type=click.Path(path_type=Path), default=None,
              help="override the ~/.agents union root, ahead of BUVIS_BRAID_AGENTS_ROOT")
@click.option("--claude-root", type=click.Path(path_type=Path), default=None,
              help="override the ~/.claude root, ahead of BUVIS_BRAID_CLAUDE_ROOT")
@click.option("--config-root", type=click.Path(path_type=Path), default=None,
              help="override the ~/.config/braid directory holding sources.d, ahead of BUVIS_BRAID_CONFIG_ROOT")
@click.option("--no-claude", is_flag=True, help="skip projecting skills into claude-root")
@click.option("--kiro", is_flag=True, help="enroll Kiro once; later runs remember it")
@click.option("--kiro-root", type=click.Path(path_type=Path), default=None,
              help="enroll a Kiro root (default ~/.kiro), ahead of BUVIS_BRAID_KIRO_ROOT and saved enrollment")
@click.option("--kiro-agent", "kiro_agents", multiple=True, metavar="NAME",
              help="enroll an existing <kiro-root>/agents/NAME.json for skill resources (repeatable)")
@click.option("--forget-kiro-agent", "forget_kiro_agents", multiple=True, metavar="NAME",
              help="stop managing a custom agent; keep its existing resources (repeatable)")
@click.option("--no-kiro", is_flag=True, help="skip Kiro for this run; preserve its links/enrollment")
@buvis_options(settings_class=BraidSettings)
@click.pass_context
def cli(ctx: click.Context, *, dry_run: bool, check: bool, sources: tuple[Path, ...],
        policies: tuple[Path, ...], agents_root: Path | None, claude_root: Path | None,
        config_root: Path | None, no_claude: bool, kiro: bool, kiro_root: Path | None,
        kiro_agents: tuple[str, ...], forget_kiro_agents: tuple[str, ...], no_kiro: bool) -> None:
```

Help texts are the reference `_parser()` strings. The only change is in the
three root options and `--kiro-root`, which name the new `BUVIS_BRAID_*`
variables instead of the dropped reference names. `click.Path` gets no
`exists=`, so there is no parse-time validation (AGENTS.md § Click argument
validation).

Callback body, in order:

1. `if dry_run and check:` → `console.failure("--dry-run cannot be combined with --check")`; `ctx.exit(2)`.
2. `if no_kiro and (kiro or kiro_root or kiro_agents or forget_kiro_agents):` → `console.failure("--no-kiro cannot be combined with Kiro enrollment options")`; `ctx.exit(2)`.
3. `settings = get_settings(ctx, BraidSettings)`.
4. Lazy imports: `from braid.commands.compose.compose import CommandCompose` and `from braid.domain.engine import ComposeRequest, Mode`.
5. Build `ComposeRequest(agents_root=agents_root or settings.agents_root, claude_root=claude_root or settings.claude_root, config_root=config_root or settings.config_root, sources=sources, policies=policies, mode=Mode.CHECK if check else Mode.DRY_RUN if dry_run else Mode.SYNC, project_claude=not no_claude, enable_kiro=kiro, kiro_root=kiro_root or settings.kiro_root, kiro_agents=kiro_agents, forget_kiro_agents=forget_kiro_agents, project_kiro=not no_kiro)`.
6. `result = CommandCompose(request).execute()`.
7. For each line in `(result.output or "").splitlines()`: `console.console.out(line, highlight=False)`.
8. `if result.error:` → `console.console.print(console.format_failure(escape(result.error)), soft_wrap=True)` (`from rich.markup import escape`). This is the same ✘ line that `console.failure` prints, but with `soft_wrap=True` so it is never split. The two option rejections in steps 1-2 use plain `console.failure`, because their messages are short and fixed.
9. `ctx.exit(result.metadata["exit_code"])` when it is non-zero. On 0, return normally.

`console.panic` is not used, because it exits 1. Exit codes: 0 success, 1 when
`--check` finds drift, 2 for both option rejections and any `BraidError`.

### `src/tools/braid/manifest.toml`

```toml
[tool]
name = "braid"
display_name = "Braid"
module_name = "braid"
description = "Compose agent skills from sources.d and project them to Claude Code and Kiro"
category = "system"

[tool.interfaces]
cli = true
rest = false
tui = false
web = false

[tool.requirements]
python = ">=3.11"
extras = []
```

### `pyproject.toml`

- `[project.scripts]`: `braid = "braid.cli:cli"` between `bim` and `dot`.
- `[tool.hatch.build.targets.wheel] packages`: `"src/tools/braid",` between `"src/tools/bim",` and `"src/tools/dot",`.
- `[tool.pytest.ini_options] markers`: `"braid: braid tests",` between `"bim: bim tests",` and `"dot: dot tests",`.
- No new extra: braid has no third-party dependency beyond core.

**Wiring order (overrides the PRD's phase order).** `tests/conftest.py:34-38`
adds `pytest.mark.braid` to every file under `tests/tools/braid/`, and
`strict_markers = true` makes an unregistered marker a collection error. So the
`"braid: braid tests",` marker line lands in the same task as the first braid
test file (Phase 0). The `[project.scripts]` and wheel-packages lines land in the
Phase 1 task that adds `cli.py`, followed by a re-sync, before
`uv run braid --help` is checked. Phase 2 then only verifies the wiring
(`check_tool_wiring.py`, `-m braid` collection) and writes the docs.

### Ruff gate: parameter objects, no suppressions

Ruff 0.17.3 (from uv.lock) under gems' config flags two verbatim reference
functions. `_report_orphans` takes 8 positional parameters (PLR0913, PLR0917),
and `_sync_links` takes 10 keyword parameters (PLR0913). Only
`src/tools/*/cli.py` has a PLR0913 ignore. The aegis `block_suppression_markers`
hook refuses any new inline ruff suppression comment, and per-file ignores are
protected config. So the fix is structural, and it changes signatures only,
never logic:

```python
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


@dataclass(frozen=True)
class _OrphanScope:
    """What the orphan scan compares the disk against."""
    inventory: dict[str, Path]
    eligible: dict[str, Path]
    previous: State
    kiro: KiroRegistration | None


def _sync_links(projection: _Projection, run_pass: _Pass) -> dict[str, str]: ...
def _report_orphans(
    settings: Settings,
    union_root: Path,
    scope: _OrphanScope,
    result: Result,
    emit: Callable[[str], None],
) -> None: ...
```

Each body opens by unpacking its objects into the reference's local names, for
example `desired, previous = projection.desired, projection.previous` and
`mode, platform, result, emit = run_pass.mode, run_pass.platform, run_pass.result, run_pass.emit`.
After that, the reference body follows unchanged. `run()` builds one `_Pass`
after `result = Result()`, and replaces each of its three `_sync_links(...)`
calls with `_sync_links(_Projection(...same keyword values...), run_pass)`. Its
`_report_orphans(...)` call becomes
`_report_orphans(settings, union_root, _OrphanScope(inventory, eligible, previous_state, kiro), result, emit)`.
No reference test calls either function directly (`rg` over both suites), so no
ported test changes.

`cli(...)` takes 14 Click-bound parameters (PLR0917, too many positional). Make
every option parameter keyword-only: `def cli(ctx: click.Context, *, dry_run: bool, ...)`.
`click.pass_context` passes `ctx` positionally, and `ctx.invoke` passes options
as keywords, so this needs no suppression comment. PLR0913 is already ignored
for `src/tools/*/cli.py`.

Run `uv run ruff check src/tools/braid tests/tools/braid` before each commit. If
verbatim reference code trips another rule, fix the root cause the same way,
with the smallest change that keeps behavior, and record it in the task report.
Never add a suppression.

### Tests

`tests/tools/braid/conftest.py` holds two autouse fixtures:

- `isolate_braid_environment(monkeypatch, tmp_path)`: `monkeypatch.delenv(name)`
  for every `name` in `os.environ` that starts with `BUVIS_BRAID_`.
  It also sets `BUVIS_CONFIG_DIR` to an empty `tmp_path / "buvis-config"`, so
  `ConfigResolver` never reads the developer's own `buvis-braid.yaml`.
  It also sets `HOME` to `tmp_path / "home"` (the same root the helpers use),
  sets `BUVIS_DEV_MODE=1` (this skips the real auto-update check that
  `buvis_options` runs on every parse; precedent `tests/tools/sysup/conftest.py:19`),
  and calls `monkeypatch.chdir(tmp_path)`. This is needed because
  `ConfigurationLoader` searches `BUVIS_CONFIG_DIR`, `Path.home()/.config/buvis`
  and `Path.cwd()` for `buvis-braid.yaml` (loader.py:174-179, 472-474). Without
  a fake HOME and cwd, a developer's real `kiro_root:` key would flow into
  `select_kiro`, and a CLI test would link into their real Kiro root.
`tests/tools/braid/test_cli.py` (not `conftest.py`, because `braid.cli` does not
exist until Phase 1, and an autouse conftest fixture importing it would break
Phase 0 collection) holds one more autouse fixture:

- `narrow_console(monkeypatch)`: `monkeypatch.setattr(braid_cli.console, "console", Console(width=80, color_system=None))`.
  `braid_cli` is `braid.cli`, which re-exports the `console` adapter it imported.
  The Console has no `file`, so it writes to the current `sys.stdout`, which
  `CliRunner` captures. The width is pinned to the non-TTY default of 80 on
  purpose, so the one-line asserts prove that the CLI does not wrap rather than
  hiding wrapping behind a huge width. Precedent:
  `tests/tools/backup/progress_cli_cases.py:54`.

`tests/tools/braid/helpers.py` holds `make_skill`, `settings`, `kiro_root`,
`enroll`, `write_agent` and `read_state`, verbatim from `tests/test_braid.py`
lines 33-73. The test modules import them as
`from tests.tools.braid.helpers import ...`. Engine names come from
`braid.domain.engine`, and the reference module alias `cli` becomes
`from braid.domain import engine` (so `cli._write_state` becomes
`engine._write_state`, `cli.State` becomes `engine.State`, and
`cli.discover_inventory` becomes `engine.discover_inventory`). The reference
autouse `ignore_ambient_kiro_root` is dropped, because the engine no longer reads
any env.

Port map:

- `test_engine.py`: the 26 `def test_` functions of `tests/test_braid.py` that
  do not call `cli.main`, `cli._parser` or `cli.entrypoint`. These are 31 minus
  the 5 CLI cases: `test_cli_loads_machine_policy_from_agents_root`,
  `test_parser_documents_previously_bare_options_with_help_text`,
  `test_cli_enrolls_kiro_and_reports_the_configured_agent`,
  `test_cli_enrolls_kiro_from_the_environment`,
  `test_cli_rejects_no_kiro_combined_with_enrollment`. Parametrize decorators
  are kept as they are.
- `test_check.py`: 10 of the 13 `def test_` functions in
  `tests/test_braid_check.py`. Dropped:
  `test_a_failed_temp_cleanup_does_not_hide_the_state_write_error` (it tests the
  replaced temp-file code; its two `occupy_*` helpers go with it). Moved to
  `test_cli.py`: `test_cli_reports_a_failed_state_write_on_one_line_and_exits_2`
  and `test_cli_reports_an_unreadable_state_file_on_one_line_and_exits_2`.
  Rewritten:
  `test_a_failed_state_write_reports_a_braid_error_and_leaves_no_temp_file`.
  It still blocks the state path with a directory and expects `BraidError`.
  The temp-file glob assert becomes
  `assert {path.name for path in state_path.parent.iterdir()} == {".braid-state.json", "skills"}`.
  `skills` is the union directory that `run()` legitimately creates before the
  state write. The assert therefore fails on any leftover `atomic_write_text`
  temp (`.braid-state.json.*.tmp`), whatever its name.
- `test_cli.py`: `CliRunner().invoke(cli, [...])` from `braid.cli`. Every
  invocation passes `--agents-root`, `--claude-root` and `--config-root` under
  `tmp_path`, except the two config-root tests. The sources the reference got
  from `_repository_root` are passed as `--source <source>`. Cases:
  - `test_cli_loads_machine_policy_from_agents_root`: exit 0; `"3 change(s)"` in output; symlink and absence asserts as in the reference.
  - `test_cli_enrolls_kiro_and_reports_the_configured_agent`: exit 0, `"1 configured"`, then the same roots plus `--check` exit 0.
  - `test_cli_enrolls_kiro_from_the_environment`: `monkeypatch.setenv("BUVIS_BRAID_KIRO_ROOT", ...)`; the Kiro link exists.
  - `test_cli_rejects_no_kiro_combined_with_enrollment`: `["--no-kiro", "--kiro"]` gives exit 2 and `"--no-kiro cannot be combined with Kiro enrollment options"` in output.
  - `test_cli_reports_a_failed_state_write_on_one_line_and_exits_2`: exit 2. Exactly one output line contains `f"braid: cannot write Braid state {state_path}: "`, and no other line carries the error text.
  - `test_cli_reports_an_unreadable_state_file_on_one_line_and_exits_2`: same shape with `"cannot read Braid state"`, plus the byte-unchanged state file assert.
  - `test_parser_documents_previously_bare_options_with_help_text`: for each of `--policy`, `--agents-root`, `--claude-root`, `--config-root`, `--no-claude`, the option's `help` on `cli.params` (found by `opts`) is a non-empty string. Its help text also appears in `CliRunner().invoke(cli, ["--help"]).output`, compared after whitespace normalization (`" ".join(output.split())`), because Click wraps help.
  - `test_cli_check_exits_1_on_drift`: one skill, fresh roots, `--check` gives exit 1 and `"drift"` in the summary line, and no state file is written.
  - `test_cli_rejects_dry_run_with_check`: `["--dry-run", "--check"]` gives exit 2 and `"--dry-run cannot be combined with --check"`.
  - `test_cli_never_reads_the_old_agent_skills_config`: `monkeypatch.setenv("HOME", str(tmp_path / "home"))`, with a real source listed in `tmp_path/"home"/".config"/"agent-skills"/"sources.d"/"personal"`. There is no `--config-root` and no `--source`. Expect exit 2, an output containing `"no skill sources configured"`, and no `tmp_path/"home"/".agents"/"skills"` created.
  - `test_cli_without_sources_names_the_braid_config_directory`: same `HOME`, nothing configured. Expect exit 2, and `str(tmp_path / "home" / ".config" / "braid" / "sources.d")` in output.
  - `test_cli_reports_an_os_error_after_a_backup_and_exits_2`: put a real directory at `<agents_root>/skills/portable` (a union collision, so `_backup` moves it and emits `BACKUP`). Then `monkeypatch.setattr("braid.domain.engine.create_directory_link", ...)` with a stub that raises `PermissionError("denied")`. Expect exit 2, the `BACKUP ` line in output before the `braid: denied` failure line, and no traceback (`result.exception` is a `SystemExit`).
  - `test_cli_keeps_a_long_report_line_whole_at_80_columns`: a source path padded past 80 characters (a nested dir named `"x" * 90`), sync run with `--no-claude` and `--no-kiro`, so only the union link is made. Exactly one output line starts with `LINK[symlink] `, and it contains both the full destination and the full target path.

## Data flow

```text
argv -> Click (cli) -> option rejections (exit 2)
     -> get_settings(ctx, BraidSettings)  [env BUVIS_BRAID_*, YAML config, defaults]
     -> ComposeRequest (flag or settings, per root)
     -> CommandCompose.execute()
          -> resolve_settings: sources.d + --source -> dedupe -> policy candidates -> engine Settings
          -> run(settings, lines.append)
               discover_inventory -> read_ignored -> _load_state -> select_kiro -> prepare_kiro_agents
               -> _sync_links(union) -> _sync_links(claude) -> _sync_links(kiro) + sync_kiro_agent
               -> _report_orphans (read-only modes) -> MISMATCH STATE check
               -> _write_state (SYNC only, atomic_write_text)
          -> CommandResult(output=lines + summary, error, metadata{drift, exit_code})
     -> cli: console.console.out(line, highlight=False) per line;
             console.console.print(console.format_failure(escape(error)), soft_wrap=True); ctx.exit(code)
```

The state file at `<agents_root>/.braid-state.json` keeps schema version 1. An
existing state written by agent-skills braid is read unchanged.

## Reuse inventory

- `src/lib/buvis/pybase/filesystem/atomic_write.py:atomic_write_text(path, data, *, encoding="utf-8", mode=0o644)`. It replaces `_write_state`'s hand-rolled temp-plus-replace and cleans up its own temp on any failure. Use it for the state file only.
- `buvis.pybase.filesystem.atomic_write_bytes` was considered for the Kiro agent rewrite and rejected. It has no compare step, and the reference re-checks `read_bytes() == before` after writing the temp (PRD says keep it).
- `src/lib/buvis/pybase/result.py:CommandResult(success, output, error, info, warnings, metadata)`, the return type of `CommandCompose.execute`.
- `src/lib/buvis/pybase/configuration/click_integration.py:buvis_options(settings_class=...)` and `get_settings(ctx, cls)`. They add `--version`, `--config`, `--config-dir` and the other standard options, and resolve `BraidSettings`. Use them as in `src/tools/backup/cli.py` and `src/tools/pinger/cli.py`.
- `src/lib/buvis/pybase/configuration/settings.py:GlobalSettings`, the base for `BraidSettings` (pattern: `src/tools/pinger/settings.py`).
- `buvis.pybase.adapters.console` (`print(message, mode="raw")`, `failure`). Raw mode wraps the line in `rich.text.Text`, so markup is not parsed.
- `tests/tools/backup/progress_cli_cases.py:54`, the console swap fixture pattern (`Console(file=..., width=240, color_system=None)`).
- `tests/tools/backup/test_parallel_runner.py:31`, the `from tests.tools.<tool>.<helpers> import` pattern for shared test helpers under importlib mode.
- `tests/conftest.py:34-38`, which auto-applies the `braid` marker by path. Only the `pyproject.toml` marker registration is needed (`strict_markers = true`).
- `tools/lib/check_tool_wiring.py`, which validates the scripts and packages wiring. `tools/lib/scaffold.py` can generate a skeleton, but its generated cli/command/test files do not match the port (group plus example command). Hand-write the files and copy only its wiring order.
- No existing skill-composition, symlink-projection or junction helper exists in gems. Greps tried: `rg -n "symlink|mklink|junction" src/lib src/tools` (the only hits are dot's host-links, which are dotfile-specific and git-backed, so not reusable) and `rg -n "SKILL.md|braidignore|sources.d" src` (nothing). The control grep `rg -n "atomic_write_text" src/lib` proved the pattern works.

## Alternatives considered

1. **Smallest diff: vendor the reference `cli.py` as one module** (`src/tools/braid/engine.py` verbatim, `main()` kept), with a thin Click shim that calls `main(argv)`. This is the fewest lines, but it breaks the gems standards: argparse inside Click, `print` and `sys.exit` outside console and CommandResult, bare temp-file writes, and env names the PRD drops. Rejected.
2. **Chosen: domain/commands/cli split with `model.py`.** The engine and Kiro logic are verbatim. Only `_write_state`, the `emit` default and the `main()` resolution change. The extra size over option 1 buys the gems invariants and a single `BraidError` mapping, and PRD 00116 can add a rules kind beside `engine.py` without touching the CLI.
3. **Two domain files, with kiro.py importing engine lazily inside functions.** This avoids `model.py` but hides a real cycle behind function-level imports, and mypy and readers have to follow them. Rejected for `model.py`, which is one small file.

## Risks & edge cases

- **Report lines are no longer streamed.** They are printed after `run` returns, or after it fails. On a large union this delays output by a fraction of a second. It is acceptable, and the order is preserved.
- **Rich markup.** Report lines go through `Console.out` (no markup) and the error through `escape()`. A path containing `[` cannot break or restyle output.
- **Old env names are silently ignored.** A user with `AGENTS_ROOT` set loses that override. The CHANGELOG entry and `braid.rst` name the `BUVIS_BRAID_*` replacements.
- **Default config root moves to `~/.config/braid`.** PRD 00183 (buvis home) moves this machine's `sources.d`. Until then, `braid` exits 2 with a message naming the new path.
- **Windows.** `create_directory_link` junction fallback and `_points_to` stay verbatim. `_expand_user` handles `~\`. `atomic_write_text` uses `os.replace`, which works on Windows for a file target.
- **Likely next changes:** (a) PRD 00116 rules kind, which adds a second inventory kind; `run()` and `State` are verbatim, so that PRD reshapes them. (b) `--version` output changes from the agent-skills version to the buvis-gems version, and scripts that parse it break (none known). (c) A future `braid` TUI or API would reuse `CommandCompose(ComposeRequest)` unchanged. Nothing here boxes these in.

## Test strategy outline

- Engine parity: 26 + 10 ported tests, unchanged except imports, helpers and the one rewritten state-write assert. They run with `uv run pytest tests/tools/braid/test_engine.py tests/tools/braid/test_check.py`.
- CLI: 13 `CliRunner` cases in `test_cli.py`, covering exit codes 0, 1 and 2, env enrollment, the no-fallback guarantee, and help texts.
- Rendering: `test_cli_keeps_a_long_report_line_whole_at_80_columns` pins the no-wrap contract.
- Wiring: `uv run python tools/lib/check_tool_wiring.py`, and `uv run pytest -m braid --collect-only -q`, which lists only `tests/tools/braid`.
- Gate: `uv run pytest`, `uv run mypy src/lib/ src/tools/`, `uv run ruff check`, and `uv run sphinx-build -W -b html docs/source docs/build/html`. Run all of them with the env from the capsule (`CARGO_HOME=<scratchpad>/cargo-home`, `BUVIS_SKIP_FRONTEND=1`).
- Live smoke: `uv run braid --help`, and `uv run braid --check --source <tmp source> --agents-root <tmp> --claude-root <tmp> --config-root <tmp> --no-kiro`, which exits 1 on a fresh tmp (drift) and 0 after a sync.

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 4, non-blocker 3, question 1
- fixed (blocker): the braid marker was registered too late, so Phase 0 collection failed. Wiring order now set in `### pyproject.toml`.
- fixed (blocker): verbatim `_report_orphans`/`_sync_links` and the 14-param `cli` fail ruff PLR0913/PLR0917. The reviewer suggested inline suppressions, but the aegis `block_suppression_markers` hook refuses them (it fired on this very doc edit). Fixed structurally instead: parameter objects plus a keyword-only `cli`, see `### Ruff gate: parameter objects, no suppressions`.
- fixed (blocker): `console.print(mode="raw")` wraps at 80 columns when stdout is not a TTY. Report lines now go through `console.console.out`, the error through `soft_wrap=True`, and a new 80-column test pins this.
- fixed (blocker): `BUVIS_CONFIG_DIR` alone does not isolate `ConfigResolver` (it also searches HOME and cwd). The fixture now fakes HOME and cwd.
- non-blocker: raw `OSError` from `read_configured_sources`/`read_ignored`/`discover_inventory`/`_sync_links`/`_backup` still escapes as a traceback (reference parity; `entrypoint` caught only `BraidError`). Conflicts with AGENTS.md "never let raw exceptions reach the user". Left for the planner and reviewers to decide. Mapping `OSError` to exit 2 in `execute()` is the cheap fix.
- non-blocker: README.md has four "15" CLI counts (lines 14, 23, 70, 90), and the list at line 70 already omits klyreon and postup. Update all four counts and record the omission rather than silently fixing it.
- non-blocker: CliRunner tests ran the real auto-update check. Adopted anyway (`BUVIS_DEV_MODE=1` in the fixture) because it costs one line.
- question: the resolution move to `resolve_settings` was missing from the deviations list. Added as deviation 3.

dispatch 2 (codex): cardinal-sin 0, blocker 1, non-blocker 2, question 1
- Dispatch note: the first codex run could not read files (`sandbox-exec: sandbox_apply: Operation not permitted`). It reran with the design doc, PRD, reference `cli.py`, `backup/cli.py` and `console.py` inlined into the prompt. That rerun is the dispatch counted here.
- fixed (blocker, in part): the `narrow_console` autouse fixture imported `braid.cli` from `conftest.py`, which breaks Phase 0 collection before `cli.py` exists. Moved into `test_cli.py`. Rejected the other half (wheel packages must land in Phase 0 for `import braid.domain.engine`): `pytest` has `pythonpath = ["src/tools", "src/lib"]`, and the editable install's `.pth` already puts all of `src/tools` on the path (verified by dispatch 1). Neither import needs the wheel mapping.
- fixed (non-blocker, adopted): an `OSError` escaping `execute()` would drop the buffered report lines, including a `BACKUP` for a move that already happened. `execute()` now catches `(BraidError, OSError)` and keeps the lines, and a new CLI test pins it. This also resolves dispatch 1's traceback non-blocker.
- fixed (non-blocker, adopted): `## Data flow` and `## Risks & edge cases` still named the rejected `console.print(raw)`. Made consistent.
- question: does `ctx.exit(code)` survive `buvis_options`? Yes, verified by dispatch 1 against source: the wrapper returns `ctx.invoke(f, ...)` with no exception handler, so `click.exceptions.Exit` reaches Click's `main`, which exits with that code under `CliRunner`. The CLI tests assert exit codes through the fully decorated command.

dispatch 3 (codex): cardinal-sin 0, blocker 0, non-blocker 3, question 1
- Same inline-prompt mode as dispatch 2. `click_integration.py` was added to the inlined files.
- non-blocker: a `KeyboardInterrupt` after `_backup` moves a collision loses the buffered `BACKUP` report. The reference streamed it. The cost is an orphaned backup directory under `<root>/backups/<suffix>/`, which is still on disk and findable. Not fixed now; the upgrade path is `try/finally` rendering in the CLI.
- non-blocker: on Windows, `Path.home()` reads `USERPROFILE`, not `HOME`, so the test fixture does not isolate a Windows run. CI runs Linux and macOS only. Not fixed now; the upgrade path is to also set `USERPROFILE` in `isolate_braid_environment`.
- non-blocker: AGENTS.md § Code Conventions says "Explicit `__all__` in `__init__.py`", and deviation 4 omits it because the peers do. Left for the planner. The cheap fix is an empty `__all__: list[str] = []` in `braid/__init__.py`.
- question (clarified in place): the long-line test said "exactly one `LINK[symlink]` line", but a default sync also projects to Claude. The test now passes `--no-claude --no-kiro`. This is a one-phrase clarification of an obviously wrong count, not a design change.
