# buvis-gems

BUVIS Python toolkit and CLI tools, shipped as a single PyPI package.

[Documentation](https://buvis.github.io/gems/)

## Install

Pre-built wheels for Linux (x64, ARM), macOS (ARM), and Windows (x64). Python 3.10+.

### uv

```bash
uv tool install buvis-gems              # all 9 CLIs, no optional deps
uv tool install buvis-gems[bim]         # + jira & textual deps for bim
uv tool install buvis-gems[bim,muc]     # combine extras
uv tool install buvis-gems[all]         # all optional deps
```

### pipx

```bash
pipx install buvis-gems                 # all 9 CLIs, no optional deps
pipx install 'buvis-gems[all]'          # all optional deps
```

### mise

mise's experimental `uvtool` backend doesn't support extras. Use the `pipx` backend instead.

In `~/.config/mise/config.toml`:

```toml
[tools]
"pipx:buvis-gems" = { version = "latest", extras = "all" }
```

Then run `mise install`.

## Update

### uv

```bash
uv tool upgrade buvis-gems
```

### pipx

```bash
pipx upgrade buvis-gems
```

### mise

```bash
mise upgrade pipx:buvis-gems
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

