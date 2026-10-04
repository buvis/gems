# bim doc: claim release + dedup identity integrity

<!-- tasks; migrated from PRD 00044 flat file -->

## Tasks

### Phase 0: Foundation
- [ ] Add a stale-claim predicate to `state_db` reading the existing `claimed_at` column (`state_db.py:84`; no schema change) (no deps) — Acceptance: a claim older than the max age is reported reclaimable; unit test covers the boundary.

### Phase 1: Core
- [ ] Wrap `_run_after_claim` in `try/finally` (or catch `BaseException`) so the claim is always released; preserve the structured `CommandResult` for `Exception` (depends on: Phase 0) — Acceptance: injected `KeyboardInterrupt` releases the claim; re-run proceeds.
- [ ] Record the raw source sha on triage (`pipeline.py:627`) and promote (`promote.py:236-237`) (depends on: Phase 0) — Acceptance: re-ingesting the same source PDF after promote is detected as duplicate, no second archive copy.
