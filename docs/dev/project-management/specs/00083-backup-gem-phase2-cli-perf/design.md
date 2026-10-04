# backup gem: Phase-2 CLI + perf enhancements v1

<!-- design; migrated from PRD 00083 flat file -->

## Implementation

### Files (all under `src/tools/backup/`)
- **`cli.py`** — add `--source` / `--out` / `--show-excludes` / `--for` options and
  their handlers (render via `console`; lazy-import as today).
- **`capabilities/tar_archive.py`** — add the `engine` input and the `tar -T`
  archiving branch; keep the Python walk/filter shared between both engines.
- **`config.py`** — accept `engine` in the `tar-archive` `with:` inputs contract.
- **`shared/bkpignore.py`** — expose a "resolve rules effective under path" entry
  point for `--show-excludes` (likely already present from v1; reuse).

### Tests (`tests/tools/backup/`)
- `--source`/`--out` override precedence and the multi-instance usage error.
- `--show-excludes --for` output matches the actual archived set for a fixture.
- `engine: system-tar` produces a byte-equivalent member set to the Python engine
  on a fixture tree; missing/incompatible `tar` falls back with a warning.
- v1 default behavior unchanged (regression).

## Provenance

Deferred fast-follow items from PRD 00082 (backup gem v1, merged 2026-09-26 as
[PR #179](https://github.com/buvis/gems/pull/179)). Grouped into one Phase-2 PRD
because all three touch the same gem and CLI and would ship together. No new
elicitation — these are the exact "Out of scope (v1) / Phase 2" items named in
00082, promoted to their own backlog PRD so the follow-up work isn't lost.
