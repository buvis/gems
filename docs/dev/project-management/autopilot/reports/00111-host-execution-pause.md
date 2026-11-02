# Build pause: command approval timeouts

PRD: `00111-backup-parallel-jobs-and-cancellation-v1.md`.

The build is incomplete and paused at task 2's test quality gate. No completion review or phase advance ran. The coordinator used statectl to persist `pause_reason.site: host_exec_approval_timeout`, `phase: paused`, and `next_phase: paused`. The sibling paused-state snapshot preserves the checkpoint.

## Execution evidence

Default command execution failed with `sandbox-exec: sandbox_apply: Operation not permitted` at session start. Explicit escalated commands initially worked through automatic approval review.

Later, an optional scratch-prompt correction and scoped file listing failed before execution. Its one permitted retry also failed. A separate read-only `git diff --stat` failed the same way. Every result reported:

> The automatic permission approval review did not finish before its deadline. Do not assume the action is unsafe based on the timeout alone. You may retry once, or ask the user for guidance or explicit approval.

The subsequent statectl pause write succeeded after a delayed approval. Further checkpoint commands succeeded. This is an intermittent host approval failure, not a policy finding that these operations are unsafe. No guard, sandbox, nesting control, or permission mode was bypassed. The pause remains for attended recovery; this session does not clear it merely because later checkpoint commands worked.

## Preserved work

- Task 1 tests: `cd40e4e3`, strengthening `61501bd9`.
- Task 1 implementation: `455c9cba`; all commit hooks passed after one bounded Astra repair.
- Task 1 coordinator verification: 26 passed in 12.70 seconds; style and split hygiene clean; cleanup pass found no slop.
- Task 1 Pat review: unavailable because Claude weekly quota resets November 1 at 10:00 Europe/Prague. No review pass claimed. Raw quota output and prepared review context retained.
- Task 2 test author: `/root/tess2`, observed session `01a18c54-1211-7490-b364-eaa04fb32f6e`, OpenAI `gpt-6.1-sol`; raw session metadata and final result retained in sibling reports.
- Task 2 draft tests remain uncommitted: `test_parallel_runner.py`, `test_parallel_runner_lifecycle.py`, `parallel_runner_helpers.py`, and `test_plan_runner.py` under `tests/tools/backup/`.
- The task 2 author observed 19 failed, 2 passed, exit 2 in 5.25 seconds against the old runner, then corrected a coordinator-supplied interface typo without rerunning for counts. Targeted Ruff passed. Existing archive test bodies were reported unchanged.
- Task 2 coordinator quality gate, test commit, Devon, implementation, and task verification have not run. No runner implementation was dispatched. The aborted attempt records this distinction.
- Tasks 3–5 remain pending. No final suite or completion review ran.

## Recovery boundary

Use attended Resume after resolving the execution approval issue. Preserve batch identity, work base `9a7f78c8eb0e4148181584f92eb649cfec590034`, review cycle 1, and cap 2. Continue task 2 at the test quality gate against the existing draft; do not discard or blindly recreate its tests. Keep held PRDs and their evidence untouched. Capture any remaining raw contributor metadata before building the implementation-model audit. A fresh process must receive completion review after all work and verification finish.

## Agent self-debug report

- Failure: repeated pre-execution automatic approval deadlines, including a read-only command.
- Root cause: host approval infrastructure; commands were not judged unsafe.
- Recovery: one permitted retry, independent read-only check, then precise statectl pause and checkpoint.
- Result: blocked; pause persisted and no agent or reviewer process remains active.
- Risk: further retries could consume time without providing reliable execution.
- Follow-up: attended Resume; no cap increase or implementation repair is authorized by this pause.

## Interactive diagnosis, 2026-10-30

### Failure capture

- Session/task: interactive recovery of `a3e2a400dac044409603bd60651ac053`, task 2 test quality gate.
- Goal: establish whether unattended execution can safely resume with the existing draft tests.
- Error: the original automatic approval deadlines followed failed sandbox initialization.
- Last successful step: task 1 implementation `455c9cba`; pause checkpoint `6d4ac36d`.
- Failed probe: `codex sandbox -- /usr/bin/true` exits 71 with `sandbox-exec: sandbox_apply: Operation not permitted`, including with an escalated tool call.
- Repeated pattern: sandbox initialization fails before the requested command runs.
- Assumption checked: successful ordinary shell commands do not establish that Codex's own sandbox works.

### Diagnosis and contained recovery

`~/.config/bash/plugins/development.plugin.bash:426` starts the driver through `run-agent`. `~/bin/run-agent:132` applies the user-managed Seatbelt profile. `~/.config/autocodex/driver.py:154` additionally passes `--approve-for-me`; the installed Codex CLI help explicitly says that flag enables the workspace-write sandbox. This launch configuration nests sandbox initialization. The no-op probe reproduces the initialization failure, so the original blocker cannot be declared resolved merely because interactive shell execution works.

Ordinary `git diff --stat` and `git diff --check` succeed in the interactive host. This does not verify recovery of the prior headless automatic approval service. No inference of an unsafe command follows from its earlier timeouts.

The resolved host contract and installed run-autopilot resume instructions were read. `autopilot resume-target` returns `paused: await user`; driver status still reports 1/5 tasks completed. All four task 2 draft test files remain present. No tests, implementation, task status, cap, cycle, or work base were changed during diagnosis.

Proposed operator decision: retain the outer `run-agent` Seatbelt sandbox, replace the driver's `--approve-for-me` shorthand with explicit `--sandbox danger-full-access --ask-for-approval on-request -c approvals_reviewer=\"auto_review\"`, and verify the effective launch before resuming. This removes Codex's narrower workspace sandbox and therefore requires explicit security-change authorization. Automatic approval routing is a separate supported setting; retaining it does not mean every command receives review. The proposal has **not** been applied or runtime-validated. Direct driver launches without the outer sandbox must be addressed before applying this mode.

### Self-debug result

- Result: blocked on a security-configuration decision; original pause retained.
- Recovery action: inspected authoritative configuration and reproduced the failure with a no-op; preserved unfinished work.
- Time-burn risk: restarting unchanged can repeat sandbox failures and approval waits.
- Follow-up: resolve the launch policy, verify execution, then use the state CLI for attended Resume and preserve the fresh build/review boundary.
- Preventive change: preflight the effective execution sandbox before starting a long batch; never automatically weaken it after a failed probe.

## Approved launcher repair

The operator approved using outer Seatbelt protection while preserving automatic approval review. The prepared patch changes only `~/.config/autocodex/{driver.py,test_driver.py,README.md}` relative to their existing dirty contents. It uses an OS sandbox-presence probe, not an environment flag: only Darwin `sandbox_check(getpid(), NULL, 0) == 1` with no errno selects `--sandbox danger-full-access -c approval_policy="on-request" -c approvals_reviewer="auto_review"`. Without that confirmation, the original `--approve-for-me` policy remains. The shared argument builder covers coordinator and GPT reviewer launches; Claude's policy is unchanged. The probe establishes sandbox presence, not the identity of its profile.

Validation: targeted tests went from 8 failed/3 passed to 11 passed. Broader driver/role/quota checks passed 61 tests; two existing watchdog tests requiring `ps` fail under the outer sandbox and remain unchanged. Ruff passed for changed Python files. The patch passed `git apply --check`; all three live files still matched their pre-edit snapshots after the denied install attempts.

Both ordinary and escalated patch installation were denied by outer Seatbelt. The required warrant request is `39fae3167ec8b595ce48d927e3a0e6c5`, applying `docs/dev/tmp/autocodex-seatbelt-recovery/autocodex-seatbelt.patch` (SHA-256 `a3452a0bee9e1c53d75c2fa2ce4f336a290373cce562057ff435e4d235dc591a`). The operator must approve that request outside the sandbox. Keep the original pause until installation and a real Codex execution probe succeed, then resume task 2 at its existing test quality gate through the state CLI. No PRD implementation work has run during this recovery.

## Recovery completed

The operator approved warrant `39fae3167ec8b595ce48d927e3a0e6c5`; `warrant wait` returned 0 and all three installed files matched the tested patch byte-for-byte. The installed launch-policy tests passed: 11 passed, 21 deselected. The applied patch is preserved beside this report as `00111-autocodex-seatbelt-repair.patch`; existing unrelated dotfile changes remain uncommitted and intact.

A fresh real Codex process using the installed argument builder executed the read-only health command with default tool permissions. Its command output was `OUTER_SEATBELT 1 ERRNO 0`, a successful `git diff --stat`, and `EXECUTION_PROBE_OK`, exit 0. Evidence: `autocodex-sessions/recovery-seatbelt-smoke-retry.jsonl`. The first probe obeyed the facts hook but stopped without its requested retry; that evidence remains in `recovery-seatbelt-smoke.jsonl`. The second followed the hook's facts-and-retry procedure; no hook, nesting guard, or approval mode was bypassed. Both processes exited and were awaited. These diagnostic sessions contributed no implementation and must not be classified as PRD implementors.

Attended Resume used statectl to record the recovery decision, restore `phase` and `next_phase` to `build`, and clear `pause_reason`. Task 1 remains completed; task 2 remains in progress with its aborted attempt and draft tests preserved; tasks 3–5 remain pending. Batch `202610292344`, work base `9a7f78c8eb0e4148181584f92eb649cfec590034`, cycle 1, cap 2, and review requirements are unchanged. A fresh autocodex build session resumes task 2's test quality gate. No PRD completion is claimed.

Sandbox probe semantics were checked against Chromium's primary implementation: https://chromium.googlesource.com/chromium/src/+/master/sandbox/mac/seatbelt.cc . Automatic review remains explicitly configured, not forced for every command; its configuration is documented at https://learn.chatgpt.com/docs/config-file/config-reference .
