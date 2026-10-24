# PRD 00105 build evidence

## Bootstrap
- Host: autocodex; coordinator excluded from implementation provenance.
- Enter selected full lane, catchup full, design run; no prior tasks or pause.
- Catchup refreshed capsule; engram embedding endpoint refused connections, documented there.
- Planning Qwen preflight failed: endpoint_unreachable. No Qwen implementation dispatched.
- Source Codex interception doctor: 4 ok, 7 stale, 5 broken; first broken target /Users/bob/.codex/codex-hook. No live probe or external implementation dispatched; unhealthy batch probe recorded via statectl.
- Native OpenAI implementation workers have independent Anthropic review support in the host driver; native role mapping applies after source fallback.
- Native watchdog adaptation: asynchronous collaboration agents, completion notifications, 15-minute progress check and 45-minute hard cap; tool waits remain <=60 seconds.
- External wrappers retain nesting guards; no bypass flags or hook repairs.

## Design review transport
- Dispatch 1: isolated native gpt-6.1-sol/high; minimum-engagement retry requested.
- Dispatch 2 source external Codex role adapted to real personal use-sonnet wrapper, sonnet/high, read-only prompt, no bypass flags. Exited 1: OAuth session expired and could not be refreshed. Raw stderr/output retained at docs/dev/tmp/design-00105-review-2-output.txt; main session tool transcript records exit. Auth failures are not retried blindly.
- Source design-solution outage policy uses a fresh native fallback; selected gpt-6.1-sol/high, provenance stated explicitly rather than claiming Claude ran.

## Plan
- Three tasks: capability plus registry (coupled import/availability), configuration plus its assertion (coupled plan contract), and docs/changelog. Classifier results: sonnet/default, sonnet/floor, sonnet/floor; 62084, 63784, 88557 estimated tokens, all below 150000.
- check-plan exit 0. Full reviewed interface contract copied verbatim; acceptance clauses copied from PRD. Numeric suffix ambiguity resolves to a/b/rc plus digits, full-string matching; every unknown receipt key is rejected.
- No unresolved question prevents execution. Source design review uses legacy role tokens with actual host provenance stated in the log.
- Work start db6b1b434a88c84ce06d25e5773d0225d23de56b, captured once before implementation.

## Task evidence
- Task 1: test commit c261fd72, implementation 0bbe5e97, style fix 5026a1e0. 88 tests passed; red_check n/a:new_module; Tess shape/manual behavior review clean, style clean after one fix, split hygiene clean, self-deslop noop. A first plain uv run could not write its default cache; rerun with UV_CACHE_DIR under /tmp passed. Pre-commit formatter changes were restaged and commits retried once, preserving hooks.
- Task 1 Pat: full persona rendered, 39475 bytes; source tool-less Sonnet transport kept nesting guards and tools disabled. Requested high effort via CLAUDE_CODE_EFFORT_LEVEL. Authentication failed before a served model or review existed. Auth taxonomy forbids blind retry; record review failed:oauth_expired. Raw failure is retained in 00105-task-1-review-auth-failure.txt. No completion review substitution was attempted.
- Task 2: commit a177d948; 15 configuration tests passed. Tess/Devon/Pat skipped by source config-only gates; red_check n/a:config-only-task, style clean, split hygiene clean, self-deslop skipped:trivial (29 net lines).
- Task 3: commit e47252fa; documentation searches pass and Sphinx build exits 0. Source docs-only gates skip Tess/Devon/Pat; style clean (no Python), split hygiene skipped:no-tests, self-deslop skipped:trivial.
- Native worker reports: ASSUMPTIONS none for all contributors. Assumption ledger reset for this plan.
- Final static checks: mypy src/lib/ src/tools/ passed (557 files); Ruff src/ tests/ passed; actual registry import and Capability protocol check passed.
- Model audit preserves exact raw native session metadata, with SHA-256 line evidence for Tess, Ivan, style repair, configuration worker and documentation worker. Failed external auth and read-only reviewers are excluded from implementation contributors. Host review-route validated the audit and returned anthropic. Regenerate before fresh review cycle after cycle initialization.
- No temporary worktree or task branch was created; no executed plan artifact was added to the plans directory. Scratch prompts remain under ignored docs/dev/tmp for the active PRD.

## Full-suite host isolation
Initial full run: 5662 passed, 3 failed, 16 skipped, 1 xfailed (129.88s). No changed path belongs to klyreon or postup. Two klyreon tests tried default host lock paths outside sandbox writes; the postup test loaded the operator portfolio roots from host config. Rerunning exactly those three with writable XDG_STATE_HOME and a high-priority temporary postup roots:[] config passed 3/3 in 0.10s. No production or test code changed for this environmental repair.
A second full verification runs the identical pytest argv under those isolated directories, through docs/dev/tmp/verify-00105.py. The wrapper derives PASS/FAIL/SKIP/EXIT from the runner summary and preserves the real exit code; the initial raw pytest summary was not parseable by the source gate, so no first-run verification record was written. No failing test was deselected or weakened.

## Final gate and handoff
Full isolated gate: PASS 5665 FAIL 0 SKIP 16 EXIT 0 (plus 1 xfailed in pytest summary). autopilot verify exit 0; canonical last-verification.json recorded at e47252fa765fcd30876bb2145ac228d41e09295c. Initial and isolated raw logs retained alongside this report. Schema valid, tasks_total=tasks_completed=3, all attempts completed. All worker processes and agents awaited. No completion-review lens ran here. Source-required next gate is a fresh review session. Claude authentication is still expired; this build does not clear or work around it.
