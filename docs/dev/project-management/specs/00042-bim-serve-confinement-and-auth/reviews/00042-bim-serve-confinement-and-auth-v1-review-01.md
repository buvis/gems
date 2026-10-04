---
prd: dev/local/prds/wip/00042-bim-serve-confinement-and-auth-v1.md
review: 1
date: 2026-08-15
head_sha: 7d362cc4bdc3d038826aa325fd1fa0ea0665ab98
codex_thread_id: 01a005ef-b58e-76c1-add0-406f58c957f4
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00042-bim-serve-confinement-and-auth-v1

Diff range: `cc11c7e355fdc0126b1546d92524471ad8b30410..7d362cc4bdc3d038826aa325fd1fa0ea0665ab98`

codex_rung_guard: not fired

## Review Summary

Reviewed: 5 completed tasks
PRDs checked: 00042-bim-serve-confinement-and-auth-v1

Cycle 1, full review of the PRD's entire work range. All four lenses ran:
Alice (consensus, implementation-aware), Blake (blind, PRD-only), Bob
(codex — doubt rubric D1-D5 + de-slop), Carl (gemini — frontend/design).

### Agent Status

- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available
- Carl: ✅ Available

### Notes on method

- The context file labels the diff scope "incremental" only because the diff
  base was passed explicitly via `--since`. The work was committed directly on
  `master`, so `gather-context.sh`'s branch-base detection would have produced
  an empty diff. This was a **full** cycle-1 review of `work_start_sha..HEAD`.
- The mechanical-facts block could not be appended to the context file
  (`block_devlocal_redirects.py` hard-blocks shell redirects into `dev/local/`).
  It was inlined verbatim into every implementation-aware prompt instead
  (Alice, Bob, Carl), which carries the same guarantee.
- Blake's `File:` paths were normalized from absolute to repo-relative before
  consolidation so same-file findings could merge across reviewers. No content
  was changed.

## Consolidated Findings

35 raw consolidated rows. The consolidator under-merged several rows because
reviewers cited the same defect at different line-number suffixes; the
orchestrator's effective merge is given below, with the raw table following.

### Effective consensus after orchestrator merge

- **[3/4] 🔴 Unauthenticated ad-hoc query surface — arbitrary code execution and
  arbitrary-directory read.** `POST /api/queries/_adhoc` carries no
  `require_token` and `_run_query` only injects `default_directory` when
  `spec.source.directory is None`, so the caller controls the traversal root.
  The same client-supplied spec drives `filter`, `columns`, `lookups`, and
  `expand` through `get_evaluator()`, which is `python_eval` —
  `eval(compiled, {"__builtins__": __builtins__, ...})`. Found by: Bob (🔴 RCE),
  Blake (🔴 directory escape, proved live), Alice (🟠 directory escape, verified
  live). **Orchestrator-verified** by direct read of
  `bim/dependencies.py:44-47`, `expression_engine.py:281-300`, and
  `query_zettels_use_case.py:33-58`. Breaks PRD Success Metric 1.
- **[3/4] 🔴 Non-loopback bind hands the token to any caller.**
  `install_security` sets `allowed_hosts=["*"]` off loopback, and the
  unauthenticated `GET /` returns `window.__BUVIS_TOKEN__` in the page, so any
  LAN host fetches `/`, reads the token, and gets authenticated write/delete.
  The warning text's claim "writes still require it" is therefore false.
  Found by: Blake (🔴), Alice (🟠, verified live), Bob (🟠).
- **[3/4] 🟠 `confine_path` drops the PRD-specified `.expanduser()`** on both the
  request path and the allowed roots, while `_actions.py:92,93,150` expands the
  same directories. Safe today only because `cli.py` pre-expands; any other
  `create_app` caller passing `~/zettelkasten` gets roots of `<cwd>/~/…` and
  403s every legitimate path. Fail-closed but a silent total lockout.
  Found by: Blake (🟠), Bob (🟡), Alice (⚪).
- **[2/4] 🟠 No CHANGELOG entry** for five `feat(bim)` commits with user-visible
  effects. `rules/changelog.md` marks this BLOCKING. Found by: Alice, Blake.
  **Orchestrator-verified**: `[Unreleased]` holds only 00041's items.
- **[2/4] 🟡 `require_token` returns 500, not 401, on a non-ASCII header.**
  `secrets.compare_digest` raises `TypeError` on non-ASCII str and Starlette
  latin-1-decodes headers. Fails closed, but a raw stack trace reaches the
  user. Found by: Alice, Blake (both proved).
- **[2/4] 🟡 Docs unchanged** — `docs/source/tools/bim.rst:211` still advertises
  `-H 0.0.0.0` with no mention of token auth, the Host allowlist, or LAN read
  exposure. Found by: Alice, Blake. **Orchestrator-verified**.
- **[2/4] 🟡 Read surface stays unauthenticated / design Question unresolved.**
  `GET /api/zettels/{path}`, `GET /api/queries*`, `POST /api/queries/{name}/exec`
  and `GET /api/events` carry no token. The design doc self-flagged this as an
  open Question and never resolved it. Found by: Blake (🟠), Alice (🟡).

### Downgraded / discarded at the gate

- **Blake 🟠 "served frontend bundle is stale, sends no token" → downgraded to
  ⚪ (dev-only).** **Orchestrator-verified**: `src/tools/bim/commands/serve/static/`
  is gitignored (`.gitignore:74`) and `hatch_build.py:74-96` runs `npm ci` +
  `npm run build` and replaces `static/` at package build time, so a stale
  bundle cannot ship. The residue is real but local: a developer serving from
  the working tree without rebuilding gets 401s with no diagnostic.
- **Blake 🟡 "`::1` in `LOOPBACK_HOSTS` can never match" → discarded, settled by
  design.** The design doc documents this verbatim as a known upstream Starlette
  limitation (`headers.get("host","").split(":")[0]` mis-parses an IPv6 literal),
  explicitly "not a bug to fix here".
- **Blake 🟡 "`handle_import` confinement breaks importing outside files" →
  discarded, settled by design.** The design doc records this as a deliberate,
  in-scope tightening of the WebUI import action, with the CLI path unaffected.
- **Carl 🟡 "`_serialize_dict` duplicates `_serialize_row`" → discarded,
  out of diff.** Both functions are pre-existing (`_routes.py:65,77`) and
  untouched by this range.
- **Blake ⚪ "`handle_archive` builds `Path(str(None))`" → noted, out of diff.**
  Real, but the line is pre-existing and not part of this PRD's change.

### Raw consolidated table

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🔴 | `POST /api/queries/_adhoc` still accepts a client-supplied filesystem path: `_run_query` only injects `default_directory` when `spec.source.directory is None`. Verified live. PRD Success Metric 1 unmet. | src/tools/bim/commands/serve/_routes.py:129-133 | general | ALICE, BLAKE |
| [2/4] | 🟠 | `confine_path` drops the PRD-specified `.expanduser()` on both the input path and the allowed roots, while `_actions.py:92,93,150` expands the same directories. | src/tools/bim/commands/serve/_security.py:45-53 | 1 | ALICE, BLAKE |
| [2/4] | 🟡 | `require_token` raises `TypeError` (uncaught 500) when the token header carries a byte > 0x7F, instead of the documented 401. | src/tools/bim/commands/serve/_security.py:74-79 | 1 | ALICE, BLAKE |
| [1/4] | 🔴 | Non-loopback bind disables the specified Host allow-list (`allowed_hosts=["*"]`), so DNS-rebinding is live and the attacker page reads the token from `GET /`. | src/tools/bim/commands/serve/_security.py | Phase 2 | BLAKE |
| [1/4] | 🔴 | `POST /api/queries/_adhoc` remains unauthenticated and feeds client-controlled expressions to `python_eval` with full builtins, enabling arbitrary code execution. | src/tools/bim/commands/serve/_routes.py:129 | 2 | BOB |
| [1/4] | 🟠 | In non-loopback mode the token is handed to anyone; the warning text's "writes still require it" is false. | src/tools/bim/commands/serve/_security.py:92-99 | 4 | ALICE |
| [1/4] | 🟠 | No CHANGELOG.md entry for this PRD's five user-visible `feat(bim)` commits. `rules/changelog.md` marks this BLOCKING. | CHANGELOG.md | general | ALICE |
| [1/4] | 🟠 | The served frontend bundle is stale and sends no token; nothing catches source/bundle skew. | src/tools/bim/commands/serve/static/_app/immutable/nodes/2.DlOHyigm.js | Phase 2 | BLAKE |
| [1/4] | 🟠 | Whole read surface is unauthenticated (`GET /api/zettels`, queries, `/api/events`). | src/tools/bim/commands/serve/_routes.py | Phase 2 | BLAKE |
| [1/4] | 🟠 | Ad-hoc `source.directory` and `lookups[].source.directory` reach repository traversal without confinement. | src/tools/bim/commands/serve/_routes.py:130 | 2 | BOB |
| [1/4] | 🟠 | Non-loopback mode combines `allowed_hosts=["*"]` with an anonymous `GET /` that returns the bearer token. | src/tools/bim/commands/serve/_app.py:40 | 4 | BOB |
| [1/4] | 🟡 | `docs/source/tools/bim.rst` `bim serve` section unchanged — no token auth, allowlist, or LAN exposure documented. | docs/source/tools/bim.rst:211 | general | ALICE |
| [1/4] | 🟡 | All 8 action-handler tests assert only the reject branch; no in-vault success case. | tests/tools/bim/test_serve.py:418-521 | 3 | ALICE |
| [1/4] | 🟡 | Test duplication: `test_matching_loopback_host_passes_through` and `test_none_archive_directory_does_not_raise_for_that_reason` duplicate existing coverage. | tests/tools/bim/test_serve.py:566-614 | 4 | ALICE |
| [1/4] | 🟡 | The design's self-flagged open Question (token scope on read routes) was never resolved. | src/tools/bim/commands/serve/_routes.py:117,130,171 | general | ALICE |
| [1/4] | 🟡 | `::1` in `LOOPBACK_HOSTS` can never match (Starlette host parsing). | src/tools/bim/commands/serve/_security.py | Phase 2 | BLAKE |
| [1/4] | 🟡 | Token injection only covers `GET /`; `GET /index.html` is served raw by the mount. | src/tools/bim/commands/serve/_app.py | Phase 2 | BLAKE |
| [1/4] | 🟡 | No CHANGELOG entry for a breaking behavior change. | CHANGELOG.md | general | BLAKE |
| [1/4] | 🟡 | Docs unchanged for `bim serve`. | docs/source/tools/bim.rst | general | BLAKE |
| [1/4] | 🟡 | `handle_import` confines the import *source*, so importing an outside file always 403s in the WebUI. | src/tools/bim/commands/serve/_actions.py | Phase 1 | BLAKE |
| [1/4] | 🟡 | `confine_path` omits the PRD-required `expanduser()`. | src/tools/bim/commands/serve/_security.py:52 | 1 | BOB |
| [1/4] | 🟡 | No valid-token success tests exercise `/api/open` or `/api/actions/*`. | tests/tools/bim/test_serve.py:409 | 2 | BOB |
| [1/4] | 🟡 | Query-name rejection and resolution duplicated in `get_query` and `exec_query`. | src/tools/bim/commands/serve/_routes.py:101 | 2 | BOB |
| [1/4] | 🟡 | `test_none_archive_directory_does_not_raise_for_that_reason` duplicates `test_allows_real_in_vault_path`. | tests/tools/bim/test_serve_security.py:90 | 1 | BOB |
| [1/4] | 🟡 | `_serialize_dict` is identical to `_serialize_row`. | src/tools/bim/commands/serve/_routes.py:77 | general | CARL |
| [1/4] | ⚪ | `_index` regressions: missing `index.html` → 500 not 404; silent no-op `</head>` replace; drops `include_in_schema=False`. | src/tools/bim/commands/serve/_app.py:40-45 | 4 | ALICE |
| [1/4] | ⚪ | Pre-commit guard glob widened from `!*/serve/*` to `!**/serve/**`, exempting any tool's `serve/` subtree from the framework-import guard. | .pre-commit-config.yaml:23 | general | ALICE |
| [1/4] | ⚪ | The `.yaml`/`.yml` 404 guard is duplicated verbatim in `get_query` and `exec_query`. | src/tools/bim/commands/serve/_routes.py:102-103,118-119 | 2 | ALICE |
| [1/4] | ⚪ | `handle_archive` builds `Path(str(app_state.archive_directory))`; with `None` that is the literal path `None`. | src/tools/bim/commands/serve/_actions.py | Phase 1 | BLAKE |
| [1/4] | ⚪ | Check-then-act between `confine_path` and the write/open call (symlink swap race). | src/tools/bim/commands/serve/_routes.py | Phase 1 | BLAKE |
| [1/4] | ⚪ | Token injection is a blind `html.replace("</head>", ..., 1)` that silently no-ops if the tag is absent. | src/tools/bim/commands/serve/_app.py | Phase 2 | BLAKE |
| [1/4] | ⚪ | `install_security(app, host)` does not match the PRD's declared export `install_security(app, allowed_hosts)`. | src/tools/bim/commands/serve/_security.py | Phase 2 | BLAKE |
| [1/4] | ⚪ | `GET /api/events` streams absolute vault paths with no token and no test coverage; `handle_open` skips the `is_file()` check. | src/tools/bim/commands/serve/_sse.py | general | BLAKE |
| [1/4] | ⚪ | The explicit index handler raises an uncaught `FileNotFoundError` when a non-empty static dir lacks `index.html`. | src/tools/bim/commands/serve/_app.py:42 | 4 | BOB |
| [1/4] | ⚪ | Cannot statically verify: tests pass and the built WebUI completes token-bearing flows. | N/A | general | BOB |

## Alice

Implementation-aware consensus lens. Ran with `Read, Bash`; independently ran
`uv run pytest tests/tools/bim` (1120 passed), `uv run mypy` (clean),
`uv run ruff check` (clean), `npm run build` (succeeds, built bundle contains
`X-Buvis-Token`), and live `TestClient` probes that confirmed the adhoc
directory escape, the non-loopback token disclosure, and the non-ASCII-header
500. Full findings in `dev/local/tmp/alice-output-00042-01.txt`.

12 findings: 3 🟠, 5 🟡, 4 ⚪.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: fail
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: pass

## Blake

Blind lens — PRD-only prompt, no diff, no design doc, no review history. Found
the code himself and proved each claim with `TestClient`. Full findings in
`dev/local/tmp/blake-output-00042-01.txt`.

16 findings: 2 🔴, 3 🟠, 6 🟡, 5 ⚪. Confirmed the Phase 1 exit criterion holds
(the only remaining `Path(file_path)` in `serve/` is inside `confine_path`).

B1: fail
B2: pass
B3: fail
B4: pass
B5: fail
B6: pass
B7: pass
B8: pass
B9: fail
B10: fail
B11: pass
B12: pass
B13: pass
B14: fail
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens (rubric D1-D5) + de-slop, run on codex in a static-only sandbox.
Full findings in `dev/local/tmp/bob-output-00042-01.txt`. Sole reviewer to
identify the `python_eval` arbitrary-code-execution path behind the ad-hoc
query route — orchestrator-verified.

9 findings: 1 🔴, 2 🟠, 4 🟡, 2 ⚪ (one of which is the sandbox's
cannot-statically-verify line).

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: fail
R8: fail
R9: fail
R10: fail
R11: pass
R12: pass
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

FIX:
- Unauthenticated ad-hoc queries allow arbitrary Python execution — `_routes.py:129` — remove full-builtins evaluation from request-controlled specs or require effective authentication before execution, and add an RCE regression test
- Ad-hoc primary and lookup directories bypass confinement — `_routes.py:130` — resolve every supplied source directory through `confine_path` before `_run_query`
- Anonymous LAN callers can retrieve the injected bearer token — `_app.py:40` — reject non-loopback binding without an operator-provided secret, or use credentials not disclosed by the anonymous page
- `confine_path` omits `expanduser()` — `_security.py:52` — use `Path(file_path).expanduser().resolve()` and add a home-relative-path test
- Valid-token open/action integrations lack success tests — `test_serve.py:409` — add in-vault success cases asserting the underlying operation receives the resolved path
- Query-name validation and resolution are duplicated — `_routes.py:101` — extract one helper used by both routes
- Two confinement tests cover the identical `archive_directory=None` behavior — `test_serve_security.py:90` — remove the redundant second test
- Missing `index.html` produces an uncaught 500 — `_app.py:42` — register the injected-index route only when the file exists or return a controlled 404

VERIFY:
- Runtime tests and WebUI token flow are unverified — run `uv run pytest tests/tools/bim/test_serve.py tests/tools/bim/test_serve_security.py`, build the frontend with `npm run build`, then smoke-test patch, action, and open from the served UI

KNOWN:
- (none)

## Carl

Frontend & design specialist (gemini/copilot backend). Read the diff, `api.ts`,
and `_routes.py`. Full output in `dev/local/tmp/carl-output-00042-01.txt`.

1 finding: 1 🟡 (duplicate `_serialize_dict` / `_serialize_row` — discarded at
the gate as out of diff). Raised no frontend-specific findings on the `api.ts`
token wiring.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

Verdict: 35 findings
Tests: 3782 passed, 0 failed, 16 skipped
