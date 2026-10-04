# postup F: TUI + text brief (Python derive layer)

<!-- tasks; migrated from PRD 00068 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: Tested Python view-model.

**Tasks**:
- [ ] `domain.derive` with loader and view-model, tested against the shared fixture payloads (no deps) - Acceptance: derive tests green incl. missing `epics.json`, missing `data.json`, no-prev diff; zero UI imports asserted.

**Exit Criteria**: View-model green and UI-free.

### Phase 1: Core
**Goal**: The default text surface.

**Tasks**:
- [ ] `CommandBrief` + console rendering + bare-`postup` dispatch (depends on: Phase 0) - Acceptance: output snapshot-style unit test from fixtures; "run collect first" state; test asserts `textual` not imported on the bare path.

**Exit Criteria**: Bare `postup` prints the standup on a core-only install.

### Phase 2: Integration
**Goal**: The interactive surface.

**Tasks**:
- [ ] Textual app (attention queue, todos, repo list) + `CommandTui` + `postup` extra wiring (depends on: Phase 0) - Acceptance: Textual snapshot tests cover the main layout incl. degraded (`errors[]`) and not-enriched states; missing-extra path yields `require_import` guidance.
- [ ] Docs + CHANGELOG Added entry (depends on: Phase 0) - Acceptance: gems gates green; snapshot baselines generated via the `update-snapshots` workflow.

**Exit Criteria**: Success Metrics hold; `pytest -m postup` green incl. auto-skipped snapshots locally.
