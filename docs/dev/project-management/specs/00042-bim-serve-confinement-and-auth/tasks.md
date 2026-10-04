# bim serve: confine paths and require local auth

<!-- tasks; migrated from PRD 00042 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: one confinement + auth module.
**Tasks**:
- [ ] Add `serve/_security.py` with `confine_path`, `require_token`, `install_security` (no deps) — Acceptance: unit tests cover `/etc/passwd`, `../` escape, symlink escape (all 403) and an in-vault path (ok).
**Exit Criteria**: helper rejects every out-of-vault path in tests.

### Phase 1: Core
**Goal**: no endpoint touches an unconfined path.
**Tasks**:
- [ ] Apply `confine_path` in GET/PATCH/`open` (`_routes.py`) and every `_actions.py` handler that takes `file_path` (depends on: Phase 0) — Acceptance: integration test that PATCH/DELETE/GET on an absolute out-of-vault path returns 403 and the file is untouched.
**Exit Criteria**: `rg "Path\(file_path\)"` in serve has no unconfined use.

### Phase 2: Integration
**Goal**: cross-origin and unauthenticated callers are blocked.
**Tasks**:
- [ ] `install_security(app, ...)` in `create_app`; add `TrustedHostMiddleware`; generate + require the `X-Buvis-Token` header; warn on non-loopback `-H` (depends on: Phase 1) — Acceptance: request with a foreign Host → 400; mutating request without token → 401; TestClient asserts the served `index.html` carries the injected token and token-bearing API calls succeed (frontend has no test harness — `api.ts` wiring verified indirectly; manual WebUI smoke post-merge).
**Exit Criteria**: default-bind server rejects rebinding-style requests; `-H 0.0.0.0` prints a security warning.
