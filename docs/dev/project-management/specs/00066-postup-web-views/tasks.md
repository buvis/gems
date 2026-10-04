# postup D: web frontend views (Matrix/Activity/Work/PRDs + temporal features)

<!-- tasks; migrated from PRD 00066 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: Temporal logic, test-first.

**Tasks**:
- [ ] Extend fixtures with `data-prev.json` + `history.jsonl`; write diff/trend/horizon derive tests, then implementations (no deps) - Acceptance: derive tests green incl. no-prev and single-history-line cases.

**Exit Criteria**: Temporal derive functions green.

### Phase 1: Core
**Goal**: The four remaining tabs.

**Tasks**:
- [ ] Matrix, Activity, Work, PRDs views (depends on: Phase 0) - Acceptance: component test per view from fixtures, incl. deterministic-only Matrix fallback and empty-state Work.

**Exit Criteria**: All tabs render from fixtures.

### Phase 2: Integration
**Goal**: Drill-down and temporal presentation; parity complete.

**Tasks**:
- [ ] RepoDetail route with `errors[]` surfacing (depends on: Phase 1) - Acceptance: detail renders a degraded repo's errors verbatim.
- [ ] Horizon strip, since-last badges, trend sparkline on Brief/Repos (depends on: Phase 1) - Acceptance: component tests cover with-prev, without-prev, thin-history.
- [ ] SPA parity sweep, CHANGELOG Added entry, refreshed committed build (depends on: Phase 1) - Acceptance: every SPA component's information content mapped to a new view (checklist written to `dev/local/audit-results/spa-parity-<date>.md`, the 00070 parity-artifact precedent); gates green.

**Exit Criteria**: Success Metrics hold; web feature parity with the SPA reached.
