---
prd: docs/dev/project-management/prds/wip/00151-bim-tiromex-backends-v1.md
review: 1
date: 2026-11-25
head_sha: 2e525a319a5f735f2d646c7b8052900bf7fdd3c5
codex_thread_id: 01a2115c-b6a3-7480-9a5c-69b481acf408
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: df1851c1
  carl: 194981e4
---

# Review: 00151-bim-tiromex-backends-v1

Diff range: `49250f8366e3f90437aac6eb0e7acab05959a8d2..2e525a319a5f735f2d646c7b8052900bf7fdd3c5`

codex_rung_guard: not fired

Autopilot run, cycle 1, full review. Interactive session (no `$_AUTOPILOT_LOOP`), so no Watcher was dispatched. Consensus engine: legacy. Pack: ok. Bob ran on codex with the inlined prompt (473 KB). Carl ran on copilot, model gemini-3.8-flash.

Diff base note: HEAD is a merge of origin/master (`c570e042`) made after the build, so `state.work_start_sha..HEAD` (`fb9e91ca..HEAD`) holds 310 files of master's own work. The base `49250f83` is a synthetic, unreferenced commit made with git plumbing (`merge-tree`, `commit-tree`): the pre-PRD tree merged with the same master commit, with `docs/dev/project-management/` and the one conflicted source file (`src/lib/buvis/pybase/adapters/console/console.py`) taken from HEAD. The range is 43 files and holds this PRD's contribution plus the merge's two one-line test adjustments. The commit has no ref and git can prune it later; cycle 2 scopes from `head_sha`, so nothing depends on it after this cycle.

Coordinator checks: `mypy src/lib/ src/tools/` at HEAD reports no issues in 596 source files (R49). R2 is confirmed in the installed `requests`: `Session.send` calls `resolve_redirects(..., yield_requests=True)` even with `allow_redirects=False`, and that generator reads `resp.content` (sessions.py:212) before it yields, so a 3xx reply with a `Location` header has its whole body read with no cap before `_download` sees the status. R3 matches the residual the design doc accepts (a worker can stay blocked after the deadline; the caller is released). R4 is real but narrow: the reader and writer threads start before the `try` whose `finally` kills the process group.

Consolidation: the canonical script ran. The coordinator then merged paraphrase pairs the script left apart and absorbed every mechanical test-check line into an existing row (`mech-check` added to its finders; no new row was needed). Merges: R17 into R5 (duplicate issuer helper); R19 into R6 (CLI does not prove it passes the llm map); R23 and R25 into R7 (hedged dependency-failure tests); R41 into R12 (relative executable against the temp cwd); R20 and R46 into R43 (model missing until invocation); R31 into R37 (settings replay). R38 gained Bob (second sentence of his R15). Refs R17, R19, R20, R23, R25, R31, R41 and R46 are retired. The fail-first replay also listed tests in files outside this diff (console adapter, note format, tx CLI, doc rules CLI); they belong to master's work and sit in R32.

Bob's KNOWN bucket is in the table as he wrote it (R21 to R34, less the retired refs): he judged those rows as not defects of this PRD.

## Review Summary

Reviewed: 7 completed tasks
PRDs checked: 00151-bim-tiromex-backends-v1

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex)
- Carl: ✅ Available (copilot, gemini-3.8-flash)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | ⚪ | The Claude probe never saw a successful reply: auth failed in the sandbox, so the envelope key (`structured_output` vs `result`) and the effect of `--safe-mode` on OAuth/setup-token auth are unobserved. `unattended_safe = True` rests on `claude --help` listing the flags. I checked `claude --help` (CLI 2.1.332) and it lists all six isolation flags. The docs are honest about the gap. Live qualification stays with 00153 | docs/source/tools/bim.rst:1138 | 4 | ALICE, BOB |
| R2 | [1/4] | 🟠 | The HTTP reply cap misses redirect bodies. `requests.Session.send` can consume a redirect body while preparing `Response.next`, even with `allow_redirects=False` and `stream=True`. This occurs before `_download` sees the status. Use a transport path that returns the initial response without preparing the redirect. Test with real Requests and a loopback server that returns a `Location` header and a large body. | src/tools/bim/shared/llm/http.py:156 | 2 | BOB |
| R3 | [1/4] | 🟠 | The HTTP deadline releases the caller while a worker can remain blocked inside a read. A peer that keeps sending data within the socket inactivity timeout can hold the connection and worker past the deadline. The fake iterator resumes only when the test releases it. Make the deadline interrupt the transport and verify that a real slow response releases both the worker and connection. | src/tools/bim/shared/llm/http.py:163 | 2 | BOB |
| R4 | [1/4] | 🟠 | A thread-start failure can leave a spawned CLI running because the cleanup `finally` starts after all three threads launch. Cover startup with process cleanup immediately after spawn, map startup failures to `exit`, and inject a thread-start failure in a test. | src/tools/bim/shared/llm/base.py:253 | 3 | BOB |
| R5 | [2/4] | 🟡 | `_issuer_from_reply` is a verbatim copy of the existing `_resolve_model_issuer`, so the new helper is redundant and the diff touched working code. Delete `_issuer_from_reply` and call `_resolve_model_issuer(parsed, registry)` at classify_with_model (`(None, None, None) if doc_type_only`) | src/tools/bim/commands/doc/shared/classifier.py:281 | 6 | ALICE, BOB |
| R6 | [2/4] | 🟡 | Nothing tests that `bim doc` passes `settings.llm` to the health checker and `get_pipeline`. The 6 call sites in doc_cli.py were changed. The CLI tests stub the checker with `lambda _s, _llm: None` and mock `get_pipeline` without checking its args. Dropping `settings.llm` from a call site would pass every test, and a named-backend config would only fail at run time. Capture the arguments and assert `settings.llm` arrives at both seams, for ingest and at least one other command | src/tools/bim/doc_cli.py:92 | 7 | ALICE, BOB |
| R7 | [2/4] | 🟡 | Three touched CLI tests keep an `or` hedge and pass against the pre-change code (fail-first replay). With the old 1-arg call, the new 2-arg `_raise` raises TypeError, so `exit_code != 0` is still true. They cannot fail on the behavior they claim to check. Assert `exit_code != 0 and "ocrmypdf" in result.output` (or the message each test raises), and have the stub record its `(settings, llm)` args | tests/tools/bim/doc/test_cli_ingest.py:130 (same shape at tests/tools/bim/doc/test_cli_audit.py:218 and tests/tools/bim/doc/test_cli_promote.py:116) | 7 | ALICE, BOB, mech-check |
| R8 | [1/4] | 🟡 | Doc classifier/extractor call the registry with `JsonObject` (wire schema `{"type":"object"}`) and skip `require_strict_schema`. The spec says to reject unexpected schema keys and check the caller's schema, but for doc this check is bypassed by design and doc coerces fields itself. | src/tools/bim/shared/llm/base.py:149 | doc integration | BLAKE |
| R9 | [1/4] | 🟡 | Unrequested transport behaviour change in the doc LLM path. HTTP redirects are no longer followed (`allow_redirects=False`, redirect becomes an `exit` error). The old `requests.post` followed them. There is also a new 4 MiB reply cap, and a process-group kill with a 5 s reader join for CLIs. The CHANGELOG discloses the redirect change, but the spec asks for behaviour-preserving doc cutover and lists none of these. | src/tools/bim/shared/llm/http.py:156 | HTTP adapters | BLAKE |
| R10 | [1/4] | 🟡 | `extraction_method` and retry keys change meaning in named mode (`llm:<backend name>` instead of `llm:<model>`). Timeouts now appear as `[timeout] <backend>: ...` in triage reasons instead of the `requests` message. Both are documented and defensible, but neither is in the spec. | src/tools/bim/commands/doc/shared/pipeline.py:274 | doc integration | BLAKE |
| R11 | [1/4] | 🟡 | A configured `llm:` entry named `ollama` or `llamacpp` silently takes over legacy mode, so `endpoint`/`primary_model`/`fallback_model` are ignored. Docs mention it (docs/source/tools/bim.rst:1063) but nothing warns at load time. | src/tools/bim/commands/doc/shared/llm.py:86 | doc settings | BLAKE |
| R12 | [2/4] | 🟡 | CLI preflight can find an executable through a relative path, then `Popen` looks for it from the temporary directory. Resolve the executable to an absolute path before changing the child's working directory. Keep the remaining arguments literal and test a relative executable. (Alice, same defect: `bim.rst` does not say that a command backend runs in an empty temp directory; add one sentence to the `command` bullet at docs/source/tools/bim.rst:1076.) | src/tools/bim/shared/llm/base.py:309 | 3 | BOB, ALICE |
| R13 | [1/4] | 🟡 | Configuration accepts embedded NULs in command arguments, and `Popen` raises an uncaught `ValueError`. Temporary-directory creation and cleanup can also raise raw `OSError`. Reject NULs at config load and map filesystem failures to `exit`. Add tests for both paths. | src/tools/bim/shared/llm/base.py:219 | 3 | BOB |
| R14 | [1/4] | 🟡 | Inner JSON decoding can leak `ValueError` for integers above Python's conversion limit and `RecursionError` for deeply nested replies. Both inputs fit the reply cap. Map these decoder failures to `parse` in the shared helper and add regression cases. | src/tools/bim/shared/llm/base.py:157 | 1 | BOB |
| R15 | [1/4] | 🟡 | The CLI runner ignores the stdin writer's lifetime and checks its errors without joining it. Include the writer in the existing bounded join so pipe failures reach the caller reliably. Decode diagnostic output only on the nonzero-exit path. | src/tools/bim/shared/llm/base.py:253 | 3 | BOB |
| R16 | [1/4] | 🟡 | The nonzero-exit fallback copies arbitrary command stdout into the error. A command that echoes its input can put OCR text in doc triage reasons. Keep generic command diagnostics on stderr and handle Claude's stdout error envelope in its adapter. | src/tools/bim/shared/llm/base.py:271 | 3 | BOB |
| R18 | [1/4] | 🟡 | The doc transport tests repeat the fake Requests exception hierarchy and streamed response across six files. Share a test helper and remove fake `.json()` methods where only `iter_content()` is used. | tests/tools/bim/doc/test_classifier.py:24 | 6 | BOB |
| R21 | [1/4] | 🟡 | The mechanical check flags the classifier lazy-import test for having no assertion. Its body predates the cutover and is outside this diff. | tests/tools/bim/doc/test_classifier.py:502 | general | BOB, mech-check |
| R22 | [1/4] | 🟡 | The mechanical check flags the audit missing-config assertion for accepting either outcome. The assertion is unchanged and independent of backend routing. | tests/tools/bim/doc/test_cli_audit.py:204 | general | BOB, mech-check |
| R24 | [1/4] | 🟡 | The mechanical check flags the migration missing-config assertion for accepting either outcome. The assertion is unchanged and independent of backend routing. | tests/tools/bim/doc/test_cli_migrate_layout.py:116 | general | BOB, mech-check |
| R26 | [1/4] | 🟡 | The mechanical check flags the triage missing-config assertion for accepting either outcome. The assertion is unchanged and independent of backend routing. | tests/tools/bim/doc/test_cli_triage.py:108 | general | BOB, mech-check |
| R27 | [1/4] | 🟡 | The mechanical check flags the extractor lazy-import test for having no assertion. Its body predates the cutover and is outside this diff. | tests/tools/bim/doc/test_extractor.py:435 | general | BOB, mech-check |
| R28 | [1/4] | 🟡 | The mechanical check flags the health happy-path test for having no assertion. This legacy smoke test is unchanged. The new named health tests assert the probe calls. | tests/tools/bim/doc/test_health.py:43 | general | BOB, mech-check |
| R29 | [1/4] | 🟡 | The mechanical check flags the business-root acceptance test for having no assertion. This unchanged test covers path validation outside the LLM work. | tests/tools/bim/doc/test_settings_models.py:267 | general | BOB, mech-check |
| R30 | [1/4] | 🟡 | Replay passes three new legacy extractor tests against base. They intentionally preserve fallback-model selection, summary truncation, and partial summaries. These behaviors are part of the compatibility contract. | tests/tools/bim/doc/test_doc_llm_preserved.py:67 | 6 | BOB, mech-check |
| R32 | [1/4] | 🟡 | Replay flags console, note-format, tx CLI, and doc rules tests that pass against base. Those cases exercise existing behavior outside the backend cutover. | N/A | general | BOB, mech-check |
| R33 | [1/4] | 🟡 | The function-size check records `Pipeline.run` at 58 lines and `_triage` at 111. Both bodies are unchanged. Splitting them would be a separate refactor. | src/tools/bim/commands/doc/shared/pipeline.py:154 | general | BOB |
| R34 | [1/4] | 🟡 | The extractor test file still exceeds 800 lines. It already exceeded the limit before the cutover, and the new preservation tests live in a sibling file. Splitting the existing suite is separate work. | tests/tools/bim/doc/test_extractor.py:860 | general | BOB |
| R35 | [1/4] | 🟡 | Redundant bytes(bytearray) conversion in _run; call .decode() directly on out and err | src/tools/bim/shared/llm/base.py:285 | 3 | CARL |
| R36 | [1/4] | 🟡 | Redundant bytes(buffer) conversion in _download; json.loads accepts bytearray directly | src/tools/bim/shared/llm/http.py:160 | 2 | CARL |
| R37 | [2/4] | ⚪ | `test_backend_rejects_a_non_string` passes against the old `Literal` field, so it pins nothing new. The other new cases in that class do fail at base | tests/tools/bim/doc/test_settings_models.py:175 | 5 | ALICE, BOB, mech-check |
| R38 | [2/4] | ⚪ | `_run` decodes stderr and stdout into `diagnostics` and `excerpt` on every call, including zero-exit runs with up to 4 MB of stdout. The result is used only on the non-zero-exit path. Compute it inside the `proc.returncode != 0` branch | src/tools/bim/shared/llm/base.py:269 | 3 | ALICE, BOB |
| R39 | [1/4] | ⚪ | `get_classifier` and `get_extractor` have no production caller now that `get_pipeline` builds both itself. Their new `llm` parameter is exercised only by tests. Keep them if the design contract requires them, or drop them and the tests that exist only for them | src/tools/bim/dependencies.py:224 | 7 | ALICE |
| R40 | [1/4] | ⚪ | The doc error text is awkward for non-HTTP backends. The classifier builds "HTTP error calling claude: exited with code 1: ..." (and for HTTP backends "HTTP error calling ollama: HTTP error calling http://...: ..."). The extractor builds "HTTP error: ..." the same way. This matches the design table but misleads in triage reasons. Choose a per-kind prefix or use `str(exc)` (dispatch-1 note NB3, left open) | src/tools/bim/commands/doc/shared/classifier.py:454 | 6 | ALICE |
| R42 | [1/4] | ⚪ | `HttpBackend` uses `model if model is not None` while `ClaudeBackend` uses `model or settings.model`. An empty-string model is sent as `"model": ""` by HTTP and ignored by Claude. Validate the field non-empty in settings, or use one rule in both adapters | src/tools/bim/shared/llm/http.py:104 | 2 | ALICE |
| R43 | [3/4] | 🟡 | A named `ollama` or `openai` entry without `model` loads and passes health, then fails every doc call with a raw `LLMConfigError` (dispatch-1 notes NB2/NB10, left open). Rejecting it in `resolve_doc_route` at config load would be cheaper for the user. This is not a PRD requirement. (Bob: the approved design explicitly permits missing models during health and checks the effective model at invocation. Blake: in doc the error is caught as a generic exception and becomes a triage "classifier error".) | src/tools/bim/commands/doc/shared/llm.py:94 | 5 | ALICE, BLAKE, BOB |
| R44 | [1/4] | ⚪ | The literal Phase 1 acceptance commands `pytest tests/tools/bim/test_llm_backends.py -k claude` and `-k command` select zero tests (exit 5, verified). The adapter tests sit in `tests/tools/bim/test_llm_claude.py` and `tests/tools/bim/test_llm_command.py`. The PRD's own build note authorises this move, and the redirected commands pass. The Success Metrics command, which names only `test_llm_backends.py`, does not cover them. | tests/tools/bim/test_llm_backends.py | Phase 1 | BLAKE |
| R45 | [1/4] | ⚪ | `unattended` enforcement exists only in `LLMRegistry.get/invoke`. No production caller (doc) passes `unattended=True`, so the "schedule use requires unattended:true" guard is unit-tested only and not wired to any scheduled path. This is probably deferred to 00153/00155. | src/tools/bim/shared/llm/registry.py:28 | command adapter | BLAKE |
| R47 | [1/4] | ⚪ | The branch also contains unrelated changes: `_DocGroup` IssuersFileError handling, `exit_on_failure=True` on audit, and rewording of `[doc]` to `` `doc` `` in panic messages. These are likely from other PRDs. | src/tools/bim/doc_cli.py:22 | general | BLAKE |
| R48 | [1/4] | ⚪ | The endpoint rule says bim never follows redirects, but health probes retain Requests' redirect behavior. Scope the rule to completion POSTs. | docs/source/tools/bim.rst:1069 | 7 | BOB |
| R49 | [1/4] | ⚪ | Closeout type-check evidence is open. Run `uv run mypy src/lib/ src/tools/` on revision `2e525a319a5f735f2d646c7b8052900bf7fdd3c5` and record the exit status. The supplied pytest gate recorded 8,950 passed, zero failed, and 17 skipped. | N/A | 7 | BOB |

## Alice

11 findings, none above medium (R1, R5, R6, R7, R12, R37, R38, R39, R40, R42, R43). She found the wire formats, legacy defaults, route resolution, CLI call sites and the subprocess runner sound. Raw output: `docs/dev/tmp/alice-output-00151c1-20261125.txt`.

R1: fail
R2: fail
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

## Blake

Blind lens, PRD only. 8 findings, none above medium (R8, R9, R10, R11, R43, R44, R45, R47). He verified the closed reason set, the Claude isolation argv against the installed CLI, literal argv without a shell, strict settings, legacy defaults and the unchanged Ollama and llama.cpp wire formats. Raw output: `docs/dev/tmp/blake-output-00151c1-20261125.txt`.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens and de-slop, codex, inlined prompt. FIX bucket: 12 items, three high (R2, R3, R4). VERIFY bucket: one item (R49, mypy), queued in `00151-bim-tiromex-backends-v1-checks-1.json`. KNOWN bucket: 19 items he judged outside this PRD or accepted by the design. Raw output: `docs/dev/tmp/bob-output-00151c1-20261125.txt`.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: fail
R11: pass
R12: fail
R13: fail
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

2 findings, both medium style items (R35, R36). He could not read the context and diff files whole (too large for his reader) and worked from slices and the source files. Raw output: `docs/dev/tmp/carl-output-00151c1-20261125.txt`.

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

Verdict: 41 findings
Tests: 8950 passed, 0 failed, 17 skipped (suite run this cycle)
