# postup E: serve (FastAPI + SSE + confinement)

<!-- tasks; migrated from PRD 00067 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: A confined, static-serving app factory.

**Tasks**:
- [ ] `create_app` serving the committed build; localhost bind, TrustedHost, auth, path confinement (no deps) - Acceptance: confinement tests — non-local host header rejected, traversal path rejected, unauthenticated request rejected per bim convention.
- [ ] Wire `postup-web` extra (fastapi/uvicorn/watchfiles) + update `all`; `require_import` guidance when absent (no deps) - Acceptance: import without extra yields the guidance message.

**Exit Criteria**: Static UI reachable on localhost in tests; confinement suite green.

### Phase 1: Core
**Goal**: Live payload plane.

**Tasks**:
- [ ] Payload/prev/history endpoints incl. not-yet-collected state (depends on: Phase 0) - Acceptance: endpoint tests round-trip the fixture contracts; empty out_dir returns the explicit empty state.
- [ ] SSE endpoint on out_dir changes with debounce (depends on: Phase 0) - Acceptance: test simulating an atomic replace emits exactly one event.

**Exit Criteria**: Frontend loader (00065 prod mode) works against the test server.

### Phase 2: Integration
**Goal**: Actions from the UI; command complete.

**Tasks**:
- [ ] Collect/enrich trigger endpoints via the composition root, with already-running rejection (depends on: Phase 1) - Acceptance: trigger tests assert the same command classes execute (mocked) and status/messages surface; concurrent trigger rejected.
- [ ] `CommandServe` + CLI wiring + docs + CHANGELOG Added entry (depends on: Phase 1) - Acceptance: gems gates green; `postup serve` documented.
- [ ] Extend `hatch_build.py`'s `_build_frontend` to also build/package postup's frontend for release wheels — it is currently hardcoded to bim's frontend dir only (`hatch_build.py:79`); generalize to iterate tool frontend dirs, or add an explicit second call, honoring `BUVIS_SKIP_FRONTEND` (depends on: Phase 1) - Acceptance: a release-mode build (`BUVIS_SKIP_FRONTEND` unset) produces a freshly built postup frontend bundle alongside bim's; a build-hook test covers both tool dirs.

**Exit Criteria**: Success Metrics demonstrable via the TestClient/SSE/trigger suites against a real out_dir; browser smoke (serve, browse, trigger collect, watch SSE refresh) is a documented post-merge step.
