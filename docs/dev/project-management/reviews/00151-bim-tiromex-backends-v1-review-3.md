---
prd: docs/dev/project-management/prds/wip/00151-bim-tiromex-backends-v1.md
review: 3
date: 2026-11-25
head_sha: b31de30b5559b9d2260ca045b07af80549e9b63f
codex_thread_id: 01a2115c-b6a3-7480-9a5c-69b481acf408
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: d5d197fe
  carl: b6931b17
---

# Review: 00151-bim-tiromex-backends-v1

Diff range: `22a5fa0da0e6abbc70c0b5df056c0dbcb5b3c198..b31de30b5559b9d2260ca045b07af80549e9b63f`

codex_rung_guard: not fired

Autopilot run, cycle 3 (rework cap 3), incremental review (`--since` the cycle-2 `head_sha`). Interactive session (no `$_AUTOPILOT_LOOP`), so no Watcher was dispatched. Consensus engine: legacy. Pack: ok. Bob ran on codex with the inlined prompt (201 KB), resuming his cycle-2 thread. Carl ran on copilot, model gemini-3.8-flash.

Scope: the only source change in range is task 12 (`217c7df1`): `run_cli` keeps the `shutil.which` result unnormalized, plus a symlink regression test. The other commits are autopilot bookkeeping.

Fail-first replay: 1 touched test ran, 1 failed against base `22a5fa0d`, 0 passed. The new symlink test pins the change. Tautology check: 7 test functions, no `[MECH]` lines.

Coordinator checks: Bob's R2 and R3 are confirmed by reading `src/tools/bim/shared/llm/base.py:312`. The line is `argv = [os.path.join(os.getcwd(), found), *argv[1:]]`: argv[0] is replaced, and `os.getcwd()` runs even when `found` is absolute.

Consolidation: the canonical script ran. No previous-cycle check queue exists (`checks-2.json` absent), so nothing carries forward. No doubt lens emitted a VERIFY item, so no check queue is written this cycle.

## Review Summary

Reviewed: task 12 (cycle-2 rework) in range; tasks 1-11 reviewed in earlier cycles
PRDs checked: 00151-bim-tiromex-backends-v1

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex, resumed thread)
- Carl: ✅ Available (copilot, gemini-3.8-flash)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🟡 | Behavior change beyond the spec. HTTP redirects are now refused and answered with an exit error, where the old `requests.post` followed them. The spec says doc behavior must be preserved. The change is documented in `docs/source/tools/bim.rst:1069` and `CHANGELOG.md:82`, but nothing in the PRD asks for it. | src/tools/bim/shared/llm/http.py:86 | Phase 1 HTTP adapters | BLAKE |
| R2 | [1/4] | 🟡 | Task 12 fixes executable selection across `symlink/..`, but still replaces `argv[0]` with the lookup result. A native executable can use `argv[0]` to select its behavior. Pass the selected path as `Popen(executable=...)` and preserve the original argv. Extend the regression test to check both values. | src/tools/bim/shared/llm/base.py:313 | 12 | BOB |
| R3 | [1/4] | 🟡 | The replacement calls `os.getcwd()` even when `shutil.which` returns an absolute path. If the launch directory was removed, a valid absolute executable now fails with a raw `FileNotFoundError`. Call `getcwd()` only for relative lookup results and test that an absolute executable still runs when `getcwd()` fails. | src/tools/bim/shared/llm/base.py:313 | 12 | BOB |
| R4 | [1/4] | ⚪ | Live Claude verification is incomplete. The docs say the probe could not authenticate, so the success-envelope key (`structured_output` vs `result`) was never observed. The adapter accepts both. This is disclosed in `docs/source/tools/bim.rst:1105`, so I count it as a documented residual risk. | src/tools/bim/shared/llm/claude.py:86 | Phase 1 Claude adapter | BLAKE |
| R5 | [1/4] | ⚪ | A malformed HTTP envelope, meaning an HTTP 200 whose body is not JSON, maps to `exit` (a transient error) rather than `parse`. This preserves the old behavior, where `response.json()` failures were treated as HTTP errors. A spec reader might expect `parse`. | src/tools/bim/shared/llm/http.py:186 | Phase 1 HTTP adapters | BLAKE |

### Auto-dismissed (ledger)

- [BLAKE] ⚪ Extra hardening the spec does not ask for: a 4 MiB reply cap, a 64 KiB stderr cap, and a separate `test_llm_transport_hardening.py`. The timeout text in triage reasons also changed to `[timeout] <backend>: ...` (`CHANGELOG.md:83`). Harmless, but it is scope growth and a change to triage text. | File: src/tools/bim/shared/llm/base.py:43 — single-voice
- [BLAKE] ⚪ The doc classifier and extractor never pass `unattended` to `registry.invoke`. A `command` backend with `unattended: false` therefore runs in doc with no refusal. No scheduled doc path exists today and the spec scopes scheduling to later work, so this is a latent gap. | File: src/tools/bim/commands/doc/shared/classifier.py:426 — settled re-raise of cycle-1 R45; also single-voice
- [BLAKE] ⚪ The acceptance commands `test_llm_backends.py -k command` and `-k claude` select nothing as literally written, because those tests live in `test_llm_command.py` and `test_llm_claude.py`. The PRD's build note (2026-11-24) records the file split, so the spec is amended, but the original command lines are stale. | File: tests/tools/bim/test_llm_backends.py — single-voice

## Alice

Cycle-2 R1 is resolved at `base.py:312`, and the new test at `tests/tools/bim/test_llm_transport_hardening.py:244` fails on the old `abspath` form (scratch probe with `os.path.samefile`). `test_llm_transport_hardening.py`: 14 passed. No regressions.

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

Six findings (R1, R4, R5 above, plus three auto-dismissed). Blind spec check: llm tests plus `tests/tools/bim/doc` 1458 passed; `claude --help` lists every isolation flag. B6 fails on the redirect behavior change (R1). No live probes against a real vault.

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

FIX bucket: R2, R3. VERIFY bucket: none. KNOWN bucket: none.

R1: fail
R2: pass
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

Ran the symlink test, the transport hardening tests, all `tests/tools/bim/test_llm_*.py`, ruff and mypy on the changed files.

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

Verdict: 5 findings
Tests: 8969 passed, 0 failed, 17 skipped (suite run this cycle)
