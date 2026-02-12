# AGENTS.md

BUVIS gems monorepo. Python toolkit (buvis-pybase + zettel) and CLI tools, shipped as a single PyPI package `buvis-gems`.

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
│   ├── command/                # CLI scaffolding (BuvisCommand)
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
    ├── hello_world/            # sample template
    ├── muc/                    # music collection tools
    ├── outlookctl/             # Outlook CLI
    ├── pinger/                 # ICMP ping utilities
    ├── readerctl/              # Readwise Reader CLI
    └── zseq/                   # Zettelsequence utilities
tests/
├── lib/                        # library tests
│   ├── pybase/
│   ├── zettel/
│   └── zettel_integrations/
└── tools/                      # CLI tool tests
dev/
├── bin/release                 # bump+tag+push
└── pin_deps.py                 # pin deps from uv.lock for publishing
```

**Key patterns:**

- **Single package**: `buvis-gems` on PyPI, one `uv tool install`
- **Namespace package**: `src/lib/buvis/` has no `__init__.py`
- **Hatch packages**: each `src/tools/<name>/` maps to top-level `<name>` in wheel
- **Libraries are internal**: pybase + zettel not published separately

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

**CLI pattern**: Click-based, inheriting from `BuvisCommand`:

```python
@click.command()
@buvis_options
@click.pass_context
def cli(ctx: click.Context) -> None:
    command = MyCommand(ctx.obj["settings"])
    command.execute()
```

## Testing

- pytest + pytest-mock + pytest-cov
- Tests in `tests/` mirror `src/lib/` and `src/tools/` structure
- Mock subprocess calls heavily
- Class-based test organization
- **No unused imports/variables**

## Installation

```bash
uv tool install buvis-gems              # core only (no tool-specific deps)
uv tool install buvis-gems[bim]         # with jira support
uv tool install buvis-gems[all]         # everything
uv tool upgrade buvis-gems              # update
```

Extras: `bim`, `hello-world`, `muc`, `pinger`, `readerctl`, `ml`, `all`

## Release

```bash
release patch|minor|major    # bump, tag, push → CI publishes to PyPI (mise adds dev/bin to PATH)
```
