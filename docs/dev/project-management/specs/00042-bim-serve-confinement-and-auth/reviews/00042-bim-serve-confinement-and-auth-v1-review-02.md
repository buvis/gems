---
prd: dev/local/prds/wip/00042-bim-serve-confinement-and-auth-v1.md
review: 2
date: 2026-08-15
head_sha: 39785d3a65854252fd944daaa85b5712ffd1c600
codex_thread_id: 01a005ef-b58e-76c1-add0-406f58c957f4
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00042-bim-serve-confinement-and-auth-v1

Diff range: `7d362cc4bdc3d038826aa325fd1fa0ea0665ab98..39785d3a65854252fd944daaa85b5712ffd1c600`

codex_rung_guard: not fired

## Review Summary

Reviewed: 12 completed tasks (5 original plan, reviewed in full in cycle 1; 7
`[D1]` decision-gate follow-ups, the work this cycle reviews)
PRDs checked: 00042-bim-serve-confinement-and-auth-v1

Cycle 2, **incremental** review of the 14 rework commits since cycle 1. All four
lenses ran: Alice (consensus, implementation-aware), Blake (blind, PRD-only),
Bob (codex — doubt rubric D1-D5 + de-slop, resumed on his cycle-1 thread), Carl
(gemini — frontend/design).

### Agent Status

- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available
- Carl: ✅ Available

### Notes on method

- Bob resumed his cycle-1 codex session via `--resume-thread`, so his verdicts
  are a delta against his own prior critique rather than a fresh review.
- Alice emitted absolute `File:` paths; they were normalized to repo-relative
  before consolidation so same-file findings merge across reviewers. No content
  was changed.
- Two ledger-settled findings were auto-dismissed mechanically
  (`--ledger-dismiss BLAKE`); four more were settled by the gate below because
  Blake re-raised them in different words or against a shortened path, which the
  matcher does not catch.
- **No follow-up tasks were created.** The cycle hit the rework cap
  (`cycle 2 >= rework_cap 2`), so no rework is dispatched and the PRD stalls;
  `autopilot stall` clears `state.tasks`, so tasks created here would be
  discarded. The findings' durable homes are this file, the settled-decisions
  ledger, and the batch deferred JSON.

## Cycle-1 findings: verification

Nine of the ten cycle-1 consolidated findings are **genuinely resolved in code**,
confirmed independently by Alice (implementation-aware, with live `TestClient`
probes) and by Bob against his own prior critique:

| # | Cycle-1 finding | Status |
|---|-----------------|--------|
| 1 | 🔴 Unauthenticated ad-hoc/named query surface (RCE + traversal) | **Resolved server-side** — `Depends(require_token)` on both exec routes; `confine_path` on `spec.source.directory` and every `lookups[].source.directory`. See the new 🔴 below for the client half. |
| 2 | 🔴 Non-loopback bind discloses the token | **Resolved** — `token_in_page` gate stops page injection off loopback; the warning no longer claims "writes still require it". |
| 3 | 🟠 `confine_path` drops `.expanduser()` | **Resolved** — expansion on both the request path and the allowed roots, with tilde-form tests behind a `fake_home` fixture. |
| 4 | 🟠 No CHANGELOG entry | **Resolved** (`aaf1caf`). |
| 5 | 🟡 `require_token` 500 on a non-ASCII header | **Resolved** — `compare_digest` on bytes, 401. |
| 6 | 🟡 Docs unchanged | **Resolved** (`5ccf031`). |
| 7 | 🟡 Read surface unauthenticated / design Question | **Closed as a documented decision** — GET reads stay token-free, now stated in `bim.rst` and the CHANGELOG. Remains a settled deferral. |
| 8 | 🟡 Query-name resolution duplicated | **Resolved** — `_resolve_query_path` extracted (`39785d3`). |
| 9 | 🟡 No valid-token success tests | **Resolved to the narrower bar** — two resolved-path success tests. |
| 10 | ⚪ `_index` regressions | **Resolved** — 404 on a missing `index.html`, a warning on a headless page, `include_in_schema=False` restored. |

The rework introduced **one regression**, which is the blocking finding of this
cycle.

## Consolidated Findings

22 consolidated rows. The consolidator under-merged the api.ts finding (Alice
cited the file, Bob the file plus `:87`), so the orchestrator's effective merge
is given first.

### Blocking (unresolved after gate triage)

- **[2/4] 🔴 The server-side token gate on the query routes was never mirrored in
  the client — the WebUI is shipped broken.** Task 6 added
  `Depends(require_token)` to `POST /api/queries/{name}/exec` and
  `POST /api/queries/_adhoc`, but `execQuery` sends **no headers at all**
  (`api.ts:87-93`) and `execAdhoc` sends only `Content-Type` (`api.ts:95-103`);
  only `patchZettel`, `execAction` and `openFile` attach `X-Buvis-Token`.
  `+page.svelte:35` calls `execQuery` for every dashboard view, so on the default
  loopback bind every query returns 401 and the UI renders only
  "Query failed: Unauthorized". This breaks PRD Success Metric 3 ("Existing
  WebUI happy-path flows still work unchanged"). The server tests miss it
  because they set the header by hand.
  **Orchestrator-verified** by direct read of `api.ts` and `_routes.py:120-145`.
  Found by: Alice (🔴), Bob (🟠). File: `src/tools/bim/commands/serve/frontend/src/lib/api.ts`.
- **[1/4] 🟠 Ad-hoc source confinement discards its own result.**
  `exec_adhoc` calls `confine_path(spec.source.directory, ...)` for the primary
  and each lookup directory but throws the resolved paths away, then hands
  `_run_query` the original client strings, which the scanner re-resolves later —
  a check-then-act window and a break of the resolved-path contract.
  **Orchestrator-verified** at `_routes.py:140-145`. Found by: Bob.

### Discarded at the gate (verified reason, recorded in the ledger)

- **Blake 🔴 "token-bearing `_adhoc` request runs arbitrary Python via
  `python_eval`" → discarded, out of diff and inverted by the baseline.** The
  evaluator (`expression_engine.py`, `dependencies.py`) is untouched by this
  PRD's entire work range (`cc11c7e..39785d3` touches 11 files, none of them the
  query engine). **Before** this PRD the same endpoint reached the same
  full-builtins `eval` with **no credential at all**; task 6 added token auth and
  source confinement, so the PRD strictly reduces this exposure. Blake is blind
  by construction and cannot see that baseline. Real product risk, wrong owner —
  logged to the batch deferred JSON for a follow-up PRD.
- **Blake 🔴 "token-theft chain via unsanitized `{@html marked.parse(content)}`"
  → discarded, out of diff and not worsened.** `MarkdownEditor.svelte` is
  untouched by this PRD's work range (its only frontend file is `api.ts`). The
  stored XSS pre-dates the PRD, and pre-PRD an XSS payload needed **no token** to
  reach the same mutating endpoints, so the token requirement is an obstacle on
  that path, not an enabler. Logged to the batch deferred JSON for a follow-up
  PRD (sanitize markdown rendering).
- **Blake 🟠 "read routes entirely unauthenticated" → settled deferral.** Already
  recorded as the cycle-1 high-severity requirements ambiguity (Success Metric 2
  vs the Feature Behavior text) and resolved then by the simplest safe
  assumption. A PRD-level call for batch end.
- **Blake 🟠 "non-loopback `allowed_hosts=[\"*\"]` lets any LAN host read the
  vault" → settled deferral.** The wildcard allowlist is a design-doc decision
  recorded verbatim; the exposure it leaves is reads-only and identical to
  pre-PRD behavior. The token-disclosure half, which *was* a regression, is
  fixed (task 7).
- **Blake 🟠 "the built WebUI bundle is stale" → settled deferral** (cycle-1
  entry, missed by the matcher on the shortened path). `static/` is gitignored
  and rebuilt by `hatch_build.py` at package build time, so a stale bundle
  cannot ship; dev-local only.
- **Blake 🟡 "`handle_import` confinement breaks importing outside files" →
  settled discard** (cycle-1 entry, re-raised in different words).
- **Auto-dismissed by the ledger matcher:** Blake 🟡 `install_security` signature
  / `::1` never matching, and Blake ⚪ `handle_archive` building `Path("None")`.

### Raw consolidated table

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🔴 | Task 6 gated the exec query routes but `execQuery`/`execAdhoc` still send no `X-Buvis-Token`; every dashboard query returns 401. PRD Success Metric 3 broken. | src/tools/bim/commands/serve/frontend/src/lib/api.ts | 6 | ALICE |
| [1/4] | 🔴 | `POST /api/queries/_adhoc` hands attacker-controlled `filter.expr`/`columns[].expr` to `python_eval` with full builtins; a token-bearing request runs arbitrary Python. Proven live. | src/tools/bim/commands/serve/_routes.py | Phase 1 | BLAKE |
| [1/4] | 🔴 | Token-theft chain: the injected `window.__BUVIS_TOKEN__` plus unsanitized `{@html marked.parse(content)}` lets a poisoned note read the token. | src/tools/bim/commands/serve/frontend/src/lib/components/MarkdownEditor.svelte | Phase 2 | BLAKE |
| [1/4] | 🟠 | Read routes are entirely unauthenticated: `GET /api/zettels/{file_path:path}` has no `Depends(require_token)`. | src/tools/bim/commands/serve/_routes.py | Phase 2 | BLAKE |
| [1/4] | 🟠 | Non-loopback bind sets `allowed_hosts = ["*"]`; combined with token-free GETs any LAN host reads the whole vault. Proven live. | src/tools/bim/commands/serve/_security.py | Phase 2 | BLAKE |
| [1/4] | 🟠 | The built WebUI on disk predates the token wiring, so every mutating WebUI action currently 401s. | src/tools/bim/commands/serve/static/_app/immutable | Phase 2 | BLAKE |
| [1/4] | 🟠 | Query execution is now token-gated, but `execQuery` and `execAdhoc` send no token, so selecting any query in the loopback WebUI returns 401. | src/tools/bim/commands/serve/frontend/src/lib/api.ts:87 | 6 | BOB |
| [1/4] | 🟠 | Ad-hoc source confinement discards the resolved paths and later re-resolves the original request strings, reopening a symlink-swap race. | src/tools/bim/commands/serve/_routes.py:140 | 6 | BOB |
| [1/4] | 🟡 | CHANGELOG and `bim.rst` claim the WebUI sends the token automatically and that the LAN UI can read but not write; both are inaccurate as shipped. | CHANGELOG.md | 10 | ALICE |
| [1/4] | 🟡 | LAN mode has no operator path to authenticate: the token is printed to the console but `api.ts` cannot accept it. | src/tools/bim/commands/serve/_security.py | 7 | ALICE |
| [1/4] | 🟡 | `for lookup in getattr(spec, "lookups", None) or []` fails open on a security check; `QuerySpec.lookups` always exists, so the `getattr` only accommodates the test stub. | src/tools/bim/commands/serve/_routes.py | 6 | ALICE |
| [1/4] | 🟡 | Two behaviors not in the PRD: the raw token is printed to the console on non-loopback, and page injection is skipped there. | src/tools/bim/commands/serve/_security.py | Phase 2 | BLAKE |
| [1/4] | 🟡 | Only `GET /` injects the token; the `StaticFiles` mount serves `/index.html` raw, so that URL yields a token-less page. | src/tools/bim/commands/serve/_app.py | Phase 2 | BLAKE |
| [1/4] | 🟡 | `GET /api/events` (SSE) has no token dependency and streams changed file paths; `_subscribers` grows unbounded. | src/tools/bim/commands/serve/_sse.py | Phase 2 | BLAKE |
| [1/4] | 🟡 | Confining `handle_import` makes the WebUI import action unusable for outside files. | src/tools/bim/commands/serve/_actions.py | Phase 1 | BLAKE |
| [1/4] | 🟡 | The in-vault ad-hoc test uses an already-canonical path, so it cannot detect that `confine_path` results are discarded. | tests/tools/bim/test_serve.py:988 | 6 | BOB |
| [1/4] | 🟡 | `test_serve.py` is 1,051 lines, past the 800-line limit; the new query-security and index-security suites split cleanly. | tests/tools/bim/test_serve.py:1 | 12 | BOB |
| [1/4] | ⚪ | `confine_path` is fed `spec.source.directory` straight from client JSON with no type check; a non-string raises an uncaught `TypeError` → 500. | src/tools/bim/commands/serve/_routes.py | 6 | ALICE |
| [1/4] | ⚪ | `test_serve.py` grew 672 → 1051 lines this cycle, past the 800-line max in AGENTS.md. | tests/tools/bim/test_serve.py | 12 | ALICE |
| [1/4] | ⚪ | Check-then-act between `confine_path` and the later `is_file()` / write, in the write path. | src/tools/bim/commands/serve/_routes.py | Phase 1 | BLAKE |
| [1/4] | ⚪ | Phase 1 acceptance asks for "403 and the file is untouched"; tests assert 403 + `assert_not_called()` but never assert real bytes. | tests/tools/bim/test_serve.py | Phase 1 | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: pytest, frontend build, and loopback/non-loopback WebUI smoke tests pass. | N/A | general | BOB |

### Auto-dismissed (ledger)

- [BLAKE] 🟡 Interface deviates from the PRD export list: spec says `install_security(app, allowed_hosts)`, implementation is `install_security(app, host)`. Spec also says allow `[::1]`; the code allows `::1`, which Starlette can never match. | File: src/tools/bim/commands/serve/_security.py — Settled by design. The design doc documents this verbatim as a known upstream Starlette limitation, noting IPv4 127.0.0.1 (the actual default) is unaffected. Not introduced by this PRD.
- [BLAKE] ⚪ `handle_archive` still does `Path(str(app_state.archive_directory))` when `archive_directory` is `None`, producing a literal `Path("None")`. | File: src/tools/bim/commands/serve/_actions.py — Out of diff. The `archive_dir` line is pre-existing and untouched by this range; noted for a follow-up PRD.

## Alice

Implementation-aware consensus lens. Ran with `Read, Bash`; independently ran the
`bim serve` suite (83 passed, 0 skipped), `uv run mypy` (clean),
`uv run ruff check` (clean), and live `TestClient` probes. Verified nine of the
ten cycle-1 findings resolved in code and identified the rework's own regression:
`api.ts` was never updated for the newly gated exec routes. Full findings in
`dev/local/tmp/alice-output-00042-02.txt`.

6 findings: 1 🔴, 3 🟡, 2 ⚪.

R1: pass
R2: pass
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: fail

## Blake

Blind lens — PRD-only prompt, no diff, no design doc, no review history, no
ledger. Found the code himself and proved each claim with `TestClient` probes,
including a live RCE probe that wrote a file outside the vault. Full findings in
`dev/local/tmp/blake-output-00042-02.txt`.

13 findings: 2 🔴, 3 🟠, 5 🟡, 3 ⚪. Six were settled or auto-dismissed at the
gate — expected for a lens that cannot see the baseline or the review history,
and the reason his two 🔴s were discarded rather than actioned.

B1: fail
B2: pass
B3: fail
B4: pass
B5: pass
B6: fail
B7: pass
B8: pass
B9: fail
B10: pass
B11: pass
B12: fail
B13: pass
B14: fail
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens (rubric D1-D5) + de-slop, run on codex in a static-only sandbox,
resumed on the cycle-1 thread (`01a005ef-b58e-76c1-add0-406f58c957f4`). Full
findings in `dev/local/tmp/bob-output-00042-02.txt`. Independently caught the
api.ts token gap and was the sole reviewer to notice that `exec_adhoc` discards
`confine_path`'s resolved paths.

5 findings: 2 🟠, 2 🟡, 1 ⚪ (the sandbox's cannot-statically-verify line).

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

FIX:
- Query execution requests omit the required token — src/tools/bim/commands/serve/frontend/src/lib/api.ts:87 — attach `X-Buvis-Token` in `execQuery` and `execAdhoc`, then correct the LAN documentation to match the UI's actual capabilities
- Resolved ad-hoc source paths are discarded — src/tools/bim/commands/serve/_routes.py:140 — assign `str(confine_path(...))` back to the primary and lookup source directories before `_run_query`
- The confinement success test cannot distinguish original from canonical paths — tests/tools/bim/test_serve.py:988 — use a tilde, traversal-normalized, or in-vault symlink path and assert the executed spec contains the returned resolved path
- `test_serve.py` exceeds 800 lines — tests/tools/bim/test_serve.py:1 — split the new query-security and index-security classes into focused test modules

VERIFY:
- Runtime tests and WebUI integration are unverified — run `uv run pytest tests/tools/bim/test_serve.py tests/tools/bim/test_serve_security.py`, run the frontend `npm run build`, then smoke-test selecting a query on loopback and verify documented non-loopback behavior

KNOWN:
- (none)

## Carl

Frontend & design specialist (gemini/copilot backend). Read the diff, the pack,
and the context file. Full output in `dev/local/tmp/carl-output-00042-02.txt`.

0 findings — `[CARL] ✅ No issues found`. Note that Carl reviewed only the
scoped server-side diff and did not open `api.ts` (unchanged this cycle), which
is where the cycle's blocking frontend regression lives.

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

## Outcome

Cycle 2 did **not** converge: one unresolved 🔴 (the api.ts token gap, 2/4
consensus, orchestrator-verified) and one unresolved 🟠 remain after gate triage.
`state.cycle` (2) has reached `state.rework_cap` (2), so no third rework is
dispatched. Under loop mode an unresolved CRITICAL at the cap stalls the PRD
(`site: cap_critical`): 00042 moves to `dev/local/prds/hold/` and the batch
continues.

**To resume:** `mv dev/local/prds/hold/00042-bim-serve-confinement-and-auth-v1.md dev/local/prds/backlog/`.
The remaining work is small and well specified:

1. Attach `X-Buvis-Token` to `execQuery` and `execAdhoc` in `api.ts` (the
   blocking 🔴 — two lines, matching the three call sites that already do it),
   and add a server test that asserts the WebUI's own call shape rather than a
   hand-set header.
2. Assign `confine_path`'s return value back to `spec.source.directory` and each
   `lookup.source.directory` before `_run_query` (the 🟠), and replace the
   already-canonical path in the in-vault ad-hoc test so it can detect the
   discard.
3. Correct the CHANGELOG / `bim.rst` claims about what the WebUI and the LAN mode
   actually do, and replace the fail-open `getattr(spec, "lookups", None)` with
   `spec.lookups`.

Verdict: 22 findings
Tests: 3811 passed, 0 failed, 16 skipped
