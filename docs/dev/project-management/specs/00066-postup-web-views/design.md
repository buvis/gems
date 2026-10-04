# postup D: web frontend views (Matrix/Activity/Work/PRDs + temporal features)

<!-- design; migrated from PRD 00066 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/postup/adapters/web/frontend/src/
├── lib/
│   ├── derive.js            # extended: diff + trend + horizon inputs (test-first)
│   └── payload.js           # extended: data-prev.json + history.jsonl loading
└── routes/                  # Maps to: Extended views + RepoDetail
    ├── matrix/
    ├── activity/
    ├── work/
    ├── prds/
    └── repo/[name]/
```

### Module: frontend/src/lib (derive + payload extensions)
- **Maps to capability**: Temporal features
- **Responsibility**: Diff, trend, and horizon computation as pure functions; loading of prev/history inputs.
- **Exports**:
  - `diffSinceLast(current, prev)` - since-last structure
  - `trendSeries(historyLines)` - sparkline series
  - extended `loadPayload()` - prev + history aware

### Module: frontend/src/routes (extended)
- **Maps to capability**: Extended views
- **Responsibility**: Presentation of the four tabs + RepoDetail.
- **Exports**:
  - Routed pages: matrix, activity, work, prds, repo/[name]

## Dependency Graph

### Foundation Layer (Phase 0)
External: 00065 (skeleton, derive, plumbing) must be in `done/`.

- **derive/payload extensions**: no internal dependencies within this PRD — built first.

### Core Layer (Phase 1)
- **Extended tabs (Matrix/Activity/Work/PRDs)**: depends on [derive/payload extensions]

### Integration Layer (Phase 2)
- **RepoDetail + Horizon/diff/trend presentation**: depends on [extended tabs, derive/payload extensions]

## Test Strategy

### Critical Scenarios
- **Happy path**: enriched fixture with prev + history → Expected: all tabs, horizon, diff badges, sparkline render.
- **Edge case**: first run (no `data-prev.json`, one history line) → Expected: no diff markers, dot sparkline, no errors.
- **Error case**: repo with `errors[]` opened in RepoDetail → Expected: errors shown verbatim, rest of the page intact.

## Risks

- **Parity blind spots** (only derive.js was tested in the SPA): the Phase 2 parity sweep is a per-component checklist against the SPA source, not memory.
- **Scope bleed into serve concerns**: this PRD renders from fixtures only; anything requiring a server (SSE refresh, triggers) belongs to 00067.
- **Diff/trend semantics drift from the skill**: derive tests encode the skill's current semantics from fixture pairs generated against the old collector's documented behavior.
