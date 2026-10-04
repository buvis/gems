# bim doc: claim release + dedup identity integrity

<!-- design; migrated from PRD 00044 flat file -->

## Implementation

### Module: bim.commands.doc.shared.pipeline / state_db / promote
- **Location**: `src/tools/bim/commands/doc/shared/pipeline.py`, `shared/state_db.py`, `promote/promote.py`
- **Responsibility**: claim lifecycle (acquire → always release / expire) and consistent dedup keys across ingest/triage/promote.
- **Exports**: stale-claim predicate reading the existing `claimed_at` column, `release_claim()` (called from finally); `record_processed(source_sha)` on triage/promote.

### Dependencies
- No cross-PRD dependency. Touches only bim doc.
