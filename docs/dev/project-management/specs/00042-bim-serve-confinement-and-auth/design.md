# bim serve: confine paths and require local auth

<!-- design; migrated from PRD 00042 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/bim/commands/serve/
├── _routes.py      # Maps to: Path confinement (GET/PATCH/open)
├── _actions.py     # Maps to: Path confinement (action handlers)
├── _app.py         # Maps to: Local access control (middleware)
├── _security.py    # NEW — confine_path() + token helpers
└── frontend/src/lib/api.ts   # sends the local token header
```

### Module: serve._security
- **Maps to capability**: Path confinement + Local access control
- **Responsibility**: the single place that decides "is this path/request allowed".
- **Exports**: `confine_path(file_path, app_state) -> Path`, `require_token(request)`, `install_security(app, allowed_hosts)`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies — built first.
- **serve._security**: confinement + token/middleware helpers.

### Core Layer (Phase 1)
- **serve._routes / serve._actions**: Depend on [serve._security] — call `confine_path` in every path-taking handler.

### Integration Layer (Phase 2)
- **serve._app / frontend api.ts**: Depend on [serve._security] — install middleware, thread the token to the WebUI.

## Test Strategy

### Critical Scenarios
- **Happy path**: WebUI patches an in-vault note with the token → 200, note updated.
- **Edge case**: symlink inside the vault pointing outside → confinement follows `resolve()` → 403.
- **Error case**: `GET /api/zettels//etc/passwd` → 403, no file read; `DELETE` an absolute path → 403, file intact.

## Risks

- **Frontend token wiring**: the SvelteKit app must send `X-Buvis-Token`; inject the token into the served `index.html` so no manual config is needed. The frontend has no test infrastructure (no vitest/playwright) — its wiring is verified indirectly via the TestClient assertions above; manual WebUI smoke after merge.
- **Breaking legitimate archive access**: archive_directory may be `None`; guard the allowed-roots list so a `None` archive doesn't crash confinement.

---

<!-- folded from architecture/decisions/00042-bim-serve-confinement-and-auth-v1-design.md -->

# Design: bim serve — confine paths and require local auth

## Architecture fit

Target layer is the existing tool-level FastAPI app under
`src/tools/bim/commands/serve/` (not `src/lib` — this is transport/tool
plumbing, not shared domain logic). The fix adds one new peer module,
`_security.py`, next to the existing `_routes.py` / `_actions.py` / `_app.py`
split, and edits all three to call into it. This closes the two GAP
invariants named in `AGENTS.md`'s evolution-guardrails table for `bim serve`:
"Confine request-derived paths" (resolve + assert-under-root before any
read/write/delete/open) and the auth/`TrustedHostMiddleware` clause of the
same paragraph. No other tool or layer is touched — `serve._security` has no
callers outside `serve/`.

## Module placement

- **NEW** `src/tools/bim/commands/serve/_security.py` — the single module
  that decides "is this path/request allowed". Exports `AppState` (moved
  here from `_actions.py`, see Reuse inventory), `TOKEN_HEADER`,
  `confine_path`, `generate_token`, `require_token`, `install_security`.
  No imports from `_routes.py`/`_actions.py`/`_app.py` — this keeps it a
  true Foundation-layer module per the PRD's Dependency Graph (Phase 0, no
  deps), which is what lets `_actions.py` import `AppState` from it without
  a cycle.
- **EDIT** `src/tools/bim/commands/serve/_actions.py` — delete the local
  `AppState` dataclass, import it from `_security`; add one `confine_path(...)`
  call at the top of every handler that takes `file_path` (8 handlers).
- **EDIT** `src/tools/bim/commands/serve/_routes.py` — add `confine_path`
  calls in `get_zettel`, `patch_zettel`, `open_file`; add
  `Depends(require_token)` to `patch_zettel`, `open_file`, `exec_action`.
- **EDIT** `src/tools/bim/commands/serve/_app.py` — `create_app` gains a
  `host` kwarg; calls `install_security`; replaces the blanket `"/"`
  `StaticFiles` mount's index handling with an explicit `GET /` route that
  injects the token, followed by the same `StaticFiles` mount for every
  other static asset.
- **EDIT** `src/tools/bim/commands/serve/serve.py` — thread
  `host=self.params.host` into `create_app(...)`.
- **EDIT** `src/tools/bim/commands/serve/frontend/src/lib/api.ts` — read
  `window.__BUVIS_TOKEN__`; attach the `X-Buvis-Token` header in
  `patchZettel`, `execAction`, `openFile`.
- **EDIT (test retrofit, required by this PRD, not optional cleanup)**
  `tests/tools/bim/test_serve.py` — the `client` fixture's `TestClient(app)`
  call and its fixture file paths predate confinement/host-checking and will
  start failing once this PRD lands; see Risks & edge cases.

## Interfaces & contracts

### `serve/_security.py`

```python
TOKEN_HEADER = "X-Buvis-Token"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass
class AppState:
    default_directory: str
    archive_directory: str | None


def confine_path(file_path: str, app_state: AppState) -> Path:
    """Reject an empty file_path outright (HTTPException(403) — resolving
    "" falls back to the server's CWD, which must never be trusted by
    coincidence). Otherwise resolve file_path and assert it lives under
    default_directory or archive_directory. Raises HTTPException(403) on
    escape or an OSError from resolve() (circular symlink / permission
    error — NOT plain dangling symlinks, which resolve() does not raise
    on; a dangling or outside-root symlink is still caught by the
    is_relative_to(root) escape check below, not by this except clause).
    Never returns a path outside the allowed roots."""


def generate_token() -> str:
    """secrets.token_urlsafe(32) — URL-safe base64 alphabet, no HTML/JS
    string-literal escaping needed when interpolated into <script>."""


def require_token(request: Request) -> None:
    """FastAPI dependency. Reads request.headers.get(TOKEN_HEADER) — NOT
    request.headers[TOKEN_HEADER], which raises KeyError (uncaught ->
    500) when the header is absent; .get() returns None instead. Compares
    with secrets.compare_digest against request.app.state.buvis_token,
    guarding both sides against None first (compare_digest itself raises
    TypeError on a None argument). Raises HTTPException(401) on
    missing/mismatched token."""


def install_security(app: FastAPI, host: str) -> None:
    """Mints app.state.buvis_token = generate_token(). If host is in
    LOOPBACK_HOSTS, adds TrustedHostMiddleware(allowed_hosts=["127.0.0.1",
    "localhost", "::1"]). Otherwise adds it with allowed_hosts=["*"] and
    calls console.warning(...) naming the bind host and what stays
    unprotected (see Risks & edge cases — this is the "-H non-loopback"
    warning from the PRD)."""
```

`confine_path`'s allowed-roots list is built as
`[resolve(default_directory)] + ([resolve(archive_directory)] if
archive_directory else [])` — the PRD's explicit "guard the allowed-roots
list so a `None` archive doesn't crash confinement" risk is satisfied by
construction (the list comprehension skips `None` rather than resolving it).

### `serve/_routes.py` changes

- `get_zettel(file_path: str, request: Request)`: `fp =
  confine_path(file_path, request.app.state)` replaces `fp =
  Path(file_path)`; no other change.
- `patch_zettel(file_path: str, body: PatchBody, request: Request, _:
  None = Depends(require_token))`: `fp = confine_path(file_path,
  request.app.state)` replaces `fp = Path(file_path)`.
- `open_file(body: OpenBody, request: Request, _: None =
  Depends(require_token))`: `fp = confine_path(body.path,
  request.app.state)` replaces `fp = Path(body.path)`.
- `exec_action(action_name: str, body: ActionBody, request: Request, _:
  None = Depends(require_token))`: unchanged body, only the new
  `Depends(require_token)` parameter — confinement for the actual
  `file_path` happens per-handler in `_actions.py` (each handler needs the
  resolved `Path`, not just a rejection, for its own use — e.g.
  `handle_create_note`'s `.parent`).
- `get_query(name: str)`, `exec_query(name: str, request: Request)`: add a
  guard **before** calling `resolve_query_file(name, ...)`:
  ```python
  if name.endswith((".yaml", ".yml")):
      raise HTTPException(status_code=404, detail=f"Unknown query: {name}")
  ```
  `resolve_query_file` (`buvis.pybase.zettel.infrastructure.query.query_spec_parser`)
  treats any `name_or_path` ending in `.yaml`/`.yml` as a raw filesystem
  path and returns `Path(name_or_path)` with **zero** confinement — fine
  for its other caller (`cli.py`'s trusted local `bim query --file ...`,
  and `shared/query_paths.py`), wrong for this HTTP surface. The route's
  `{name}` segment can never contain `/` (Starlette's `StringConvertor`
  regex is `[^/]+`), so this single suffix check is sufficient to force
  every HTTP-facing query lookup through the by-name config-dir search
  instead of the raw-path branch — no change needed inside the shared
  library function, and the CLI's existing "pass a query file path"
  convenience is untouched.
- `list_queries`, `exec_adhoc`, `health`: **no change** — no client-supplied
  path at all (adhoc queries are `POST`ed as an already-parsed spec dict,
  not a file path).
- None of the routes above gain `require_token` — see Risks & edge cases
  for why `GET`/query routes stay outside `require_token`'s scope.

### `serve/_actions.py` changes

Every handler gets one `confine_path` call before its existing body, with
one deliberate exception for the empty-`file_path` branch in
`handle_create_note`:

```python
async def handle_patch(file_path, args, app_state):
    fp = confine_path(file_path, app_state)
    ...  # repo.find_by_location(str(fp)) instead of str(Path(file_path))

async def handle_sync_note(file_path, args, app_state):
    fp = confine_path(file_path, app_state)
    ...  # SyncNoteParams(paths=[fp], ...)

async def handle_create_note(file_path, args, app_state):
    directory = confine_path(file_path, app_state).parent if file_path \
        else Path(str(app_state.default_directory))
    ...  # unchanged below

async def handle_archive(file_path, args, app_state):
    fp = confine_path(file_path, app_state)
    ...  # ArchiveNoteParams(paths=[fp])

async def handle_open(file_path, args, app_state):
    fp = confine_path(file_path, app_state)
    open_in_os(fp)
    ...

async def handle_format(file_path, args, app_state):
    target = confine_path(file_path, app_state)
    ...  # FormatNoteParams(paths=[target], path_output=target) — unchanged

async def handle_delete(file_path, args, app_state):
    fp = confine_path(file_path, app_state)
    ...  # DeleteNoteParams(paths=[fp])

async def handle_import(file_path, args, app_state):
    fp = confine_path(file_path, app_state)
    ...  # ImportNoteParams(paths=[fp], ...) — see Risks & edge cases
```

`handle_create_note`'s `if file_path:` guard must stay *before*
`confine_path`, not after: an empty string resolves to the current working
directory, which is never under `default_directory`, so calling
`confine_path("", app_state)` unconditionally would 403 the legitimate
"create at the vault root" case that `file_path == ""` represents today.

### `serve/_app.py` changes

```python
def create_app(default_directory: str, archive_directory: str | None = None,
                *, host: str = "127.0.0.1") -> FastAPI:
    app = FastAPI(title="bim dashboard")
    app.state.default_directory = default_directory
    app.state.archive_directory = archive_directory
    install_security(app, host=host)          # NEW — mints token, adds TrustedHostMiddleware

    app.include_router(api_router, prefix="/api")
    app.include_router(sse_router, prefix="/api")
    ...  # startup/shutdown handlers unchanged

    if STATIC_DIR.is_dir() and any(STATIC_DIR.iterdir()):
        index_path = STATIC_DIR / "index.html"

        @app.get("/", include_in_schema=False)          # NEW — registered before the mount
        async def _index() -> HTMLResponse:
            html = index_path.read_text(encoding="utf-8")
            token_script = f'<script>window.__BUVIS_TOKEN__ = "{app.state.buvis_token}";</script>'
            return HTMLResponse(html.replace("</head>", f"{token_script}</head>", 1))

        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    else:
        ...  # "Frontend not built" fallback — unchanged, no token to inject
    return app
```

The explicit `GET /` route must be registered *before* the `StaticFiles`
mount at `"/"` — Starlette matches routes in registration order, so the
specific route wins for the exact root path and the mount still serves
every other static asset unchanged. `index_path.read_text()` re-reads the
file on every request rather than caching it — this is a local personal
dashboard, not a high-QPS server; add caching only if it measurably
matters.

### `serve/serve.py` change

`create_app(self.params.default_directory, self.params.archive_directory,
host=self.params.host)` — one added keyword argument.

### `frontend/src/lib/api.ts` change

```ts
const TOKEN = (window as unknown as { __BUVIS_TOKEN__?: string }).__BUVIS_TOKEN__ ?? '';

// in patchZettel, execAction, openFile only — add to the existing headers object:
headers: { 'Content-Type': 'application/json', 'X-Buvis-Token': TOKEN }
```

`fetchQueries`, `fetchQuerySpec`, `execQuery`, `execAdhoc`, `fetchZettel`
are unchanged (no token attached — matches the server-side scope above).

## Data flow

**Startup:** `CommandServe.execute()` → `create_app(..., host=...)` →
`install_security` mints `app.state.buvis_token` and adds
`TrustedHostMiddleware` before any router is reachable.

**Page load:** browser `GET /` → `TrustedHostMiddleware` checks `Host` →
explicit `_index` route reads `index.html` off disk, splices in a
`<script>` setting `window.__BUVIS_TOKEN__`, returns it. Frontend JS reads
that global once and holds it in `api.ts`'s module-level `TOKEN` constant.

**Mutating call (e.g. patch a note):** browser `PATCH /api/zettels/...`
with `X-Buvis-Token` header → `TrustedHostMiddleware` (Host check) →
`require_token` dependency (401 if missing/wrong, before the handler body
runs) → `confine_path` inside the handler (403 if the resolved path escapes
the vault/archive, before any read/write) → existing
`atomic_write_text`/`Command*` write path (untouched by this PRD — 00041
already repointed these writes to atomic writes).

**Read call (e.g. fetch a note):** browser `GET /api/zettels/{path}` →
`TrustedHostMiddleware` (Host check) → `confine_path` (403 before the file
is touched) → response. No token required (see Risks & edge cases for why).

## Reuse inventory

- `Path.resolve().is_relative_to(root)` — the exact confinement pattern
  already used in `src/tools/bim/commands/doc/audit/walker.py:22`
  (`_is_contained`, private to that module, handles `OSError` — a circular
  symlink loop or a permission-denied stat, NOT a plain dangling symlink,
  which `resolve()` does not raise on — by treating it as out-of-bounds;
  `confine_path` follows the same `try/except OSError` shape) and
  `src/tools/bim/commands/doc/shared/settings_models.py:79` (a Pydantic
  validator confining `business_root` under `$HOME`). Neither is
  importable/reusable as-is (one is module-private, the other is a
  Pydantic validator method), so `confine_path` is a new function, but its
  shape is a direct copy of an established, already-reviewed project
  pattern rather than a novel one.
- `AppState` dataclass — already exists in `_actions.py`; this design moves
  it to `_security.py` rather than defining a second one, since `_actions.py`
  needs to import it from `_security.py` and `_security.py` cannot import
  from `_actions.py` (Foundation layer, Phase 0, no deps per the PRD's
  Dependency Graph).
- `atomic_write_text` (from `buvis.pybase.filesystem`, landed in PRD 00041)
  — already wired into every write path this PRD's handlers use
  (`patch_zettel`, `handle_format`, `sync_note.py`, `format_note.py`,
  `import_note.py`); this design does not touch write mechanics, only adds
  confinement/auth in front of them.
- `console.warning` (`buvis.pybase.adapters.console`) — the project's
  existing user-facing-output channel; used for the non-loopback-bind
  warning instead of a bare `print`.
- Greps tried beyond the two hits above (nothing else found): `rg -n
  "TrustedHostMiddleware|X-Buvis-Token|require_token|secrets.token"
  src/` (empty — confirmed the search itself works via a control hit on
  `is_relative_to`, which returned results); `rg -n "class.*Middleware"
  src/tools/bim` (empty); no existing per-request auth/token mechanism
  anywhere in the repo to reuse.

## Alternatives considered

1. **Smallest-diff option — confine only the two most obviously dangerous
   routes (`PATCH`/`DELETE` action)**, skip `GET` and the other action
   handlers. Rejected: the PRD's own Exit Criteria is a literal grep (`rg
   "Path\(file_path\)"` finds nothing unconfined in `serve/`) and its
   headline example is a `GET` (`GET /api/zettels//etc/passwd`) — leaving
   `GET` open reopens the exact vulnerability the PRD leads with.
2. **A single blanket middleware that inspects and confines every request
   before routing**, instead of a per-handler helper call. Rejected: the
   client-supplied path arrives in at least three different shapes across
   routes (a path parameter, `body.path`, `body.file_path`), so a
   route-agnostic middleware can't reliably locate "the path" without
   route-specific knowledge — it would end up re-implementing per-route
   dispatch inside the middleware anyway. A shared helper called explicitly
   at each entry point is what makes the PRD's grep-based Exit Criteria
   possible in the first place.
3. **Chosen — one shared `confine_path` helper, called individually at
   every entry point**, plus a dependency-injected `require_token` for
   mutating routes. Slightly more call sites than option 1, but each one is
   one line, auditable by the same grep the PRD's Exit Criteria already
   specifies, and consistent with the confinement pattern already used
   twice elsewhere in this codebase (Reuse inventory).
4. **Session-cookie-based auth** instead of a printed/injected token.
   Rejected: no login UI or user management exists or is wanted for a
   single-user localhost tool; the project already settled on a
   `X-Buvis-Token` header in the 2026-07-10 backlog review (see project
   memory), so this design implements that existing decision rather than
   reopening it.

## Risks & edge cases

- **`tests/tools/bim/test_serve.py` needs retrofitting, not just
  additions.** Two independent reasons the *existing* tests will start
  failing once this PRD lands, both must be fixed in the same PRD:
  1. The `client` fixture builds `TestClient(app)` with no `base_url`;
     httpx's `TestClient` defaults to `Host: testserver`, which
     `TrustedHostMiddleware` will reject (400) once Phase 2 lands — every
     existing test in the file uses this fixture. Fix: `TestClient(app,
     base_url="http://localhost")` (or `127.0.0.1`).
  2. Several fixtures use paths that are not under the fixture's
     `default_directory="zettels"` (e.g. `test_patch_zettel_metadata`'s
     `real_file = tmp_path / "note.md"`, and the bare relative
     `"note.md"`/`"missing.md"` in `test_get_zettel`/
     `test_get_zettel_missing_returns_404`). Once Phase 1's `confine_path`
     lands, these 403 instead of exercising the intended path. Fix: change
     the shared `client` fixture's `default_directory` to
     `str(tmp_path / "zettels")` (a real absolute path whose last path
     component is still literally `"zettels"`) and create fixture files
     under it. This is not a no-op rename: `TestServeQueries::test_exec_query`
     and `TestServeQueries::test_exec_adhoc` both assert
     `query_spec.source.directory == "zettels"` (the bare literal string,
     sourced from `_get_directory` returning
     `str(request.app.state.default_directory)`) — changing the fixture's
     `default_directory` value breaks these two currently-passing
     assertions too. Update both to compare against
     `str(tmp_path / "zettels")` instead of the literal `"zettels"` in the
     same retrofit; do not change `default_directory` without also fixing
     these two.
- **`handle_import`'s `file_path` is now vault/archive-confined**, narrowing
  the WebUI's "import" action to same-vault-or-archive sources (previously
  unconfined — could import from anywhere the server process could read).
  This is a deliberate, in-scope tightening (the PRD's Exit Criteria grep
  would otherwise flag this one call site as the sole unconfined survivor),
  and it does not affect the desktop `bim import-note` CLI command, which
  is a fully separate call path (`cli.py` → `CommandImportNote` directly,
  never through `serve/_actions.py`) already running with the user's own
  full local access. Flagged explicitly since it is a user-visible
  behavior change to the WebUI's import action, not purely a security fix.
- **Success Metric 2 ("rejected before any filesystem access") is read as
  an ordering guarantee for whichever check gates a given route, not as
  "every route requires a token."** The Feature's own Behavior text scopes
  the token to "`/api/*` mutating routes"; this design keeps `GET` routes
  token-free and relies on `confine_path` (path safety) +
  `TrustedHostMiddleware` (blocks the DNS-rebinding vector the PRD's
  Problem Statement calls out by name) for read protection. Flagged as a
  **Question** for review — if the intent was truly universal token
  coverage, `fetchZettel`/`fetchQueries`/`execQuery`/`execAdhoc` in
  `api.ts` would need the header too, which is a larger frontend surface
  than the PRD's Structural Decomposition names.
- **`/api/queries/{name}/exec` and `/api/queries/_adhoc` stay outside
  `require_token`'s scope** — deliberately: neither takes a client-supplied
  filesystem path (they read the trusted `default_directory`). Flagged as
  the same Question above: acceptable, or should every `POST` require the
  token uniformly for simplicity/defense-in-depth?
- **Non-loopback bind (`-H 0.0.0.0`) widens `allowed_hosts` to `"*"`**,
  because a fixed loopback allowlist would reject every request in the
  already-supported LAN-access mode (browsers send the LAN IP/hostname as
  `Host`, never `"127.0.0.1"`). This means the DNS-rebinding defense is
  void for LAN-bound instances, and `GET` reads (token-free by design,
  above) remain fully open to anyone who can reach the port in that mode —
  identical exposure to today, not a regression, but `install_security`'s
  warning text must say this plainly (not just "network exposure") so a
  LAN-mode operator understands writes are token-gated but reads are not.
- **IPv6 loopback (`[::1]`) is a known limitation, not a bug to fix here.**
  Starlette's `TrustedHostMiddleware` derives the comparison host via
  `headers.get("host", "").split(":")[0]`, which mis-parses an IPv6-literal
  `Host: [::1]:8000` header (yields `"["`, not `"::1"`). Any browser hitting
  `bim serve` via `http://[::1]:8000` gets a 400 even with `"::1"` in
  `allowed_hosts`. This is upstream Starlette behavior, not introduced by
  this PRD; noted so it isn't mistaken for a regression later. IPv4
  `127.0.0.1` (the actual default) is unaffected.
- **Token safe to interpolate into `<script>` without HTML/JS escaping** —
  `secrets.token_urlsafe(32)`'s output alphabet is `[A-Za-z0-9_-]` only, so
  it cannot break out of the double-quoted JS string literal or the
  surrounding `<script>` tag. No escaping helper is added; if the token
  generator ever changes to a charset that includes `"`, `<`, or `` ` ``,
  this assumption breaks and would need revisiting.
- **Likely next changes this design should not box in:** (a)
  `dev/local/prds/backlog/00067-postup-serve-v1.md` already models its own
  confinement on `confine_path`'s shape ("00042 posture") — keep the
  signature (`file_path: str, app_state) -> Path`, raising `HTTPException`
  on rejection) stable across the batch; (b) a future audit log of
  confinement rejections would hook naturally at `confine_path`'s
  `HTTPException(403)` raise points; (c) if `bim serve` ever needs
  multi-user auth, `require_token`'s single-shared-secret-on-`app.state`
  model would need replacing with per-session tokens — keeping token
  storage on `app.state` rather than baked into individual route
  signatures is what makes that swap contained to `_security.py` later.

## Test strategy outline

- **Unit (`confine_path`, Phase 0):** in-vault absolute path → returns the
  resolved `Path`; `/etc/passwd` → 403; `<vault>/../../etc/passwd` → 403;
  a symlink created under a `tmp_path` vault pointing outside it → 403
  (via `os.symlink`); `archive_directory=None` does not raise while
  building the roots list; a path under `archive_directory` → ok.
- **Integration (Phase 1):** for `GET`/`PATCH /api/zettels/{path}`, `POST
  /api/open`, and each `POST /api/actions/{name}` (`patch`, `sync_note`,
  `create_note`, `archive`, `open`, `delete`, `format`, `import`): an
  absolute out-of-vault `file_path` → 403 and the underlying
  Command/UseCase is never invoked (assert-not-called on the mocked
  command class, matching the existing test file's mocking style). Retrofit
  `test_serve.py`'s `client` fixture and in-vault fixture paths per Risks
  above — this is required for the *existing* tests to keep passing, not
  new coverage.
- **Integration (Phase 2):** `TrustedHostMiddleware` — request with a
  foreign `Host` header → 400; default-loopback bind with a matching Host
  → passes through unaffected. `require_token` — a mutating route without
  `X-Buvis-Token` → 401; with the token read back from
  `app.state.buvis_token` in the test → 200. Token injection — `GET /`
  response body contains `window.__BUVIS_TOKEN__ = "<value>"` matching
  `app.state.buvis_token` exactly. Non-loopback host → `allowed_hosts ==
  ["*"]` and `console.warning` fired (via the console adapter's existing
  `capture()` context manager).
- **Frontend (`api.ts`):** no new test infrastructure — matches the
  already-accepted project decision that `bim serve`'s frontend has no
  vitest/playwright harness. The token-attachment wiring is verified only
  indirectly via the server-side `require_token` assertions above (a
  request without the header 401s; the frontend attaches it, so a real
  browser session succeeds), plus a manual WebUI smoke test after merge —
  matching the PRD's own Risks section verbatim.

## Review log

- non-blocker (dispatch 1): confine_path's OSError branch is triggered by
  circular-symlink loops / permission errors, not "broken" (dangling)
  symlinks — fixed in this doc (wording only, no behavior change).
- question (dispatch 1): is token coverage correctly scoped to mutating
  routes only (this design's reading), or should every `/api/*` route
  including reads require it? Self-flagged in Risks & edge cases; left
  open for `/plan-tasks`/implementation to resolve (default: the narrower
  reading already documented here, matching the PRD's Feature Behavior
  text).
dispatch 1 (claude): cardinal-sin 0, blocker 4, non-blocker 1, question 1
