# postup: track migrated docs/dev project-management paths

<!-- tasks; migrated from PRD 00085 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: Readers resolve the new location with a legacy fallback, tested.

**Tasks**:
- [ ] Shared resolution helper + update `read_prd_pipeline` and `read_brush_last_run` to prefer `docs/dev/project-management/`, fall back to `dev/local/` (no deps) — Acceptance: a repo with only the new tree reads it; a repo with only the legacy tree reads it; a repo with both reads the new tree; a repo with neither returns empty/`None` exactly as today. New tests in `test_repofiles.py` cover all four cases per reader.
- [ ] `read_purge_last_run(repo)` reading `docs/dev/tmp/.trash` with a legacy `dev/local/.trash` fallback, detection shape resolved from the current skill `collect.py` (no deps) — Acceptance: returns the expected date for a populated trash dir, `None` for an absent one; test covers both.

**Exit Criteria**: All three readers resolve correctly across migrated / legacy / both / neither, on fixtures.

### Phase 1: Core
**Goal**: The purge signal reaches the brief.

**Tasks**:
- [ ] Add `purge_last_run: str | None` to the repo contract and wire it into `collect.py` alongside `brush_last_run` (depends on: Phase 0) — Acceptance: a collected record carries `purge_last_run`; mypy clean; the contract version bumps if the schema rule requires it (per contracts.py's additive-evolution note).
- [ ] Derive a purge-cadence nag mirroring the brush cadence in `derive.py` (depends on: contract wiring) — Acceptance: a repo whose `purge_last_run` exceeds the threshold surfaces the nag; one within the threshold does not; `test_derive.py` covers both boundaries.

**Exit Criteria**: `postup collect` emits the purge signal and the brief shows the cadence nag; `pytest -m postup` green.

### Phase 2: Integration
**Goal**: Parity holds against the migrated skill, unblocking the 00070 deletion.

**Tasks**:
- [ ] Re-run the 00070 parity gate against the skill's **current** (migrated) collector state; update the parity fixtures/artifact to reflect the migrated paths and the now-covered purge field (depends on: all Phase 1) — Acceptance: the parity suite passes with PRD/brush/purge covered against the migrated skill output; the recorded artifact names the migrated repo set and shows no missing field; a genuine repo-set difference is a config note, not a failure.
- [ ] CHANGELOG entry under `[Unreleased]` (depends on: Phase 1) — Acceptance: notes that postup now tracks the `docs/dev/project-management/` layout and the purge cadence.

**Exit Criteria**: Success Metrics hold; postup is a faithful superset of the migrated skill, so 00070's skill-deletion follow-up is unblocked (pending the owner committing the migration and running the corrected `git rm` in `agent-skills`).
