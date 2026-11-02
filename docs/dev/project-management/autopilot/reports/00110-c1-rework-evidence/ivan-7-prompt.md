
You are Ivan, the implementor. Make all failing tests pass. Tests ARE the
spec. Do NOT modify test files unless your allowlist below names them (a
test-only task lists them on purpose). Do NOT read the task's acceptance criteria —
none are provided to you on purpose.

## Failing tests

from __future__ import annotations

import tarfile
from typing import TYPE_CHECKING

import pytest
from buvis.pybase.result import FatalError

from backup.capabilities.tar_archive import TarArchive
from backup.config import BackupConfig
from backup.runner import Runner

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

    from backup.step_result import PlanEntry, StepResult


def _source(root: Path, name: str) -> Path:
    source = root / name
    source.mkdir(parents=True)
    (source / "tiny.txt").write_bytes(name.encode())
    (source / "tiny.txt-copy").write_bytes(f"{name}-copy".encode())
    return source


def _invoke(interface: str, mode: str, values: dict[str, object]) -> list[PlanEntry | StepResult]:
    if interface == "capability":
        archive = TarArchive()
        if mode == "plan":
            return [archive.plan(label="selected", **values)]
        return list(archive.run(label="selected", dry_run=mode == "dry-run", **values))
    cfg = BackupConfig.model_validate({"instances": {"selected": {"use": "tar-archive", "with": values}}})
    runner = Runner(cfg, dry_run=mode == "dry-run")
    selected = list(cfg.instances.items())
    return runner.plan(selected) if mode == "plan" else list(runner.run(selected))


def _assert_archive(out: Path, name: str) -> None:
    with tarfile.open(out, "r:gz") as archive:
        files = {member.name for member in archive.getmembers() if member.isfile()}
        assert files == {f"{name}/tiny.txt", f"{name}/tiny.txt-copy"}
        for filename, payload in (("tiny.txt", name), ("tiny.txt-copy", f"{name}-copy")):
            member = archive.extractfile(f"{name}/{filename}")
            assert member is not None
            assert member.read() == payload.encode()


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None for path in root.rglob("*")}


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize("name", ["notes", "photos"])
def test_empty_engine_matches_omitted_python_engine(tmp_path: Path, interface: str, mode: str, name: str) -> None:
    source = _source(tmp_path / "sources", name)
    out = tmp_path / "archives" / f"{name}.tar.gz"
    values = {"source": str(source), "out": str(out)}
    omitted = _invoke(interface, "plan", values)
    results = _invoke(interface, mode, {**values, "engine": ""})

    assert len(omitted) == len(results) == 1
    assert omitted[0].status == "run"
    result = results[0]
    assert result.label == "selected"
    if mode == "plan":
        assert result == omitted[0]
        assert result.source == str(source)
        assert result.out == str(out)
        assert result.replaces is False
    else:
        assert result.success is True
        assert result.skipped is False
        assert result.out_path == str(out)
    assert out.exists() is (mode == "run")
    assert out.parent.exists() is (mode == "run")
    if mode == "run":
        _assert_archive(out, name)
    assert (source / "tiny.txt").read_bytes() == name.encode()
    assert (source / "tiny.txt-copy").read_bytes() == f"{name}-copy".encode()


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize(("key", "message"), [("source", "no source configured"), ("out", "no out path configured")])
@pytest.mark.parametrize("existing", [False, True])
def test_empty_paths_fail_without_using_cwd_or_changing_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interface: str, mode: str, key: str, message: str, existing: bool
) -> None:
    source = _source(tmp_path / "sources", "notes")
    cwd = _source(tmp_path, "working")
    monkeypatch.chdir(cwd)
    out = tmp_path / "archives" / "notes.tar.gz"
    if existing:
        out.parent.mkdir()
        out.write_bytes(b"keep existing archive")
    values = {"source": str(source), "out": str(out), key: ""}
    before = _snapshot(tmp_path)

    results = _invoke(interface, mode, values)

    assert len(results) == 1
    result = results[0]
    assert result.label == "selected"
    if mode == "plan":
        assert result.status == "fail"
        assert result.reason == message
        if key == "out":
            assert result.out == ""
            assert result.replaces is False
    else:
        assert result.success is False
        assert result.skipped is False
        assert result.message == message
    assert _snapshot(tmp_path) == before


def _mixed_config(tmp_path: Path) -> tuple[BackupConfig, Path]:
    shared = tmp_path / "shared.tar.gz"
    shared.write_bytes(b"preserve duplicate archive")
    values = {}
    for name in ("empty", "empty-copy", "missing", "missing-copy", "same", "same-copy", "notes", "notes-copy"):
        source = _source(tmp_path / "sources", name)
        out = str(tmp_path / "outputs" / f"{name}.tar.gz")
        if name in {"empty", "empty-copy"}:
            out = ""
        elif name in {"same", "same-copy"}:
            out = str(shared)
        values[name] = {"source": "" if name in {"missing", "missing-copy"} else str(source), "out": out}
    cfg = BackupConfig.model_validate(
        {"instances": {name: {"use": "tar-archive", "with": value} for name, value in values.items()}}
    )
    return cfg, shared


@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
def test_runner_keeps_missing_inputs_distinct_from_collisions_and_executes_independent_instances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    cfg, shared = _mixed_config(tmp_path)
    cwd = _source(tmp_path, "working")
    before_cwd = _snapshot(cwd)
    monkeypatch.chdir(cwd)
    runner = Runner(cfg, dry_run=mode == "dry-run")
    selected = list(cfg.instances.items())

    results = runner.plan(selected) if mode == "plan" else list(runner.run(selected))

    assert [result.label for result in results] == list(cfg.instances)
    for result in results:
        name = result.label
        if name in {"notes", "notes-copy"}:
            assert result.status == "run" if mode == "plan" else result.success is True
            out = tmp_path / "outputs" / f"{name}.tar.gz"
            assert out.exists() is (mode == "run")
            if mode == "run":
                _assert_archive(out, name)
            continue
        message = "no out path configured" if name in {"empty", "empty-copy"} else "no source configured"
        if name in {"same", "same-copy"}:
            other = "same-copy" if name == "same" else "same"
            message = f"output '{shared}' is also the output of '{other}'"
        assert result.status == "fail" if mode == "plan" else result.success is False
        assert (result.reason if mode == "plan" else result.message) == message
    expected = {shared}
    if mode == "run":
        expected |= {tmp_path / "outputs" / f"{name}.tar.gz" for name in ("notes", "notes-copy")}
    assert set(tmp_path.rglob("*.tar.gz")) == expected
    assert shared.read_bytes() == b"preserve duplicate archive"
    assert _snapshot(cwd) == before_cwd
    assert (tmp_path / "outputs").exists() is (mode == "run")


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
@pytest.mark.parametrize("engine", ["python-tarfile-copy", "copy-python-tarfile"])
def test_engine_lookalikes_remain_rejected_without_archive_effects(
    tmp_path: Path, interface: str, mode: str, engine: str
) -> None:
    source = _source(tmp_path / "sources", "photos")
    out = tmp_path / "archives" / "photos.tar.gz"
    out.parent.mkdir()
    out.write_bytes(b"preserve rejected engine archive")
    before = _snapshot(tmp_path)

    results = _invoke(interface, mode, {"source": str(source), "out": str(out), "engine": engine})

    assert len(results) == 1
    assert results[0].label == "selected"
    assert results[0].status == "fail" if mode == "plan" else results[0].success is False
    message = results[0].reason if mode == "plan" else results[0].message
    assert f"unknown engine '{engine}'" in message
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("interface", ["capability", "runner"])
@pytest.mark.parametrize("message", ["archive storage unavailable", "archive permission denied"])
def test_fatal_archive_errors_propagate_with_empty_default_engine(
    tmp_path: Path, mocker: MockerFixture, interface: str, message: str
) -> None:
    source = _source(tmp_path / "sources", "notes")
    out = tmp_path / "notes.tar.gz"
    mocker.patch("tarfile.open", autospec=True, side_effect=FatalError(message))

    with pytest.raises(FatalError, match=message):
        _invoke(interface, "run", {"source": str(source), "out": str(out), "engine": ""})

    assert not out.exists()
    assert (source / "tiny.txt").read_bytes() == b"notes"
    assert (source / "tiny.txt-copy").read_bytes() == b"notes-copy"


@pytest.mark.parametrize("mode", ["plan", "run", "dry-run"])
def test_runner_empty_selection_has_no_archive_effects(tmp_path: Path, mode: str) -> None:
    source = _source(tmp_path / "sources", "unselected")
    cfg = BackupConfig.model_validate(
        {"instances": {"unselected": {"use": "tar-archive", "with": {"source": str(source), "out": ""}}}}
    )
    before = _snapshot(tmp_path)
    runner = Runner(cfg, dry_run=mode == "dry-run")

    results = runner.plan([]) if mode == "plan" else list(runner.run([]))

    assert results == []
    assert _snapshot(tmp_path) == before


## Architecture context

# AGENTS.md

BUVIS gems monorepo. Python toolkit (buvis-pybase + zettel) and CLI tools, shipped as a single PyPI package `buvis-gems`. Supports Python 3.11+.

## Reading these instructions

This root `AGENTS.md` is the always-on canonical guidance. Some directories also
carry their own nested `AGENTS.md` with rules scoped to the code beside them.
Before working on files in a directory, discover and read any `AGENTS.md` on the
path from the repo root down to that directory, and follow it for files in its
scope. Do this yourself even if your host did not load those files automatically
— host loading of nested files varies and is not guaranteed (see
[`docs/dev/architecture/agent-host-support.md`](docs/dev/architecture/agent-host-support.md)).

## Quick Start

```bash
uv sync --all-groups --all-extras            # install deps
pre-commit install                          # setup hooks
uv run pytest                               # run tests
uv run pytest -m snapshot                   # run snapshot tests only (skipped off canonical env)
uv run pytest --snapshot-update             # regenerate snapshot baselines (local use only)
uv run mypy src/lib/ src/tools/              # type check
uv run sphinx-build -b html docs/source docs/build/html  # build docs
```

## Architecture

```text
src/
├── lib/buvis/pybase/           # shared library (namespace pkg: no buvis/__init__.py)
│   ├── adapters/               # jira, console, config adapters
│   ├── configuration/          # settings/config helpers
│   ├── filesystem/             # file utilities
│   ├── formatting/             # output formatting
│   └── zettel/                 # zettel subsystem
│       ├── domain/             # entities, services, interfaces, value objects
│       ├── application/        # use cases
│       ├── infrastructure/     # formatters, repositories, file parsers
│       └── integrations/       # jira assemblers
└── tools/
    ├── bim/                    # BUVIS InfoMesh CLI (zettel integration)
    ├── dot/                    # dotfiles manager
    ├── fctracker/              # foreign currency tracker
    ├── fren/                   # file renamer toolkit
    ├── morph/                  # file conversion toolkit
    ├── muc/                    # music collection tools
    ├── netscan/                # network scanning tools
    ├── outlookctl/             # Outlook CLI
    ├── pinger/                 # ICMP ping utilities
    ├── puc/                    # photo utility collection
    ├── readerctl/              # Readwise Reader CLI
    ├── sysup/                  # system update tools
    ├── vuc/                    # video utility collection
    └── zseq/                   # Zettelsequence utilities
tests/
├── lib/                        # library tests
│   ├── pybase/
│   ├── zettel/
│   └── zettel_integrations/
└── tools/                      # CLI tool tests
tools/                          # Dev command shims (on PATH via mise) + helpers
├── release                     # public shim → mise `release` task
└── lib/                        # helpers, invoked by path (NOT on PATH)
    ├── release                 # release impl: bump+tag+push
    ├── pin_deps.py             # pin deps from uv.lock for publishing
    ├── scaffold.py             # scaffold a new tool
    ├── check_audit_ignores.py  # pip-audit suppression guard (+ audit/ config)
    ├── check_tool_wiring.py    # pre-commit tool-wiring check
    ├── parity_brief_portfolio.py
    └── gen_zettel_writer_fixtures.py
```

**Key patterns:**

- **Single package**: `buvis-gems` on PyPI, one `uv tool install`
- **Namespace package**: `src/lib/buvis/` has no `__init__.py`
- **Hatch packages**: each `src/tools/<name>/` maps to top-level `<name>` in wheel
- **Libraries are internal**: pybase + zettel not published separately
- **All-interface rule**: every command/action must work across CLI, TUI, API, and WebUI

## Tool Structure

Every tool under `src/tools/<name>/` follows a base layout:

```text
tool_name/
├── __init__.py
├── __main__.py
├── cli.py              # Click entry point
├── settings.py         # Tool-specific settings
└── commands/           # One module per CLI command
```

Add subdirs only when needed:

| Dir | When | Example |
|-----|------|---------|
| `adapters/` | External service clients | fctracker, readerctl |
| `domain/` | Business logic beyond simple commands | fctracker |
| `shared/` | Code reused across commands | zseq |

> `bim/commands/serve/frontend/` contains the WebUI SvelteKit app — the only tool with a frontend subtree.

> `bim/commands/doc/` follows the existing `commands/serve/`-style group pattern with a `shared/` subdir holding cross-command utilities (pipeline, OCR/classifier/extractor adapters, state DB, issuer registry, zettel writer).

## Code Conventions

**Type hints** — modern style, no `Optional`:

```python
from __future__ import annotations
def foo(path: Path | None = None) -> list[str]: ...
```

**Imports**:

- Explicit `__all__` in `__init__.py`
- `TYPE_CHECKING` guards for type-only imports

**Docstrings**: Google format

**CLI pattern**: Click-based. `buvis_options` adds `--version`, `--config`, `--log-level`, `--debug`, and `--update` to every tool automatically:

```python
@click.command()
@buvis_options
@click.pass_context
def cli(ctx: click.Context) -> None:
    settings = get_settings(ctx)
    ...
```

**Lazy imports in CLI handlers**: import command classes inside handler functions, not at module level. This avoids pulling in optional/heavy dependencies before the user picks a subcommand:

```python
@cli.command("create")
@click.pass_context
def create(ctx):
    from bim.commands.create_note.create_note import CommandCreateNote
    ...
```

## Error Handling

**Command layer** (`commands/`):
- Return `CommandResult` for all outcomes — success and failure
- Catch expected exceptions (e.g. `FileNotFoundError`) internally, return `CommandResult(success=False, error=str(exc))`
- No `console.panic()` or `sys.exit()` inside command classes
- No custom exception classes for control flow

**CLI layer** (`cli.py`):
- Inspect `CommandResult` and call `console.panic()` / `console.failure()` / `console.success()`
- Use `console.report_result()` for standardized output
- Catch `ImportError` for optional deps, call `console.require_import()`
- Catch `FatalError` for unrecoverable infrastructure failures

**Click argument validation**:
- Avoid parse-time validators that short-circuit before the callback (`click.Path(exists=True)`, `IntRange`, custom `ParamType.convert` that raises). They emit Click's default `Usage: ... Error: ...` formatting and bypass the buvis console.
- Validate inside the callback instead: `if not path.is_file(): console.panic(f"file not found: {path}"); return`.
- `click.Choice` is the exception — its parse-time error lists the valid values, which is more useful than a rewritten message.

**Console methods**:
- Fatal (exit): `console.panic(msg)` — prints + exits with code 1
- Recoverable: `console.failure(msg)` — prints, continues
- Status: `console.success()`, `console.warning()`, `console.info()`
- All user-facing output must route through `console`. No `print()`, `sys.stdout.write()`, `sys.stderr.write()`, `click.echo()`, `click.secho()`, or the Python logging module. Plain writes bypass the buvis prefix markers (`✘`, `✓`, etc.) and become indistinguishable from stray output, which is what makes a missed `console.panic` look like a print statement to the user.
- The one sanctioned exception is the `dot filter` clean/smudge plumbing, which writes git's blob payload as raw bytes on stdout and at most one error line on stderr, because git owns both streams and a console marker would corrupt the payload (discovery R12).
- Never let raw exceptions (stack traces) reach the user.

## Invariants (evolution guardrails)

These encode the failure classes surfaced by the 2026-07-09 evolution assessment (`docs/dev/project-management/reviews/evolution-assessment-2026-07-09.md`). Each is either **HOLDS** (enforce it) or a **GAP** (a tracked PRD is closing it — write new code to the target state, not the current one).

- **Atomic persistence** — never persist a note, state file, or config with a bare `Path.write_text`/`open(...,"w")`. Use `pybase.filesystem.atomic_write` (tempfile + fsync + `os.replace`). Truncate-then-write loses data on crash/ENOSPC. *HOLDS for the library and note/updater write paths (00041) — keep it, except `ConfigWriter.write` (`configuration/config_writer.py`), which still does a bare `write_text` — deliberately out of scope for 00041. GAP → pidash was closed by retiring pidash (00071); autopilot-state durability now lives in the buvis home repo (tracon/statectl), not gems.*
- **Confine request-derived paths** — any filesystem path built from an HTTP request / external input must be `resolve()`d and asserted under an allowed root before read/write/delete/open. Network-facing servers must have auth + `TrustedHostMiddleware`. *HOLDS (00042) — bim serve confines request paths via `confine_path` (403 outside the vault/archive roots), mints a startup token required as `X-Buvis-Token`, installs `TrustedHostMiddleware`, and warns on a non-loopback bind (`commands/serve/_security.py`). Keep it.*
- **The library stays interface-agnostic** — `src/lib/buvis/pybase/` must not import a UI framework at module import time or emit output outside the console adapter. No import-time Click monkey-patching, no `sys.exit`/`click.echo`/`print` in lib code. A TUI/API/WebUI process must be able to `import` settings without pulling Click. *HOLDS (00052) — keep it.*
- **One action, one implementation across interfaces** — CLI/TUI/API/WebUI adapters must drive the same command class / use case through the composition root and return `CommandResult`; do not reimplement business logic per interface (dot's TUI is the anti-pattern; bim's serve action registry is the exemplar). *HOLDS (00051 design → 00053/00054) — the all-interface seam design (00051) is realized: dot's git ops unified behind `DotGitService` (00053) and bim's serve/TUI converged on the shared action registry (00054). Keep it.*
- **Claim/lifecycle release on any exit** — resource claims and locks release in `finally` (or catch `BaseException`), never only `except Exception`; `KeyboardInterrupt` must not leak a claim. *HOLDS (00044) — the bim doc claim/dedup pipeline releases claims and locks in `finally` (`commands/doc/shared/`); keep it.*
- **`CommandResult` discipline** — commands return `CommandResult`; the CLI/adapter layer renders it (`console.report_result`) and maps exit/HTTP status. No `sys.exit`/`console.panic` inside command classes. *HOLDS in `src/tools/*/commands/**` — keep it.*
- **Clean-architecture layering + tool isolation** — zettel `domain → application → infrastructure → integrations` one-directional; no cross-tool imports; no `src/lib → src/tools`. *HOLDS — keep it.*

## Testing

- pytest + pytest-mock + pytest-cov
- Tests in `tests/` mirror `src/lib/` and `src/tools/` structure
- Mock subprocess calls heavily
- Class-based test organization
- **No unused imports/variables**
- **Markers**: `pytest -m <tool>` runs one tool, `pytest -m lib` runs library tests, `pytest -m "not bim"` excludes a tool. Auto-applied by path in `tests/conftest.py` — no decorators needed. Scaffold registers markers for new tools.
- **Snapshot tests** (`@pytest.mark.snapshot`) only run on the canonical env (Linux + Python 3.12) — SVG output from Rich/Textual differs across OS/Python so baselines must come from one place. Anywhere else they are auto-skipped. To regenerate baselines run the `update-snapshots` GitHub workflow (`gh workflow run update-snapshots.yml`); it runs `pytest --snapshot-update` on the canonical env and commits the result. Force locally with `BUVIS_SNAPSHOT_CANONICAL=1` only if you know what you're doing.

## Installation

```bash
uv tool install buvis-gems              # core only (no tool-specific deps)
uv tool install buvis-gems[bim]         # with jira support
uv tool install buvis-gems[bim-web]     # bim web UI deps
uv tool install buvis-gems[all]         # everything
uv tool upgrade buvis-gems              # update
```

Extras: `bim`, `bim-web`, `doc`, `dot`, `fren`, `morph`, `muc`, `pinger`, `postup`, `postup-web`, `readerctl`, `all`

## Release

> Full procedure (version authority, checks, destinations, partial-failure recovery): `docs/dev/procedures/releasing.md`.

```bash
release patch|minor|major              # bump, tag, push → CI publishes to PyPI
release --pre rc1                      # pre-release current version to TestPyPI
release --pre rc1 minor                # bump + pre-release to TestPyPI
release                                # after rc: strip suffix, release stable to PyPI
release local                          # build .devN wheel + install locally
release --dry-run [--pre rc1] [patch]  # preview without changes
```

`mise` adds `tools` to PATH (shims; `tools/lib` holds the implementations). Tags with `rc` in the name publish to TestPyPI; stable tags go to PyPI. Manual workflow dispatch defaults to TestPyPI.

**First-time setup** (already done for buvis-gems):
- test.pypi.org: add trusted publisher (owner: `buvis`, repo: `gems`, workflow: `publish.yml`, env: `testpypi`)
- GitHub repo settings: create `testpypi` and `pypi` environments

**Why explicit version in pyproject.toml?** maturin reads the version from `pyproject.toml` at build time to compile the Rust extension. Tag-based versioning (hatch-vcs) would require glue to inject the version before maturin sees it. Pure Python projects like mkdocs-zettelkasten use hatch-vcs instead — the version derives from the git tag, no file to keep in sync, no bump commits.

Task 7 scope: restore consistent plan/run input semantics exercised by the supplied regressions. The review also requires removing repeated label/engine parsing in TarArchive._run_validated; pass already parsed values instead. Keep source/out/now setup shared or otherwise consistent; do not apply the discarded broad validator refactor. The Runner change is authorized only as required to preserve missing-out diagnostics for two instances with empty output configuration instead of inventing a '.' collision. Preserve all task 6 fixes. Update the Fixed changelog for restored empty-engine and empty-path behavior. Test files stay read-only. No commits or state changes; orchestrator handles those.
Read /Users/bob/.claude/AGENTS.md and repo AGENTS.md. Routine reversible work is authorized.


## Files you may read and modify

/Users/bob/git/src/github.com/buvis/gems/src/tools/backup/capabilities/tar_archive.py
/Users/bob/git/src/github.com/buvis/gems/src/tools/backup/runner.py
/Users/bob/git/src/github.com/buvis/gems/CHANGELOG.md


Read only the files listed above. If a file or symbol you need is not
listed, stop and report it as a blocker — do not run broad `rg` sweeps to
discover scope.



### Code quality rules (mandatory)

Follow these four rules. They override any instinct to "improve" the code
beyond what the failing tests require.

**1. Think before coding.** Re-read the task and the failing tests. If scope,
data shape, target file, or success criteria are ambiguous - more than one
reasonable implementation would pass the tests differently - STOP and report
the ambiguity as a blocker. Do not guess and proceed.

**2. Simplicity.** Write the simplest code that makes the failing tests pass.

- No abstractions, helpers, or interfaces built for a single caller.
- No error handling, fallbacks, or validation for inputs the tests never
  exercise. Validate at real system boundaries only.
- No features, options, or configuration the task did not ask for.
- If your draft runs long and the same behavior fits in far fewer lines,
  rewrite it before returning.

**3. Surgical changes.** Touch only what the task requires.

- Do not refactor, reformat, or "improve" code outside the change.
- Match the surrounding style even if you would write it differently.
- Remove imports, variables, and functions that YOUR change orphaned. Do not
  delete pre-existing dead code - mention it instead.
- Every changed line must trace to the task or a failing test.

**4. Goal-driven.** The failing tests are the spec. Make them pass - do not
modify them, do not weaken them, do not add tests. If a test looks wrong,
report it as a blocker rather than changing it.

Abort and report if you read more than 100K of total input. Return the
partial result and an abort_reason: context_overrun field.

Read every file before your first Edit to it. Never call bash `head`,
`tail`, `cat`, `grep`, or `find` - a hook blocks them. Use the Read tool
(offset/limit), `rg`, or `rg --files` instead. Never combine an inspection
(read, list, search, diff) with a test, lint or build invocation in one Bash
call - run them as two calls, because a combined command has two ways to hang
and one exit code. Pass an explicit `timeout` on every Bash call: 60000 ms for
an inspection, 300000 ms for a lint run or a narrow test run, 600000 ms for a
full suite or a full build.

Run only the test files this task names (the tests you wrote, or the
failing tests in your prompt), with `-q --tb=line`. Never run a whole test
directory or `dev/bin/release-checks`: the orchestrator runs the full suite
once, after every task. Read the pass count and exit code from that one
run; never re-run a suite to recover a number.

End your report with `ASSUMPTIONS:` - one line per assumption you made
where the task, tests, or listed files were silent (guessed interface, data
shape, resolved ambiguity, unstated behavior). Write `ASSUMPTIONS: none` if
you made none.

Also end your report with `FILES_TOUCHED:` - one line per file you created
or modified, path relative to the repo root. Write `FILES_TOUCHED: none` if
you changed no files.
