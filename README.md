# buvis-gems

BUVIS Python toolkit and CLI tools, shipped as a single PyPI package.

## Install

```bash
uv tool install buvis-gems              # core CLIs (dot, fctracker, outlookctl, zseq)
uv tool install buvis-gems[bim]         # + jira dep for bim
uv tool install buvis-gems[bim,muc]     # combine extras
uv tool install buvis-gems[all]         # everything
```

The base install includes all 9 CLIs (`bim`, `dot`, `fctracker`, `hello-world`, `muc`, `outlookctl`, `pinger`, `readerctl`, `zseq`) but some tools need extra dependencies to work:

| Extra | Dep | Tool |
|-------|-----|------|
| `bim` | jira | bim |
| `hello-world` | pyfiglet | hello-world |
| `muc` | ffmpeg-python | muc |
| `pinger` | ping3 | pinger |
| `readerctl` | requests | readerctl |
| `ml` | torch, transformers, rake-nltk | tag suggester |
| `all` | all of the above | — |

## What's inside

**Library** (`src/lib/buvis/pybase/`) — shared adapters, CLI scaffolding, configuration, filesystem and formatting utilities, plus the zettel subsystem (domain logic and Jira integration).

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
release patch|minor|major    # bump version, tag, push -> CI publishes to PyPI
```
