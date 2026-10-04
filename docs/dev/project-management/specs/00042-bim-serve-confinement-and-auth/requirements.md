# bim serve: confine paths and require local auth

<!-- requirements; migrated from PRD 00042 flat file -->

## Overview

### Problem Statement
`bim serve` (the FastAPI dashboard for the personal zettelkasten) is **unauthenticated and its path parameters are never confined to the vault**, so it exposes arbitrary-file read, overwrite, and delete on the user's home directory:

- `GET /api/zettels/{file_path:path}` → `Path(file_path)`, only `is_file()` checked, returns the file body (`src/tools/bim/commands/serve/_routes.py:160-174`). `GET /api/zettels//etc/passwd` leaks it.
- `PATCH /api/zettels/{file_path:path}` → `fp.write_text(formatted)` on any path (`_routes.py:136-157`).
- `POST /api/actions/delete` → `DeleteNoteParams(paths=[Path(file_path)])`, no confinement (`_actions.py:135-144`); same for `open`, `format`, `archive`, `import`, `patch`.
- The app wires **no middleware at all** — no auth, no `TrustedHostMiddleware`, no CORS control (`_app.py:14-41`) — and `bim serve -H 0.0.0.0` is available (`cli.py:522-543`).

At the default `127.0.0.1` bind, an attacker still reaches it via DNS-rebinding from any web page the user visits (no Origin/Host check). With `-H 0.0.0.0`, any host on the LAN has unauthenticated read/overwrite/delete of `$HOME`.

### Target Users
Bob (running the bim web UI on his machine / LAN) and anyone else running `bim serve` from the published package.

### Success Metrics
- 0 endpoints accept a path outside `{default_directory, archive_directory}`.
- A request without the local token, or with a non-allowed Host header, is rejected before any filesystem access.
- Existing WebUI happy-path flows still work unchanged.

## Functional Decomposition

### Capability: Path confinement
Every request-derived filesystem path is resolved and asserted to live under the vault or archive before any read/write/delete/open.

#### Feature: confine_path helper
- **Description**: resolve a request path and reject anything not under an allowed root.
- **Inputs**: `file_path: str`, allowed roots from `app.state` (`default_directory`, `archive_directory`).
- **Outputs**: a resolved `Path`, or `HTTPException(403)`.
- **Behavior**: `resolved = Path(file_path).expanduser().resolve()`; require `resolved.is_relative_to(root)` for some allowed root; else 403. Applied in GET/PATCH/`open`/all action handlers.

### Capability: Local access control
The server refuses requests that are not same-machine and token-bearing.

#### Feature: TrustedHost + loopback + token
- **Description**: block cross-origin/rebinding and unauthenticated callers.
- **Inputs**: request Host header; a per-run local token; the bind host.
- **Outputs**: 400/401 on failure; pass-through on success.
- **Behavior**: add `TrustedHostMiddleware` (allow `localhost`, `127.0.0.1`, `[::1]`); generate a random token at startup, require it as the `X-Buvis-Token` header on `/api/*` mutating routes, and inject it into the served `index.html`; warn loudly when `-H` is non-loopback.
