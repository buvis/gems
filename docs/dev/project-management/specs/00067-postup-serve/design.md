# postup E: serve (FastAPI + SSE + confinement)

<!-- design; migrated from PRD 00067 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/postup/adapters/web/
├── __init__.py
├── app.py                   # Maps to: App factory (create_app)
├── _routes.py               # Maps to: REST payload endpoints + triggers
├── _sse.py                  # Maps to: SSE refresh (watchfiles)
└── frontend/build/          # served static UI (from 00065/00066)
src/tools/postup/commands/
└── serve/serve.py           # Maps to: serve command (CommandServe)
tests/tools/postup/          # route/confinement/sse/trigger tests
```

### Module: postup.adapters.web
- **Maps to capability**: Serve application + Live data plane
- **Responsibility**: HTTP delivery only — routes, SSE, static UI, confinement; all actions delegate to command classes.
- **Exports**:
  - `create_app(settings)` - configured FastAPI app
  - route handlers (payload/prev/history/trigger/SSE)

### Module: postup.commands.serve
- **Maps to capability**: Serve application
- **Responsibility**: Validate settings/extras, start uvicorn; return `CommandResult` for failures.
- **Exports**:
  - `CommandServe` - `execute() -> CommandResult`

## Dependency Graph

### Foundation Layer (Phase 0)
External: 00065 (frontend build + loader contract) and 00064 (enrich command) must be in `done/`.

- **create_app skeleton + confinement middleware**: no internal dependencies — built first.

### Core Layer (Phase 1)
- **payload endpoints + SSE**: depends on [create_app]

### Integration Layer (Phase 2)
- **collect/enrich triggers + serve command + extra wiring**: depends on [payload endpoints, create_app]

## Test Strategy

### Critical Scenarios
- **Happy path**: fixture out_dir, serve, fetch payload, trigger collect (mocked), receive SSE → Expected: UI data flows end to end.
- **Edge case**: empty out_dir (never collected) → Expected: explicit empty-portfolio response; UI renders its empty state; no 500.
- **Error case**: path traversal in a request-derived path / non-localhost Host header → Expected: rejected by confinement; trigger failure surfaces the `CommandResult` error message in the response.

## Risks

- **Open decision (design): auto-collect on serve start vs serve-last-data-until-refreshed** — affects startup latency and surprise network calls; design doc decides, both fit this structure.
- **Route-pattern choice**: bim's action-registry is the default candidate; if design rejects it, routes stay bespoke — either way actions go through the composition root.
- **Done-state endpoint (nice-to-have)**: server-side done persistence (JSON in out_dir) may land here later; 00065's storage seam keeps it a local swap, not scoped in this PRD.
- **Auto-open browser (nice-to-have)**: deliberately unscoped; add later behind a flag if wanted.
- **SSE/watchfiles platform quirks**: mirror bim's `_sse.py` implementation rather than inventing a new watcher.
