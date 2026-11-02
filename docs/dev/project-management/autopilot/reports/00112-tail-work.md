# PRD00112 Tail work evidence

Only task6 and task7 rework, review_cycle1. Original tasks1–5 and original audit/receipts/evidence remain unchanged. Coordinator does no substantive implementation. Normal lane selected to preserve delegated implementation; task6 adds required regression test. Task6 logical sonnet native Tess runs gpt-6.1-sol/medium, observed in copied session turn_context. Devon tier gate skips at sonnet.

Task6 tests: behavior-specific names, real phase/content/output assertions, fsync/chmod/replace fault cases, two distinct labels/payloads, multi-element input plus empty member, near-miss labels/names, and persistent failure/output preservation. Empty whole-tree fallback is outside this finding (empty trees skip archive); no added speculative behavior. Shape checker and test style gate passed.
Test commit35897f21d9fed7764f8a6d5a234930fc7a70343f. Red check uv run --no-sync pytest tests/tools/backup/test_tar_fallback_progress.py -q --tb=line: exit1,6failed2passed in0.20s. All six fail at expected archiving phase after first finalizing.

Task6 implementation routing: backend row7 because qwen_eligible absent; two writable files after mandatory CHANGELOG coupling exclude Qwen with files/null preflight. User host substitution replaces source Codex implementor with real use-sonnet wrapper; no nested Codex CLI. Explicit sonnet/medium with isolated session de7bd933-5a45-467f-b1bf-7220f530edcc.

Task6 initial implementation614eff94 passed8new cases; selfdeslop skipped:trivial (net2lines,2files). Pat first (independent tool-less Claude Sonnet5.5/high) resolved both quoted findings, LOW duplicate early-fallback archiving. Existing immutable test_progress.py:406-410 proved exact prior event sequence, so bounded same-tier repair362ba76b... retained. Repair reports143passed across new+existing progress files. Commit ef9d192e preserves early-fallback sequence while restarting only after system finalizing. Coordinator narrow8passed0.13s. Reflow/style/split clean. Pat resumed delta (54d9ac9e) resolved duplicate; LOW finalize_once naming suggestion recorded, no correctness defect and source LOW row proceeds. No additional repair undertaken.

6: style_gate: clean, split_hygiene: clean
Task6 task-done atomic, attempt1,sonnet,lean,review_cycle1. Task7 documentation-only skips Tess/Devon/red and Pat per source class gates; substantive comments/docstrings delegated.

Task7 documentation commit312e7cd346604931f52ba5a72316d987a656b44f. Adds queue-binding rationale and Runner observer contract including calling-thread delivery, swallowed ordinary exceptions, dry-run/plan silence, .2second idle tick, short/nonblocking observers, held-yield exception; input-byte/unknown ProgressEvent docs. AST comparison stripping only docstrings confirms identical executable trees for both files. Reflow clean, task style clean. Selfdeslop skipped:trivial (net20lines,2files). Task7 task-done atomic, attempt1,sonnet,lean,review_cycle1.
7: style_gate: clean, split_hygiene: skipped:no-tests

All implementation provenance retained in00112-tail-evidence.json and raw copied logs. Tess is observed OpenAI gpt-6.1-sol/medium; both task6 implementor passes and task7 implementor observed Anthropic claude-sonnet-5-5/medium; Pat rounds independently observed claude-sonnet-5-5/high. Launcher and requested tier remain separate fields.

Final verification commands: canonical autopilot verify --cycle1 --gate-command 'python3 docs/dev/project-management/autopilot/reports/00111-verification-runner.py' --log docs/dev/tmp/00112-tail-full-suite.log. Reused unchanged prior isolation runner; no omitted tests. Product Ruff src/tests/tools passed; mypy557source files passed; Sphinx HTML passed. Canonical full suite passed:6380passed,0failed,16skipped,exit0; recorded=true,dirty=false at312e7cd346604931f52ba5a72316d987a656b44f. Raw gate log00112-tail-full-suite.log. No queued verification checks file for cycle1.

## Assumption ledger

# PRD 00112 assumptions

Task 1: Tess and Ivan reported ASSUMPTIONS: none.

## 2: Emit archive engine progress
Tess quality retry: Clearing PATH represents unavailable system tar; real fallback-message assertion passed. Other test writers and implementors reported none.

## 6: Tail sweep archive progress

Tess: System tar is available. Empty-input coverage uses an empty file. Persistent filesystem failure preserves the observed OSError behavior.

Ivan initial: Fallback retains the system-tar engine string so done_bytes remains None. The assumption that duplicate archiving on early fallback was acceptable was rejected against the existing exact-event test and corrected by the bounded repair. Ivan repair reported none.

## 7: Tail sweep observer documentation

Ivan: Plan suppression means the planning phase emits no progress events. The idle tick interval comes from completed.get(timeout=0.2). Coordinator verified both against Runner.plan/_plan and _collect_completion; paused-yield timing is stated explicitly.

## Installed-wrapper compatibility observation

Installed autopilot0.10.0 use-sonnet runner lacks an explicit --effort parser while its source work instructions require high effort for Pat. No plugin or old repository files were changed. Implementations used the standalone wrapper with explicit --effort medium. Tool-less Pat retained the installed wrapper and supplied CLAUDE_CODE_EFFORT_LEVEL=high; both raw reviewer turns verify observed effort high. This is a reported installed-plugin interface gap, not a change request executed in frozen buvis/claude-autopilot.

No new worktree or orphan branch was created. Task scratch files remain active pipeline evidence under ignored docs/dev/tmp; durable raw logs and reports were copied into autopilot/reports. Original task1–5 records, audit and receipts were not rewritten. Source telemetry rows were closed for all six dispatches; all workers and processes were awaited. No push, phase-done, cycle increment or completion-review reopening occurred. Parent owns companion audit and final handoff.
