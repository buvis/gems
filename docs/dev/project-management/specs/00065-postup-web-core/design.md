# postup C: web frontend core (SvelteKit skeleton + derive port + core views)

<!-- design; migrated from PRD 00065 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/postup/adapters/web/
└── frontend/                    # Maps to: Frontend foundation (bim subtree pattern)
    ├── package.json
    ├── svelte.config.js
    ├── src/
    │   ├── lib/
    │   │   ├── derive.js        # Maps to: derive port
    │   │   ├── derive.test.js   # ported test suite
    │   │   ├── payload.js       # Maps to: Payload plumbing
    │   │   └── done.js          # Maps to: Done-state
    │   └── routes/              # Maps to: Brief/Todos/Repos views
    └── build/                   # committed production build
```

(Final subtree location follows bim's serve-adjacent placement translated to the multi-interface layout; design-solution pins the exact path, the module contract below does not change.)

### Module: frontend/src/lib (payload, derive, done)
- **Maps to capability**: Frontend foundation + Derived view-model
- **Responsibility**: All non-view logic: loading, deriving, done-state; views stay declarative.
- **Exports**:
  - `loadPayload()` - typed payload store (dev fixtures / prod fetch)
  - `derive(payload)` - attention queue, todos, repo summaries
  - `doneStore` - persisted, pruned done set

### Module: frontend/src/routes
- **Maps to capability**: Core views
- **Responsibility**: Brief/Todos/Repos presentation only.
- **Exports**:
  - Routed Svelte pages for the three tabs

## Dependency Graph

### Foundation Layer (Phase 0)
External: 00063 (`data.json` contract) and 00064 (epics schema) must be in `done/` — both feed the fixtures.

- **SvelteKit skeleton + fixture payloads**: no internal dependencies — built first.

### Core Layer (Phase 1)
- **derive port (+ tests)**: depends on [fixtures]
- **payload plumbing**: depends on [skeleton]

### Integration Layer (Phase 2)
- **Brief/Todos/Repos views + done-state**: depends on [derive, payload plumbing]

## Test Strategy

### Critical Scenarios
- **Happy path**: enriched fixture → Expected: Brief shows summary/epics; Todos merges judgment + mechanical todos; Repos shows all repos.
- **Edge case**: no `epics.json` → Expected: deterministic-only rendering, explicit "not enriched" cue, no broken sections.
- **Error case**: payload repo with `errors[]` → Expected: repo renders with error badge; nothing crashes.

JS tests (vitest) run via `npm test` in-session/locally; they are not part of the pytest CI gate (`BUVIS_SKIP_FRONTEND=1`). 00066 inherits this harness.

## Risks

- **2,500-line rewrite creep**: scope fence — only the three core tabs here; everything else is 00066 (this split exists precisely to avoid context overflow).
- **derive parity drift**: tests ported before implementation; same-fixture parity check against the SPA is the gate.
- **JS/Python derive duplication (00068 implements a Python subset)**: shared fixture payloads keep both honest; divergence surfaces as a fixture test failure on either side.
- **Frontend toolchain versions**: follow bim's SvelteKit/adapter versions to keep one convention.
