---
prd: docs/dev/project-management/prds/wip/00151-bim-tiromex-backends-v1.md
review: 2
date: 2026-11-25
head_sha: 22a5fa0da0e6abbc70c0b5df056c0dbcb5b3c198
codex_thread_id: 01a2115c-b6a3-7480-9a5c-69b481acf408
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: e04788af
  carl: da990bc6
---

# Review: 00151-bim-tiromex-backends-v1

Diff range: `2e525a319a5f735f2d646c7b8052900bf7fdd3c5..22a5fa0da0e6abbc70c0b5df056c0dbcb5b3c198`

codex_rung_guard: not fired

Autopilot run, cycle 2, incremental review (`--since` the cycle-1 `head_sha`). Interactive session (no `$_AUTOPILOT_LOOP`), so no Watcher was dispatched. Consensus engine: legacy. Pack: ok. Bob ran on codex with the inlined prompt (280 KB), resuming his cycle-1 thread. Carl ran on copilot, model gemini-3.8-flash.

Scope note: the range holds the cycle-1 rework tasks 8 to 11 and one later commit, `22a5fa0d`, made by a peer interactive session (`feature-merge-klyreon-to-bim-48`) at the user's request, outside the autopilot task list. That commit addresses cycle-1 rows R2 (response hook replaces the Session fallback), R14, R16 and the I/O-thread wording. A first staging of this cycle (id `00151c2-20261125`) found that commit still uncommitted in the tree; that staging was abandoned and its two dispatch rows closed as not dispatched. This file comes from the second staging (`00151c2b-20261125`) at the committed HEAD.

Fail-first replay: skipped. The replay runner (`uv run --no-project --with pytest`) could not import `click`, so no `[MECH]` replay lines exist this cycle. Bob's R7 claim ("passes against the previous implementation") is therefore his own reading, not a computed fact.

Coordinator checks: Bob's R1 is reproduced. A scratch probe makes `link/../bin/tool` relative to a cwd where `link` is a symlink: `shutil.which` returns the path, `os.path.abspath` gives `elsewhere/bin/tool`, `os.path.realpath` gives `real/bin/tool`, and `os.path.samefile` reports False, so `run_cli` would run a different file than the one `which` checked. Bob's VERIFY item (R13) is run: `uv run --no-sync mypy src/lib/ src/tools/` at `22a5fa0d` reports no issues in 596 source files.

Consolidation: the canonical script ran. The coordinator rewrote one cell: R13's `int | None` is written `int or None`, because a bare pipe splits the table cell. The one mechanical tautology line (`test_cli_audit.py:204`) is added as R14 (`mech-check`); cycle 1 settled the same line as its R22. Blake's R2, R3 and R4 restate cycle-1 rows R9, R43 and R45, which the ledger settled, but their wording differed enough that the script's Blake filter did not catch them.

## Review Summary

Reviewed: 11 completed tasks (cycle-1 rework tasks 8 to 11 in range) plus peer commit 22a5fa0d
PRDs checked: 00151-bim-tiromex-backends-v1

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex, resumed thread)
- Carl: ✅ Available (copilot, gemini-3.8-flash)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🟠 | `os.path.abspath(found)` can select a different executable from the one `shutil.which` checked. It collapses `..` after a symlink before the OS resolves the path. Make the lookup result absolute without normalizing its components, pass it as `Popen(executable=...)`, and keep the original argv. Add a symlink-path regression test. | src/tools/bim/shared/llm/base.py:312 | 8 | BOB |
| R2 | [1/4] | 🟡 | Doc HTTP calls now refuse every redirect (3xx raises an `exit` BackendError). The old doc transport used `requests.post` with default redirect following. The PRD says to preserve doc behavior, and a legacy `endpoint` that redirects (an http to https proxy, for example) will now fail. The CHANGELOG records it, but the PRD does not authorize it. | src/tools/bim/shared/llm/http.py:174 | 3 | BLAKE |
| R3 | [1/4] | 🟡 | Named `ollama` and `openai` entries need `model`, but nothing checks that at config load. `BimSettings._doc_backends_exist` only runs `resolve_doc_route`, and the health check passes `None`. A missing model surfaces per document as `LLMConfigError` from `HttpBackend.complete`. It is not a BackendError, so the doc `_invoke` does not map it, and the pipeline's blanket `except Exception` turns it into a triage reason. | src/tools/bim/shared/llm/http.py:114 | 5 | BLAKE |
| R4 | [1/4] | 🟡 | The unattended guard exists only in `LLMRegistry.get`/`invoke(unattended=...)`. Neither doc caller passes `unattended`, so a `command` backend with `unattended: false` runs in an unattended doc ingest. The PRD ties schedule use to `unattended:true`, so a later caller (00153 or the scheduler) has to enforce it. Nothing in the doc path does. | src/tools/bim/commands/doc/shared/classifier.py:426 | general | BLAKE |
| R5 | [1/4] | 🟡 | On thread-start failure, killing and reaping the child closes its pipe ends. Parent-side streams assigned to threads that never started can stay open while the chained exception retains the runner frame. Close the unclaimed streams in the failure path and assert closure for each of the three injected startup failures. | src/tools/bim/shared/llm/base.py:264 | 8 | BOB |
| R6 | [1/4] | 🟡 | The regression fixture sends `SIGKILL` to recorded PIDs even after the runner has reaped them. A reused PID can belong to an unrelated process. Keep the `Popen` handles, assert the runner reaped the test child, and terminate and wait only for a child that is still running. This also removes the `_gone` polling helper. | tests/tools/bim/test_llm_transport_hardening.py:167 | 8 | BOB |
| R7 | [1/4] | 🟡 | Both new missing-executable cases pass against the previous implementation because they return before executable resolution changes. Move the relative missing-path case into the existing missing-executable test and remove the duplicate test. | tests/tools/bim/test_llm_transport_hardening.py:245 | 8 | BOB |
| R8 | [1/4] | 🟡 | The new promote wiring test repeats the dependency-failure test's setup and invocation. Parameterize the existing test with legacy and named settings so both cases check the forwarded map, the exit status, and the diagnostic. | tests/tools/bim/doc/test_cli_promote.py:125 | 10 | BOB |
| R9 | [1/4] | ⚪ | The `openai` kind sends no Authorization header and the settings have no key field, so an authenticated OpenAI-compatible endpoint cannot be used. The endpoint string is not validated at all. The PRD does not require auth, so this is a limitation. | src/tools/bim/shared/llm/settings.py:31 | 3 | BLAKE |
| R10 | [1/4] | ⚪ | The pipeline docstring still says `requests.exceptions.Timeout` is re-raised unwrapped. The code now raises `BackendError(TIMEOUT)`. It stays non-transient, so the retry short-circuit still works. Only the comment is stale. | src/tools/bim/commands/doc/shared/pipeline.py:469 | 9 | BLAKE |
| R11 | [1/4] | ⚪ | Error-message wording changed for HTTP failures. The old text was "HTTP error calling {url}: ..." and the new text is "HTTP error calling {backend}: ...". Timeouts now read "[timeout] <backend>: ..." in triage reasons. The CHANGELOG lists the timeout change. Tests may pin the new text. Result shapes and the transient/semantic split are unchanged. | src/tools/bim/commands/doc/shared/classifier.py:438 | 9 | BLAKE |
| R12 | [1/4] | ⚪ | The extra hardening goes beyond the PRD text: a 4 MiB reply cap, process-group kill, a 64 KiB stderr cap, a worker-thread total deadline, and a separate `test_llm_transport_hardening.py`. It is defensible as "bounded execution" and I found no defect in it. It is still unrequested surface. | src/tools/bim/shared/llm/base.py:43 | 2 | BLAKE |
| R13 | [1/4] | ⚪ | The recorded mypy pass covers the previous revision. Run `uv run mypy src/lib/ src/tools/` at `22a5fa0da0e6abbc70c0b5df056c0dbcb5b3c198`. Check the new `_run` return specifically because `Popen.returncode` is typed as `int or None`. `Popen.wait()` returns an `int`. | src/tools/bim/shared/llm/base.py:282 | 8 | BOB |
| R14 | [1/4] | 🟡 | test_doc_audit_panics_when_doc_section_missing hedges with `or`: either outcome satisfies it | tests/tools/bim/doc/test_cli_audit.py:204 | general | mech-check |

### Auto-dismissed (ledger)

- [BLAKE] ⚪ The acceptance commands in the PRD (`test_llm_backends.py -k claude` and `-k command`) match nothing as written. The PRD's own build note moves those tests to `test_llm_claude.py` and `test_llm_command.py`, and they pass there. File: tests/tools/bim/test_llm_backends.py (single-voice)

## Alice

All cycle-1 rows she re-checked are resolved at `22a5fa0d`: R2, R4, R5, R6, R7, R12, R14, R16, R38, R49. No regression in the scoped diff. Narrow pytest 347 passed; `mypy src/tools/bim` clean; ruff clean.

[ALICE] ✅ No issues found

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

## Blake

Eight findings (R2 to R4 and R9 to R12 above, plus one auto-dismissed). Blind spec check passes on layout, closed reason set, strict schema, unknown names and kinds, wire formats, Claude and command adapters, legacy defaults and doc cutover. Narrow pytest 388 passed. No live probes.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
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

FIX bucket: R1, R5, R6, R7, R8. VERIFY bucket: R13 (run by the coordinator, clean). KNOWN bucket: none.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
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

## Carl

Ran the touched test files, ruff, mypy and a function-size scan; checked `requests` `Session.send` and `CaseInsensitiveDict.pop` for the redirect hook.

[CARL] ✅ No issues found

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

Verdict: 14 findings
Tests: 8968 passed, 0 failed, 17 skipped (suite run this cycle)
