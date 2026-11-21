---
design: skip
default_model: opus
model_tier_rationale: security change across bim serve routes plus a token handoff for the remote web UI; needs judgment on the handoff shape
---

# bim serve on a non-loopback bind must require the token for reads

Source: agoge run `docs/dev/project-management/audit-results/agoge-2026-11-10.md` (2026-11-10), finding 10 of 13, LOW, lane trudy. Predates PRDs 00122/00123.

## Overview

### Problem Statement

On a non-loopback bind (`bim serve -H 0.0.0.0`), the routes in `_routes.py` and `_sse.py` answer note, query and event reads with no `X-Buvis-Token`, and any `Host` header is accepted. The startup warning prints the token to stdout and already admits the open reads. Anyone on the network reads the vault while it is exposed. It needs an explicit `-H 0.0.0.0`, which the operator chooses. Stable.

### Target Users

bim users who serve the web UI on a LAN or remote interface.

### Success Metrics

- On a 0.0.0.0 bind, `GET /api/zettels/<note>`, `/api/queries`, `/api/events` and `/api/health` without the token return 401.
- The startup warning no longer prints the token.
- The remote web UI can still obtain the token through a documented handoff.
- Loopback behavior is unchanged: traversal returns 403, mutating routes without a token return 401, a foreign Host returns 400.

## Functional Decomposition

### Capability: Token on reads off-loopback

#### Feature: Require `X-Buvis-Token` on every `/api` read when bound off-loopback

- Chosen option: agoge option 1. Decide the token handoff for the remote web UI (for example a one-time URL or an explicit flag) as part of this PRD, and document it.

#### Feature: Stop printing the token in the startup warning

## Structural Decomposition

- `src/tools/bim/commands/serve/_routes.py`
- `src/tools/bim/commands/serve/_sse.py`
- `src/tools/bim/commands/serve/_security.py`
- `docs/source/tools/bim.rst`, `CHANGELOG.md`

## Implementation Phases

### Phase 1: Core

- [ ] bim serve: enforce the token on reads off-loopback - Acceptance: the repro below returns 401 without the token.
- [ ] bim serve: remove the token from the warning and add the handoff.
- [ ] Docs and CHANGELOG `Fixed` entry (security).

## Test Strategy

### Critical Scenarios

Regression test, failing against current code first. Evidence from the run, verbatim:

```
- On the 0.0.0.0 run, with no token: `GET /api/zettels/<note>` returned 200 with the full note body. `GET /api/queries` returned 200 and leaked absolute paths. `GET /api/events` and `GET /api/health` returned 200.
- `Host: evil.example` returned 200 on 0.0.0.0, and 400 on loopback.
- On loopback, path confinement held: every traversal variant returned 403, and mutating routes without a token returned 401.
```

## Risks

- The remote web UI has no token handoff today; without one this change locks out legitimate remote use.
- Refusing non-loopback without `--insecure` (agoge option 2) was not chosen; it would break LAN use.
