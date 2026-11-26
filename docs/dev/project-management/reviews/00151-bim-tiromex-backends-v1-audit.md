# Decision Audit Log: 00151-bim-tiromex-backends-v1

PRD: `00151-bim-tiromex-backends-v1.md`
Started: 2026-11-26T12:24:26Z
Completed: 2026-11-26T12:24:26Z
Autonomous: 15  |  Deferred: 3  |  Doubts: 0

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: design paused: CS2/CS3/B5 fixes written after dispatch 3 were unverified

**Choice**: ran an isolated dispatch-4 verifier; all three FIXED, 0 cardinal-sin, 0 blocker; applied its 7 non-blockers (daemon thread + queue instead of ThreadPoolExecutor, 3xx and any-phase deadline rows, reader alive after join -> exit, prompt encoded before Popen, test fakes need close(), redirect change in Risks, stale communicate wording). Approach unchanged: shared registry in src/tools/bim/shared/llm, caller-owned schemas, doc passes JsonObject.

**Rationale**: the pause cause was missing verification, not a design defect

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: PRD task acceptance commands for the command and claude adapters name tests/tools/bim/test_llm_backends.py, which is already ~690 lines after the HTTP tests; adding both would break the 800-line file limit

**Choice**: command tests go to tests/tools/bim/test_llm_command.py and claude tests to tests/tools/bim/test_llm_claude.py, each test name still carrying the -k keyword; acceptance is run against those files

**Rationale**: the 800-line limit is a project rule; the acceptance intent (-k selected adapter tests pass) is unchanged

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: The HTTP reply cap misses redirect bodies. `requests.Session.send` can consume a redirect body while preparing `Response.next`, even with `allow_redirects=False` and `stream=True`. This occurs before `_download` sees the status. Use a transport path that returns the initial response without preparing the redirect. Test with real Requests and a loopback server that returns a `Location` header and a large body.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: A thread-start failure can leave a spawned CLI running because the cleanup `finally` starts after all three threads launch. Cover startup with process cleanup immediately after spawn, map startup failures to `exit`, and inject a thread-start failure in a test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: `_issuer_from_reply` is a verbatim copy of the existing `_resolve_model_issuer`, so the new helper is redundant and the diff touched working code. Delete `_issuer_from_reply` and call `_resolve_model_issuer(parsed, registry)` at classify_with_model (`(None, None, None) if doc_type_only`)

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: Nothing tests that `bim doc` passes `settings.llm` to the health checker and `get_pipeline`. The 6 call sites in doc_cli.py were changed. The CLI tests stub the checker with `lambda _s, _llm: None` and mock `get_pipeline` without checking its args. Dropping `settings.llm` from a call site would pass every test, and a named-backend config would only fail at run time. Capture the arguments and assert `settings.llm` arrives at both seams, for ingest and at least one other command

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: Three touched CLI tests keep an `or` hedge and pass against the pre-change code (fail-first replay). With the old 1-arg call, the new 2-arg `_raise` raises TypeError, so `exit_code != 0` is still true. They cannot fail on the behavior they claim to check. Assert `exit_code != 0 and "ocrmypdf" in result.output` (or the message each test raises), and have the stub record its `(settings, llm)` args

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: CLI preflight can find an executable through a relative path, then `Popen` looks for it from the temporary directory. Resolve the executable to an absolute path before changing the child's working directory. Keep the remaining arguments literal and test a relative executable. (Alice, same defect: `bim.rst` does not say that a command backend runs in an empty temp directory; add one sentence to the `command` bullet at docs/source/tools/bim.rst:1076.)

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: `_run` decodes stderr and stdout into `diagnostics` and `excerpt` on every call, including zero-exit runs with up to 4 MB of stdout. The result is used only on the non-zero-exit path. Compute it inside the `proc.returncode != 0` branch

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: R3 (high, Bob only): HTTP worker can stay blocked in a read after the deadline

**Choice**: discarded, recorded in the ledger; no task

**Rationale**: the design doc (Transport) accepts this residual: the caller is released at the deadline, the worker is a daemon holding one connection to a user-configured endpoint

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: R49 (low, Bob VERIFY): closeout mypy evidence open

**Choice**: routed to verification: uv run mypy src/lib/ src/tools/ (queued in checks-1.json); the coordinator also ran it at HEAD 2e525a31: no issues in 596 files

**Rationale**: a named check, not an implementation task

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: cycle 1 decision gate: 41 consolidated findings

**Choice**: 7 fix rows (R2, R4 high; R5, R6, R7, R12 medium; R38 low) became rework tasks 8-11; R43 deferred to batch end; R1, R37 and 29 single-voice medium/low rows discarded into the ledger

**Rationale**: R2 confirmed in requests sessions.py (redirect body read uncapped); multi-voice rows are mechanical fixes; single-voice medium/low rows are discarded by rule; R43 would change the approved design contract

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: `os.path.abspath(found)` can select a different executable from the one `shutil.which` checked. It collapses `..` after a symlink before the OS resolves the path. Make the lookup result absolute without normalizing its components, pass it as `Popen(executable=...)`, and keep the original argv. Add a symlink-path regression test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: cycle 2 decision gate: 14 consolidated findings

**Choice**: R1 (high, reproduced by coordinator probe) became rework task 12; R2-R14 discarded into the ledger

**Rationale**: R1 is a real wrong-executable path; R2/R3/R4/R14 restate settled cycle-1 rows; R13 verified by mypy; the rest are single-voice medium/low, discarded by rule

### [autonomous] 2026-11-26T12:24:26Z

**Decision**: cycle 3 decision gate: 5 consolidated findings, no critical or high

**Choice**: converged; R2 and R3 (Bob, verified at base.py:312) deferred to batch end; R1, R4, R5 discarded into the ledger; tail sweep skipped (no row raised by 2+ reviewers)

**Rationale**: R1 restates settled cycle-2 R2, R4 restates cycle-1 R1, R5 is the design's deliberate exit mapping; R2/R3 are real but single-voice medium at the cap cycle, so they stay visible as deferrals instead of being buried in the ledger

### [deferred] 2026-11-26T12:24:26Z

**Decision**: A named `ollama` or `openai` entry without `model` loads and passes health, then fails every doc call with a raw `LLMConfigError` (dispatch-1 notes NB2/NB10, left open). Rejecting it in `resolve_doc_route` at config load would be cheaper for the user. This is not a PRD requirement. (Bob: the approved design explicitly permits missing models during health and checks the effective model at invocation. Blake: in doc the error is caught as a generic exception and becomes a triage "classifier error".)

**Choice**: deferred

**Rationale**: deferred by review-close

### [deferred] 2026-11-26T12:24:26Z

**Decision**: Task 12 fixes executable selection across `symlink/..`, but still replaces `argv[0]` with the lookup result. A native executable can use `argv[0]` to select its behavior. Pass the selected path as `Popen(executable=...)` and preserve the original argv. Extend the regression test to check both values.

**Choice**: deferred

**Rationale**: deferred by review-close

### [deferred] 2026-11-26T12:24:26Z

**Decision**: The replacement calls `os.getcwd()` even when `shutil.which` returns an absolute path. If the launch directory was removed, a valid absolute executable now fails with a raw `FileNotFoundError`. Call `getcwd()` only for relative lookup results and test that an absolute executable still runs when `getcwd()` fails.

**Choice**: deferred

**Rationale**: deferred by review-close
