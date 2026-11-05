# PRD 00117 cycle 1 rework

Resumed queued task 2 through Phase 4 skip; no completion roster rerun in this session. Both original findings closed by Pat. Code normalizes once per run/plan and checks lstat identity against output and ancestors, preserving final symlink entries. Pat found an introduced identity OSError escape; one bounded retry added error conversion with regression coverage.

## Verification

- Initial red after test commit: 36 failed, 42 passed. Permission-error red: 12 failed, 78 passed. Final narrow: 90 passed, exit 0.
- Full suite through autopilot verify: 6660 passed, 16 skipped, 1 xfailed; suite exit 0, clean tree, no timeout. The helper returned recorded:false and raw_line:null because its parser did not accept the pytest summary. No last-verification.json was manually written; retained log is authoritative. Next review must follow its normal record-reuse/fallback rules.
- Full command: env -u GIT_AUTHOR_NAME -u GIT_AUTHOR_EMAIL -u GIT_COMMITTER_NAME -u GIT_COMMITTER_EMAIL BUVIS_CONFIG_DIR=/Users/bob/git/src/github.com/buvis/gems/docs/dev/tmp/verification-config uv run pytest -q --tb=short
- The config directory contains buvis-postup.yaml with roots: []; this overrides operator roots without changing tracked or machine config. Before the full run, the prior failing modules passed all 17 tests in that environment. Previous three host-dependent failures remain in original deferred evidence; none reproduced here.
- uv run ruff check src/tools/backup tests/tools/backup: passed. uv run mypy src/tools/backup: 11 files clean. Pre-commit checks passed for all four task commits.
- 2: style_gate: clean, split_hygiene: clean. self_deslop: skipped:trivial (implementation commits each touch one file). Devon skipped by sonnet lean pipeline. No cycle-1 verification queue. No reflow tripwire hits.

## Per-task review

Pat Sonnet/high, tool-less, session 6db57301-b9c5-41ee-a975-d9794f349780. First full review and one delta rerun parsed successfully. Both original findings resolved; introduced PermissionError MEDIUM resolved. Delta output upgraded a redundant guard from LOW to MEDIUM while also listing it LOW: adjudicated LOW because no correctness defect is asserted. All raw findings retained in 00117-c1-rework-model-evidence/pat-1.txt and pat-2.txt for cycle 2. No third dispatch or additional polishing.

## Provenance and assumptions

Tess and Ivan, including retries, used observed OpenAI gpt-6.1-sol/medium; raw session metadata and edit records copied with hashes and dispatch correlation. Logical sonnet, native Codex workers. Task attempt retains launcher codex separately from actual provider/model. Prior task 1 Anthropic provenance, original cycle-1 audit, snapshot and all receipts remain unchanged. Before cycle 2 regenerate canonical audit from both task sets and dispatch BOTH full independent provider rosters. No review dispatch is an implementation contributor.

All Tess and Ivan reports: ASSUMPTIONS: none. Existing meta/assumptions.md belongs to PRD 00112 and was preserved; no assumptions were appended.

Commits: 80c90eca tests; 64458f89 fix; 74d2e145 error tests; 2698031c error conversion. No stale worktree or branch created by this phase. Existing braid worktree is unrelated and retained.
