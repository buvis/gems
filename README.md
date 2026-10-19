# buvis-gems

BUVIS Python toolkit and CLI tools, shipped as a single PyPI package.

[Documentation](https://buvis.github.io/gems/)

## Install

Pre-built wheels for Linux (x64, ARM), macOS (ARM), and Windows (x64). Python 3.11+.

### uv

```bash
uv tool install buvis-gems              # all 15 CLIs, no optional deps
uv tool install buvis-gems[bim]         # + jira & textual deps for bim
uv tool install buvis-gems[bim,muc]     # combine extras
uv tool install buvis-gems[all]         # all optional deps
```

### pipx

```bash
pipx install buvis-gems                 # all 15 CLIs, no optional deps
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

Any tool accepts `--update` to ask your installer's own index (mise, uv or pip; PyPI for pipx) for a newer release and upgrade to it:

```bash
dot --update
```

This prints `buvis-gems X.Y.Z is up to date.` or streams the installer upgrade output. When PyPI is ahead of what the installer's index offers (a lagging mirror, mise's `minimum_release_age`), it says so instead of upgrading. An upgrade that leaves the installed version unchanged is reported as a failure.

You can also upgrade manually with your package manager:

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

All 15 CLIs (`backup`, `bim`, `dot`, `fctracker`, `fren`, `morph`, `muc`, `netscan`, `outlookctl`, `pinger`, `puc`, `readerctl`, `sysup`, `vuc`, `zseq`) are always installed. Extras add optional dependencies some tools need:

| Extra | Dep | Tool |
|-------|-----|------|
| `bim` | jira, textual, fpdf2 | bim |
| `bim-web` | fastapi, uvicorn, watchfiles | bim (web UI) |
| `doc` | ocrmypdf, pdfminer.six, requests, Unidecode | bim (doc subsystem) |
| `dot` | textual | dot (TUI) |
| `fren` | python-slugify, Unidecode | fren |
| `morph` | markdownify | morph |
| `muc` | ffmpeg-python | muc |
| `pinger` | ping3 | pinger |
| `readerctl` | requests | readerctl |
| `sysup-cert` | cryptography | sysup (x509-expiry) |
| `all` | all of the above | — |

## What's inside

**Library** (`src/lib/buvis/pybase/`) — shared adapters, CLI scaffolding, configuration, filesystem and formatting utilities, plus the zettel subsystem (domain logic, Jira integration, and a Rust extension via PyO3 for performance-critical parsing).

**Tools** (`src/tools/`) — 15 Click-based CLIs built on the library:

| Tool | Purpose |
|------|---------|
| backup | Config-driven tar archiver (git-src backup) |
| bim | BUVIS InfoMesh (zettel integration) |
| dot | Dotfiles manager, with host-specific config links via a `host-links` manifest |
| fctracker | Foreign currency account tracker |
| fren | File renamer toolkit |
| morph | File conversion toolkit |
| muc | Music collection tools |
| netscan | Network scanning tools |
| outlookctl | Outlook CLI |
| pinger | ICMP ping utilities |
| puc | Photo utility collection |
| readerctl | Readwise Reader CLI |
| sysup | System update tools |
| vuc | Video utility collection |
| zseq | Zettelsequence utilities |

### dot host-specific config

List per-host paths in the tracked manifest
`<dotfiles_root>/.config/buvis/host-links`, one `<target> => <source>` per
line. Both sides are `$HOME`-relative with `/` separators; absolute paths, `~`,
drive letters and `..` are rejected as `host-links:<lineno>: <reason>`.
`dot materialize` links each missing target to its untracked host file. It
never deletes or overwrites anything and warns about real files, wrong or
dangling links and missing sources. It also installs missing `post-checkout`,
`post-merge` and `post-rewrite` hooks into git `core.hooksPath` when set; they
run `dot materialize --hook`. `dot status` and the TUI (key `L`) report link
problems. On Windows, directories become junctions and file links need
Developer Mode. Details: `docs/source/tools/dot.rst`.

dot sets `core.hooksPath` to `<dotfiles_root>/.config/buvis/hooks` when it is
unset, and `dot status` warns when the hooks dir or its `pre-commit` is missing.

**New host:** `dot setup [<url>]` (or `BUVIS_DOT_REMOTE_URL`) bare-clones the
dotfiles repo, checks it out without overwriting existing files, and links host
config.

**Localizing files:** `dot localize <target> [--to <source>]` converts a tracked
file to a host-specific link: untracks it, moves it to the source location,
creates the symlink, and updates the manifest. Commit the staged manifest and
deletion, then push.

**Sharing one file across hosts:** `dot localize --shared <target>` keeps the
file where it is and registers a git clean/smudge filter for it instead. Git
stores the reserved `@HOME@` token in place of this host's home path, and each
host's checkout gets its own home back. The opt-in is one `.gitattributes`
line, staged for you; commit it with the file. `--shared` cannot be combined
with `--to`. Details: `docs/source/tools/dot.rst`.

**Pull rescue:** When another host's localize-commit arrives, `dot pull` detects
the incoming deletion and rescues your local bytes to the source location before
git removes the file. If both target and source exist with different content, you
choose which to keep (the other is backed up). The TUI (key `P`) shows a modal for
collisions. Warning: raw `git pull` bypasses rescue — always use `dot pull`.

**Divergence patch:** When an uncommitted edit touches a file the incoming
commits also change, `dot pull` saves the edit to
`~/.local/share/dot/divergence/<UTC timestamp>.patch`, resets that file to
`HEAD` and lets upstream win. The patch header names its base commit; `git apply`
it onto that commit to get the edit back, then delete the patch. `dot status`
and the TUI status bar warn while a patch is pending. Edited secrets are
saved encrypted; see `docs/source/tools/dot.rst` for recovery.

### bim doc subsystem

`bim doc ingest` watches the staging inbox and either auto-files a PDF
into `<business_root>/<issuer>/` (with a paired zettel under
`<vault>/<doc-subdir>/<issuer>/`) or stages it under `_triage/` when a
field is uncertain. `bim doc promote` finishes a triage proposal into a
filed zettel. `bim doc audit` is read-only: it walks `<business_root>/`
and writes a structured JSON report under `<state_dir>/audit/` covering
missing or orphan zettels, sha-256 mismatches, OCR/hash adapter failures,
rule-registry validity and freshness, plus a `legacy_layout_zettels`
list (zettels still at the pre-v1 flat path). `bim doc migrate-layout`
consumes that list and moves each zettel into its per-issuer subfolder
(dry-run by default; `--apply` performs the moves). See the
[Sphinx docs](https://buvis.github.io/gems/) for the full JSON schema.

