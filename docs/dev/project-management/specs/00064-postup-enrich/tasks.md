# postup B: LLM enrichment via claude CLI

<!-- tasks; migrated from PRD 00064 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: The epics contract and prompt exist and are tested.

**Tasks**:
- [ ] Implement `EpicsPayload` schema (summary, per-repo epics w/ SHAs, judgment todos w/ stable ids, urgency, importance/effort) (no deps) - Acceptance: valid/invalid fixtures pass/fail validation; SHA cross-check rejects unknown SHAs.
- [ ] Port prompt + epic/todo rules from the skill into `domain.prompt` (no deps) - Acceptance: prompt builds from fixture data/digest; rules text matches the skill's current behavior spec.

**Exit Criteria**: Schema + prompt unit-tested with no subprocess involved.

### Phase 1: Core
**Goal**: A tested claude CLI adapter.

**Tasks**:
- [ ] `ClaudeAdapter` with availability detection and `-p` invocation (depends on: Phase 0) - Acceptance: subprocess-mocked tests cover present/absent, model flag pass-through, timeout, non-zero exit.

**Exit Criteria**: Adapter behavior fully covered without a real `claude` binary.

### Phase 2: Integration
**Goal**: `postup enrich` end to end.

**Tasks**:
- [ ] `CommandEnrich` with alert, retry-once, loud degradation, atomic write (depends on: Phase 1) - Acceptance: mocked-LLM tests cover happy path, invalid-JSON→retry→success, retry→fail→degrade-without-write, claude-absent path, missing `data.json` failure result.
- [ ] CLI wiring, docs update, CHANGELOG Added entry (depends on: Phase 1) - Acceptance: gems gates green.

**Exit Criteria**: Success Metrics hold on the real portfolio with and without `claude` on PATH.
