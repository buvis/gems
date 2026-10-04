# Surface the meta-budget share in postup

<!-- tasks; migrated from PRD 00072 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: Trustworthy meta-share number.

**Tasks**:
- [ ] meta_share collector + attribution premise re-check (no deps) -
  Acceptance: unit tests cover meta/product/unknown attribution and empty
  ledger; fixture ledger reproduces a known percentage.

**Exit Criteria**: collector green with pinned attribution rules.

### Phase 1: Core
**Goal**: Visible in both briefs.

**Tasks**:
- [ ] Web + text brief tiles with ceiling state (depends on: Phase 0, postup
  00065/00068) - Acceptance: rendered output shows percentage and color state;
  "n/a" path covered by a test.

**Exit Criteria**: Success Metrics all verifiably true.

### Phase 2: Integration
**Goal**: none - retained for template parity.

**Tasks**: none - this PRD completes in two phases; the heading is retained for template parity.

**Exit Criteria**: n/a - see Phase 1.
