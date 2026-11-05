# Cycle 2 Tail sweep handoff

step: cycle 2 review converged; Tail sweep queued as tasks 3 and 4; resume at Tail sweep step 3
invariants: phase/next_phase remain review; cycle remains 2 and cap remains 2; original reviewed task 1/2 provenance, work_start_sha and cycle-2 implementation audit/receipts must remain unchanged
next: fresh session reads work skill and runs rework_task_ids 3,4 through normal work verification and per-task review; run sequentially because task 3 adds tests in the same file task 4 simplifies; preserve new case-alias/hard-link coverage
finalize: after sweep, keep cycle 2; do not run another completion roster; write the host-required tail-sweep-models.json companion for the entire task set, copying original audit evidence and appending every observed sweep contributor/retry; validate adapter.review_gap on an in-memory done candidate before phase-done --outcome converged and finalize handoff
evidence: review-2.md retains both complete provider rosters and six valid receipts; Anthropic Kiro observed claude-opus-5.5/xhigh; OpenAI gpt-6.1-sol/high requested. Alice/Blake OpenAI first transport-blocked attempts preserved; each fresh retry succeeded. adapter.review_gap=None; schema/counts valid; source gate and constraint passed. Structured full suite 6660 passed/0 failed/16 skipped, plus 1 xfailed; backup ruff/mypy passed. No implementation or stale worktree created in this review session.

Five shared Medium/Low findings span two pending sonnet tasks. Two single-voice Low findings were ledger-discarded. Original cycle-1 audit is retained in 00117-c1-implementation-models.json/.md; the canonical implementation audit now binds the reviewed cycle-2 two-task snapshot. Do not replace that snapshot with pending or completed sweep task provenance.

The source convergence and Tail sweep rules authorize the repairs but require a fresh work session in loop mode. The review session deliberately does not run phase-done while sweep tasks remain pending. Both current-cycle decision-gate and tail-sweep batches are recorded. Keep every raw log, failed first transport output, successful receipt and rubric.
