# PRD 00110 host recovery

The installed autocodex adapter now accepts a verified canonical `cap_regression`
stall after a completed review. Warrant request
`b687d54ebd729ebf38e3fd782ab2023c` installed the fix after all **153 tests passed**.
The installer verified the original file hashes and preserved existing host edits.

Before the stall, `review-stall-snapshot` validated the existing review and saved
the full state to
`00110-backup-plan-preview-and-output-resolution-v1-cycle-2-cap-regression-boundary.json`.
The adapter revalidates provider receipts, rubrics, model audit, the intact PRD
move, migrated findings, and the canonical state reset at the boundary.

The canonical stall moved PRD 00110 from `wip` to `hold`, migrated all seven
cap-overflow findings, and cleared the host pause. The cap remains **2**.
`mint-stubs` created these hold PRDs:

- `00113-triage-r5-38dfe8ad-python-3-14-backup-tests-30-v1.md`
- `00114-triage-30-of-the-new-parametrized-cases-fail-on-v1.md`

`adapter.stall_review_gap` returns `None` for the recovered state and preserved
review snapshot. All 20 original review, receipt, raw-output and model-audit files
retain their pre-recovery SHA-256 hashes. No review was repeated and no backup
implementation or test was changed. The Python 3.14 regression remains tracked
in hold; this recovery does not claim that the PRD converged.

The queued phase is `build`, for a fresh session to select the next eligible PRD.
The host fix remains in the dotfiles working tree alongside earlier uncommitted
tail-sweep changes; those existing changes were not committed by this recovery.
