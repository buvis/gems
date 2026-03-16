# AGENTS.md

BUVIS gems monorepo. Python toolkit (buvis-pybase + zettel) and CLI tools, shipped as a single PyPI package `buvis-gems`. Supports Python 3.10+.

## Quick Start

```bash
uv sync --all-groups --all-extras            # install deps
pre-commit install                          # setup hooks
uv run pytest                               # run tests
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

**CLI pattern**: Click-based:

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

**Console methods**:
- Fatal (exit): `console.panic(msg)` — prints + exits with code 1
- Recoverable: `console.failure(msg)` — prints, continues
- Status: `console.success()`, `console.warning()`, `console.info()`
- Never let raw exceptions (stack traces) reach the user
- Do NOT use Python logging module in CLI tools; use `buvis.pybase.adapters.console`

## Testing

- pytest + pytest-mock + pytest-cov
- Tests in `tests/` mirror `src/lib/` and `src/tools/` structure
- Mock subprocess calls heavily
- Class-based test organization
- **No unused imports/variables**
- **Markers**: `pytest -m <tool>` runs one tool, `pytest -m lib` runs library tests, `pytest -m "not bim"` excludes a tool. Auto-applied by path in `tests/conftest.py` — no decorators needed. Scaffold registers markers for new tools.

## Installation

```bash
uv tool install buvis-gems              # core only (no tool-specific deps)
uv tool install buvis-gems[bim]         # with jira support
uv tool install buvis-gems[bim-web]     # bim web UI deps
uv tool install buvis-gems[all]         # everything
uv tool upgrade buvis-gems              # update
```

Extras: `bim`, `bim-web`, `fren`, `hello-world`, `morph`, `muc`, `pinger`, `readerctl`, `all`

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
