# bim doc triage: list-and-approve review surface

<!-- requirements; migrated from PRD 00057 flat file -->

## Problem

Reviewing a triaged PDF is the clunkiest step of bim's most-invested workflow. Today the user must manually locate the proposal YAML under `_triage/`, hand-edit `approved: true`, then run `bim doc promote <path>` per file (`docs/source/tools/bim.rst:349-364`). There is no command to list what's waiting in triage or to approve it, and the WebUI action registry exposes only note verbs (patch/sync/create/archive/open/delete/format/import — `serve/_actions.py:175-184`), zero doc actions, so the doc subsystem is the real all-interface gap. This is the #3 user-facing win.

## Solution

Add `bim doc triage` to list pending triage proposals and `--approve` to mark and (optionally) promote them without hand-editing YAML. Build it CLI-first through a command class, then register it as a serve action via the seam contract (`dev/local/specs/all-interface-architecture.md`) so the WebUI gets it too.

## Requirements

### Must have
- `bim doc triage` (list) shows pending proposals under `_triage/` with the fields a reviewer needs (issuer, doc type, date, uncertain field(s), path).
- `bim doc triage --approve <id-or-path>` sets the proposal approved and promotes it (or approves for a subsequent promote), replacing the hand-edit-then-promote dance.
- Command returns `CommandResult`; CLI renders it; no `sys.exit`/`console.panic` in the command class.
- Registered in the serve action registry per the seam contract in `dev/local/specs/all-interface-architecture.md`, exposed through the existing generic `POST /api/actions/{name}` route — no new WebUI (Svelte) components in this PRD.
- `docs/source/tools/bim.rst` triage section replaces the hand-edit-YAML instructions with the new commands.
- Tests: list reflects the triage dir; approve transitions a fixture proposal and promotes it (reusing the 00043 collision-safe promote).

### Nice to have
- A `--reject`/discard verb.

## Success Criteria

- Reviewing/approving a triaged PDF needs no manual YAML editing.
- Doc verbs are available beyond the CLI (all-interface parity for triage); bim doc tests green.
