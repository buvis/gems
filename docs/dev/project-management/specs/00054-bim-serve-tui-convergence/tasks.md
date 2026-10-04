# bim: route every interface through the command classes

<!-- tasks; migrated from PRD 00054 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: adopt the result envelope.
**Tasks**:
- [ ] Make serve action handlers return `CommandResult.to_dict()`; add the route-level status mapping per `dev/local/specs/all-interface-architecture.md` (depends on: the seam spec) — Acceptance: a failing action returns a 4xx/5xx with the envelope; a passing one returns 200.
**Exit Criteria**: `CommandResult.to_dict()` has real callers; no handler returns 200-on-error.

### Phase 1: Core
**Goal**: no inline write path.
**Tasks**:
- [ ] Delete the PATCH route body; delegate to `UpdateZettelUseCase`, preserving the 00042 security layer on the route (`confine_path` + `X-Buvis-Token` check) (depends on: Phase 0) — Acceptance: PATCH and `handle_patch` share one code path; section-replace exists once; an out-of-vault or tokenless PATCH still returns 403/401.
- [ ] Route `tui/create_note.py` through `CommandCreateNote` (depends on: Phase 0) — Acceptance: TUI create runs the same validation/defaults as CLI; empty required answer is rejected.
**Exit Criteria**: no interface writes a note without a command class / use case.

### Phase 2: Integration
**Goal**: failures are visible everywhere.
**Tasks**:
- [ ] `api.ts` / `ActionBar` check the envelope `status` (keeping the 00042 `X-Buvis-Token` header); `EditScreen._save` and the query-TUI screens `notify(severity="error")` on `CommandResult` failure (depends on: Phase 1) — Acceptance: a failing action returns non-2xx with the envelope (route test) and the TUI notifies on failure (Textual test); `api.ts`/`ActionBar` changes are verified indirectly (frontend has no test harness — manual WebUI smoke post-merge).
**Exit Criteria**: no silent-success or silent-failure path remains.
