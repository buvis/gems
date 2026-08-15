# AGENTS.md

BUVIS gems monorepo. Python toolkit (buvis-pybase + zettel) and CLI tools, shipped as a single PyPI package `buvis-gems`. Supports Python 3.11+.

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
    ├── hello_world/            # sample template
    ├── morph/                  # file conversion toolkit
    ├── muc/                    # music collection tools
    ├── netscan/                # network scanning tools
    ├── outlookctl/             # Outlook CLI
    ├── pidash/                 # autopilot progress dashboard (TUI)
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
dev/
└── bin/
    ├── pin_deps.py             # pin deps from uv.lock for publishing
    ├── release                 # bump+tag+push
    └── scaffold.py             # scaffold a new tool
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
- Never let raw exceptions (stack traces) reach the user.

## Invariants (evolution guardrails)

These encode the failure classes surfaced by the 2026-07-09 evolution assessment (`dev/local/audit-results/evolution-assessment-2026-07-09.md`). Each is either **HOLDS** (enforce it) or a **GAP** (a tracked PRD is closing it — write new code to the target state, not the current one).

- **Atomic persistence** — never persist a note, state file, or config with a bare `Path.write_text`/`open(...,"w")`. Use `pybase.filesystem.atomic_write` (tempfile + fsync + `os.replace`). Truncate-then-write loses data on crash/ENOSPC. *HOLDS for the library and note/updater write paths (00041) — keep it. GAP → pidash (00049/00071).*
- **Confine request-derived paths** — any filesystem path built from an HTTP request / external input must be `resolve()`d and asserted under an allowed root before read/write/delete/open. Network-facing servers must have auth + `TrustedHostMiddleware`. *GAP → 00042 (bim serve).*
- **The library stays interface-agnostic** — `src/lib/buvis/pybase/` must not import a UI framework at module import time or emit output outside the console adapter. No import-time Click monkey-patching, no `sys.exit`/`click.echo`/`print` in lib code. A TUI/API/WebUI process must be able to `import` settings without pulling Click. *GAP → 00052.*
- **One action, one implementation across interfaces** — CLI/TUI/API/WebUI adapters must drive the same command class / use case through the composition root and return `CommandResult`; do not reimplement business logic per interface (dot's TUI is the anti-pattern; bim's serve action registry is the exemplar). *GAP → 00051 design doc, then 00053/00054.*
- **Claim/lifecycle release on any exit** — resource claims and locks release in `finally` (or catch `BaseException`), never only `except Exception`; `KeyboardInterrupt` must not leak a claim. *GAP → 00044.*
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

Extras: `bim`, `bim-web`, `doc`, `dot`, `fren`, `hello-world`, `morph`, `muc`, `pinger`, `readerctl`, `all`

## Release

```bash
release patch|minor|major              # bump, tag, push → CI publishes to PyPI
release --pre rc1                      # pre-release current version to TestPyPI
release --pre rc1 minor                # bump + pre-release to TestPyPI
release                                # after rc: strip suffix, release stable to PyPI
release local                          # build .devN wheel + install locally
release --dry-run [--pre rc1] [patch]  # preview without changes
```

`mise` adds `dev/bin` to PATH. Tags with `rc` in the name publish to TestPyPI; stable tags go to PyPI. Manual workflow dispatch defaults to TestPyPI.

**First-time setup** (already done for buvis-gems):
- test.pypi.org: add trusted publisher (owner: `buvis`, repo: `gems`, workflow: `publish.yml`, env: `testpypi`)
- GitHub repo settings: create `testpypi` and `pypi` environments

**Why explicit version in pyproject.toml?** maturin reads the version from `pyproject.toml` at build time to compile the Rust extension. Tag-based versioning (hatch-vcs) would require glue to inject the version before maturin sees it. Pure Python projects like mkdocs-zettelkasten use hatch-vcs instead — the version derives from the git tag, no file to keep in sync, no bump commits.
