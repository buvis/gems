# klyreon C: operator asset install, refresh, and manifest

<!-- requirements; migrated from PRD 00076 flat file -->

## Overview

### Problem Statement
Klyreon's autonomous loop drives an operator CLI, but the same operator is also how the owner works on the vault by hand. Those interactive sessions need to know the format spec, the command surface, and the conventions, or they will write files klyreon rejects. Shipping that knowledge as documentation puts the burden on the user to copy files into the right place per operator and to re-copy them after every klyreon release. Nothing tracks what was installed, so nothing can refresh it, and a hand-tuned file gets clobbered or goes stale in silence.

### Target Users
The vault owner, setting klyreon up on a machine and upgrading it later. PRD D reuses the manifest to record the installed schedule. A follow-up PRD adds kiro and copilot asset packs against the same registry.

### Success Metrics
- `klyreon assets install --operator claude` into a temp HOME writes the claude asset pack, records every file in the manifest with a hash, and reports what it wrote.
- A second install changes no file and reports every file as current.
- A hand-edited asset is backed up beside itself before being overwritten, and the displaced path is reported (discovery Q18).
- `klyreon status` warns when the installed assets carry an older klyreon version than the running CLI.
- `klyreon assets uninstall` removes untouched klyreon files, keeps edited ones and says so, and leaves the manifest consistent.
- gems gates green: `pytest -m klyreon`, mypy strict, ruff, docs, CHANGELOG. No new dependency.

## Functional Decomposition

### Capability: Installed-artifact manifest
The record of what klyreon put where, on this machine.

#### Feature: Manifest store
- **Description**: One JSON file tracking every artifact klyreon installed outside the vault.
- **Inputs**: Entry records; `$XDG_STATE_HOME/klyreon/manifest.json`.
- **Outputs**: A typed manifest: `{"schema_version": 1, "entries": [{"kind": "asset", "operator": "claude", "path": "...", "sha256": "...", "klyreon_version": "0.12.7", "installed_at": "<iso>"}]}`.
- **Behavior**: `kind` exists because PRD D records the installed schedule in the same file (discovery Q17). Written through `pybase.filesystem.atomic_write`; a truncated manifest would orphan every installed file. An unknown `schema_version` is rejected loudly rather than guessed at. A missing manifest means nothing is installed, which is not an error. Entries key on absolute path.

### Capability: Operator asset packs
What gets installed, and where each operator expects it.

#### Feature: Operator registry
- **Description**: One table mapping an operator to its install root and its file list.
- **Inputs**: Operator name.
- **Outputs**: The target directory and the package-data files to place under it.
- **Behavior**: `claude` is the only entry in v1: the pack installs under `~/.claude/skills/klyreon/` (respecting `$CLAUDE_CONFIG_DIR` when set). Adding kiro or copilot later is a new row plus a payload directory, no installer change. An unknown operator name fails with the list of known ones.

#### Feature: Claude asset pack
- **Description**: The content that teaches an interactive Claude Code session how to work in a klyreon vault.
- **Inputs**: None; the pack is package data at `src/tools/klyreon/assets/payload/claude/`.
- **Outputs**: A `SKILL.md` carrying the trigger-led frontmatter, the two file species, the closed vocabularies, the claim and doubt rules, the three conflict shapes, and the klyreon command surface, pointing at `docs/reference/klyreon/zettel-format-specification.md` as normative.
- **Behavior**: One file in v1. It states plainly that a human session edits the vault through `klyreon new` and hand edits, and that klyreon's own autonomous loop does not read this file: the loop's prompts ship inside the package (PRD B). This keeps the loop independent of anything installed into a home directory.

### Capability: Install, refresh, uninstall
The lifecycle of an installed file.

#### Feature: assets install
- **Description**: `klyreon assets install [--operator NAME]...` places a pack and records it.
- **Inputs**: One or more operator names; default is every operator already present in the manifest, or a required choice when the manifest is empty.
- **Outputs**: `CommandResult` listing files written, files already current, and files displaced by backup.
- **Behavior**: For each file: if absent, write and record. If present and its hash matches the manifest, and the shipped content is identical, leave it and report "current". If present and its hash differs from the manifest, the user edited it: copy it to `<file>.klyreon-backup-YYYYMMDDHHmmSS` first, then write the shipped version and report the displaced path (discovery Q18). If present but absent from the manifest, treat it as a user file: back it up the same way before writing. Re-runnable at any time; it never touches the vault, so it works before `init` and after.

#### Feature: assets refresh and status
- **Description**: Bring installed packs up to the running CLI, and show what is installed.
- **Inputs**: The manifest, the running `klyreon.__version__`, the files on disk.
- **Outputs**: `assets refresh` re-installs every operator recorded in the manifest; `assets status` prints per file: operator, path, recorded version, whether the file matches its hash, whether it is behind the CLI.
- **Behavior**: Version comparison uses `packaging.version` against the recorded `klyreon_version`. A file whose hash no longer matches is reported as user-edited, so `status` tells the owner what a refresh will displace before they run it. `klyreon status` (PRD A) gains one line warning when any installed asset is behind the CLI; the check does not run on every invocation, because the health dashboard is where it belongs and a warning on every command is noise. Upgrading the binary itself stays the buvis-gems updater's job.

#### Feature: assets uninstall
- **Description**: Remove what klyreon installed, without destroying what the user changed.
- **Inputs**: One or more operator names.
- **Outputs**: `CommandResult` listing files removed and files kept.
- **Behavior**: A file whose hash still matches the manifest is klyreon's and is removed. A file whose hash differs is the user's work: it is left in place and reported as kept, because human edits are never reverted by automation. Manifest entries are dropped either way. Empty directories klyreon created are removed; directories holding anything else are left.

### Capability: Setup integration
Where the owner meets this the first time.

#### Feature: init offers asset installation
- **Description**: `klyreon init` asks which operators the user runs and installs their packs.
- **Inputs**: The interactive answer; `--operator NAME` (repeatable) to answer up front; `--no-input` to skip.
- **Outputs**: The same result as `assets install`, folded into init's report.
- **Behavior**: Prompting through `console.confirm` happens only on a TTY and only during `init`, which is explicitly an interactive setup command. With `--no-input`, or when stdin is not a TTY, init skips the offer and prints how to run `klyreon assets install` later. No autonomous run ever reaches this code path.
