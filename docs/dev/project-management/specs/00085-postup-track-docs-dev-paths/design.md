# postup: track migrated docs/dev project-management paths

<!-- design; migrated from PRD 00085 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/postup/domain/
├── repofiles.py                   # Maps to: dual-location readers + read_purge_last_run
├── contracts.py                   # Maps to: purge_last_run field on the repo contract
└── derive.py                      # Maps to: purge-cadence nag (mirrors brush cadence)
src/tools/postup/commands/collect/
└── collect.py                     # Maps to: wire purge_last_run into the collected record
tests/tools/postup/domain/
├── test_repofiles.py              # Maps to: dual-location + purge reader
└── test_derive.py                 # Maps to: purge-cadence nag
tests/tools/postup/
└── test_parity.py                 # Maps to: re-parity against the migrated skill state
```

### Module: repofiles (path resolution)
- **Maps to capability**: Track migrated project-management paths
- **Responsibility**: Pure filesystem readers; resolve new-vs-legacy location; no UI, no subprocess, no network (keeps the interface-agnostic invariant).
- **Exports** (added/changed):
  - `read_prd_pipeline(repo)` — unchanged signature; dual-location resolution inside
  - `read_brush_last_run(repo)` — unchanged signature; dual-location resolution inside
  - `read_purge_last_run(repo)` — new; `YYYY-MM-DD | None`

## Dependency Graph

### Foundation Layer (Phase 0)
- **repofiles path resolution**: no deps — the shared new-vs-legacy helper + the three readers.

### Core Layer (Phase 1)
- **contract + collect wiring**: depends on [repofiles path resolution]
- **derive purge-cadence nag**: depends on [contract + collect wiring]

### Integration Layer (Phase 2)
- **re-parity against migrated skill**: depends on [all of Phase 1]

## Test Strategy

### Critical Scenarios
- **Happy path (migrated repo)**: only `docs/dev/project-management/prds` present → Expected: postup reads it; legacy path ignored.
- **Happy path (legacy repo)**: only `dev/local/prds` present → Expected: postup reads it (no regression for not-yet-migrated repos).
- **Edge case (both present)**: mid-migration repo → Expected: postup reads the new location deterministically.
- **Edge case (neither present)**: → Expected: empty `PrdPipeline` / `None` brush / `None` purge, exactly as today.
- **Purge signal**: populated `docs/dev/tmp/.trash` → Expected: `purge_last_run` set, nag raised past threshold; absent → `None`, no nag.
- **Re-parity**: postup output vs the migrated skill output → Expected: full coverage including the purge field.

## Risks

- **Migration not yet committed** in `agent-skills` (the driving edits are uncommitted at 51/51): this PRD makes postup track the target paths regardless of when the skill migration lands, and the legacy fallback means shipping it early cannot regress a not-yet-migrated repo. The re-parity in Phase 2 must run against the skill's state at *implementation* time — if the migration has been reverted or changed shape again, resolve the actual paths/detection from the current skill source rather than this PRD's snapshot (the brief-portfolio path has drifted twice already).
- **Purge detection shape drift**: the skill's trash-scan detail (mtime vs dated marker) is read from its current `collect.py` at implementation time, not hardcoded from this PRD.
- **Contract version bump**: adding `purge_last_run` is additive; follow contracts.py's additive-evolution + version-reject rule so older payloads still load.
- **Interface-agnostic invariant**: all new reads stay pure filesystem in the domain layer — no subprocess, no UI import — same as the existing readers.
