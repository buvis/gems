# buvis-gems

BUVIS Python toolkit and CLI tools, shipped as a single PyPI package.

[Documentation](https://buvis.github.io/gems/)

## Install

```bash
uv tool install buvis-gems              # all 9 CLIs, no optional deps
uv tool install buvis-gems[bim]         # + jira & textual deps for bim
uv tool install buvis-gems[bim,muc]     # combine extras
uv tool install buvis-gems[all]         # all optional deps
```

All 9 CLIs (`bim`, `dot`, `fctracker`, `hello-world`, `muc`, `outlookctl`, `pinger`, `readerctl`, `zseq`) are always installed. Extras add optional dependencies some tools need:

| Extra | Dep | Tool |
|-------|-----|------|
| `bim` | jira, textual, fpdf2 | bim |
| `bim-web` | fastapi, uvicorn, watchfiles | bim (web UI) |
| `hello-world` | pyfiglet | hello-world |
| `muc` | ffmpeg-python | muc |
| `pinger` | ping3 | pinger |
| `readerctl` | requests | readerctl |
| `all` | all of the above | — |

## What's inside

**Library** (`src/lib/buvis/pybase/`) — shared adapters, CLI scaffolding, configuration, filesystem and formatting utilities, plus the zettel subsystem (domain logic, Jira integration, and a Rust extension via PyO3 for performance-critical parsing).

**Tools** (`src/tools/`) — 9 Click-based CLIs built on the library:

| Tool | Purpose |
|------|---------|
| bim | BUVIS InfoMesh (zettel integration) |
| dot | Dotfiles manager |
| fctracker | Foreign currency account tracker |
| hello_world | Sample script template |
| muc | Music collection tools |
| outlookctl | Outlook CLI |
| pinger | ICMP ping utilities |
| readerctl | Readwise Reader CLI |
| zseq | Zettelsequence utilities |

## Development

```bash
uv sync --all-groups --all-extras
pre-commit install
uv run pytest
uv run mypy src/lib/ src/tools/
```

## Release

```bash
release patch|minor|major              # bump, tag, push -> CI publishes to PyPI
release --pre rc1                      # pre-release current version to TestPyPI
release --pre rc1 minor                # bump + pre-release to TestPyPI
release                                # after rc: strip suffix, release stable to PyPI
```
