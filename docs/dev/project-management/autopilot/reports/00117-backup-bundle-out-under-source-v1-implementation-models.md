# PRD 00117 implementation-model audit and recovery

Recovered 2026-11-05 from original Claude Code session and worker records.
All observed contributors to task 1 used `claude-sonnet-5-5` (Anthropic).
Launcher identity remains `claude`; the logical task tier remains `sonnet`.
The actual model comes from assistant `message.model` fields on implementation
edits, corroborated by worker metadata, not from a requested tier or reviewer.

## Correlation

Original parent session: `57552899-a733-45f0-8920-6d30f220db78`.
The byte-exact excerpts and original source-line mappings are retained in
`00117-recovery-evidence/manifest.json`; it includes source and line hashes.

- Tess dispatch `74aa6811`, worker `a579cbe6d9daf9b4a`: authored the two
  backup test files. Successful edit records include original lines 60, 65,
  74 and 90. Parent lines 363/366 and 380/381 correlate task, dispatch and
  worker; lines 468/471 record test commit `a7cf632a`.
- Ivan dispatch `ad135031`, worker `a24fe18c8d990062d`: authored
  `tar_archive.py` and `backup.rst`. Successful edit records include original
  lines 35, 38, 55 and 76. Parent lines 486/489 and 490/491 correlate the
  task and worker; lines 571/574 record implementation commit `d8e6bec6`.
- The parent is also an implementation contributor: original lines 548/550
  record its actual-model-bearing `CHANGELOG.md` edit and success.
  Parent line 445 records deterministic pre-commit formatting of the tests.

Both workers' observed models and `pickedEffortModel` metadata agree.
Fact-forcing hook rejections and successful retries are preserved; they did
not introduce another contributing model. The task's existing single completed
attempt remains intact. The audit includes each contributor within that attempt.
Planning and read-only reviewer models are excluded. Lost dispatch `e296a6b8`
is PRD 00109 work, not this task (original session
`2e7a0700-a2bd-4bfd-a75f-d3b1c457ed57`, lines 1987, 1990 and 1996).

The PRD implementation range is `5ae5c53e..d8e6bec6`, containing the two
commits above. Subsequent sysup/release commits are unrelated portfolio work;
the original `work_start_sha` remains unchanged. The new review must still
inspect current code and verify its applicable gates.

## Recovery disposition

The prior fast-track review cannot certify autocodex completion: it lacks
provider receipts, full required rubric evidence, and the provider guard.
Its exact bytes are preserved as `00117-recovery-evidence/original-review-1.md`.
The paused state is retained as `00117-recovery-evidence/paused-state.json`.
The original review is removed from the canonical cycle filename so
resume-by-artifact cannot silently skip the replacement review.

Resume at review cycle 1 with the obsolete `phases_completed: [review]`
marker cleared. Keep the completed task, PRD in wip, batch, cycle, work start,
and rework cap unchanged. This replaces invalid evidence; it neither consumes
nor raises the rework cap. No production or test implementation changed during
recovery. The user's interactive recovery request and standing authorization
cover these reversible corrections.

The verified route is the complete OpenAI Alice, Blake and Bob roster, using
`gpt-6.1-sol` at high effort through the host reviewer helper. Run all three
in fresh isolated external sessions with the complete source rubrics; preserve
Blake's PRD-only context. Do not reuse prior reviewer threads or claim their
old outputs supply receipts. Re-run `review-route` before dispatch.

The next session must use the full original work range, record valid receipts,
full rubric verdicts and `review_cycles`, adjudicate all findings using the
normal gate, and verify `adapter.review_gap` before the done handoff.
Recovery does not assert convergence or satisfy the provider guard.
A fresh review session is required before finalization.

## Cycle 2 audit

Original cycle 1 audit preserved in 00117-c1-implementation-models.json and .md. Original task 1 Anthropic evidence is unchanged. Task 2 Tess and Ivan raw session metadata and turn contexts show OpenAI gpt-6.1-sol/medium, including same-session retries. Dispatches ad588f5d/f9ec96bf and retries d7e0ed6e/fa6d26ec correlate to commits 80c90eca, 64458f89, 74d2e145 and 2698031c. See 00117-c1-rework-model-evidence/correlation.md and manifest.json. Pat performed read-only review and is excluded. Every cited line hash was checked before regenerating this cycle snapshot. Both complete provider rosters must review the entire PRD change.
