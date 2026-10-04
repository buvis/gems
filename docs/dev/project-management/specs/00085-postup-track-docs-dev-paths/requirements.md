# postup: track migrated docs/dev project-management paths

<!-- requirements; migrated from PRD 00085 flat file -->

## Overview

### Problem Statement
postup's pure filesystem signal readers (`src/tools/postup/domain/repofiles.py`) hardcode the pre-migration project-management layout:

| Signal | postup reads today | Migrated target (skill's uncommitted edits) |
|---|---|---|
| PRD pipeline | `dev/local/prds/{backlog,wip,done}` | `docs/dev/project-management/prds/{backlog,wip,done}` |
| Brush report | `dev/local/audit-results/brush-report.md` | `docs/dev/project-management/audit-results/brush-report.md` |
| Purge/trash cadence | *(not read at all)* | `docs/dev/tmp/.trash` → a `purge_last_run` maintenance nag |

The `brief-portfolio` skill is being migrated (`purge-devlocal` → `purge-devtmp`; project-management artifacts `dev/local/` → `docs/dev/project-management/`; trash `dev/local/.trash` → `docs/dev/tmp/.trash`). This monorepo already carries the migration's landing zone: `docs/dev/project-management/{backlog,wip,done,...}` exists (scaffolded, `.migration-placeholder`). Once a repo completes the migration, postup reads **empty** PRD and brush signals from the vacated `dev/local/` paths — a real regression that the 00070 parity gate could not catch, because that gate compared postup against the skill's *committed* (pre-migration) state.

### Target Users
Solo developer reading the portfolio brief; repo hygiene (postup must be a faithful superset of the skill before the skill is deleted).

### Success Metrics
- postup reads PRD pipeline and brush-report signals from `docs/dev/project-management/` **with a fallback to the legacy `dev/local/` location**, so both migrated and not-yet-migrated repos report correctly.
- postup emits a `purge_last_run` signal read from `docs/dev/tmp/.trash`, and the derive layer surfaces a purge-cadence nag mirroring the brush cadence.
- The 00070 parity gate re-runs GREEN against the skill's **current** (migrated) collector state, with these three signals covered — no field the migrated skill emits is missing from postup.
- CHANGELOG carries the path-migration note; gems gates green (`pytest -m postup`, mypy, ruff).

### Non-goals
- Performing the skill migration itself (that is an out-of-gems `agent-skills` action by the owner) — this PRD makes postup track the migrated paths, nothing more.
- Deleting the skill (00070's follow-up; gated on this PRD + the owner committing the migration).
- Migrating any repo's own `dev/local/` → `docs/dev/` layout (postup only *reads* these paths; it never writes them).

## Functional Decomposition

### Capability: Track migrated project-management paths
Read the relocated signals without breaking not-yet-migrated repos.

#### Feature: Dual-location PRD + brush readers
- **Description**: `read_prd_pipeline` and `read_brush_last_run` resolve the new `docs/dev/project-management/` location first, falling back to the legacy `dev/local/` location when the new one is absent.
- **Inputs**: Repository working-tree root.
- **Outputs**: Same `PrdPipeline` / brush-date contracts as today — shape unchanged, source path resolved.
- **Behavior**: Prefer `docs/dev/project-management/prds` (resp. `.../audit-results/brush-report.md`); if that directory/file is absent, read the legacy `dev/local/` path; if neither exists, return the empty/`None` result exactly as today. A repo mid-migration (both present) reads the new one. Resolution is a single shared helper so both readers and any future one share one precedence rule.

#### Feature: Purge-cadence signal
- **Description**: The maintenance-nag signal the migrated skill produces and postup never implemented.
- **Inputs**: Repository working-tree root; the trash directory `docs/dev/tmp/.trash` (fallback legacy `dev/local/.trash`).
- **Outputs**: A `purge_last_run` field (`YYYY-MM-DD` or `None`) on the repo contract, mirroring `brush_last_run`.
- **Behavior**: `read_purge_last_run(repo)` returns the last-run date from the trash-dir signal (same detection shape the skill uses — most-recent mtime or a dated marker, resolved from the actual skill source at implementation time). The derive layer raises a purge-cadence nag when it exceeds the threshold, mirroring `_BRUSH_CADENCE_DAYS`.
