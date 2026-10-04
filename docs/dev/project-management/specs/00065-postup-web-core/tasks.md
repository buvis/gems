# postup C: web frontend core (SvelteKit skeleton + derive port + core views)

<!-- tasks; migrated from PRD 00065 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: A building SvelteKit skeleton with realistic fixtures.

**Tasks**:
- [ ] Scaffold the SvelteKit app per bim layout, including a configured vitest test runner; commit a passing production build (no deps) - Acceptance: `npm run build` succeeds; build committed; `npm test` runs vitest green (empty suite ok).
- [ ] Generate fixture `data.json`/`epics.json` payloads from the 00063/00064 schemas (no deps) - Acceptance: fixtures validate against the pydantic contracts.

**Exit Criteria**: Empty app builds; fixtures exist and validate.

### Phase 1: Core
**Goal**: Tested logic layer.

**Tasks**:
- [ ] Port `derive.js` test suite, then the implementation, against the fixtures (depends on: Phase 0) - Acceptance: ported tests green; parity spot-check vs the SPA's derive on the same fixture.
- [ ] Payload loader with dev/prod modes and enrichment-absent handling (depends on: Phase 0) - Acceptance: loader tests cover fixture mode, fetch mode (mocked), missing `epics.json`.

**Exit Criteria**: Logic layer green with no views yet.

### Phase 2: Integration
**Goal**: The three core views, usable from a fixture.

**Tasks**:
- [ ] Brief, Todos, Repos views bound to derive output (depends on: Phase 1) - Acceptance: component tests render each view from fixtures incl. deterministic-only mode and `errors[]` badges.
- [ ] Done-state store (postup localStorage key, pruning) wired into Todos (depends on: Phase 1) - Acceptance: done set survives reload (test via storage mock) and prunes ids absent from payload.
- [ ] CHANGELOG Added entry; commit refreshed build (depends on: Phase 1) - Acceptance: gems gates green; build artifact current.

**Exit Criteria**: Success Metrics hold from fixture payloads alone.
