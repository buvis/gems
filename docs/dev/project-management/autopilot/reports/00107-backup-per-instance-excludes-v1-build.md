# Build evidence

PRD: `00107-backup-per-instance-excludes-v1.md`.
Work base: `4becb45eb3c0949544dfeec5ed3db3424bcbc4d5`.

Code selected `fast-track`, reason `card_sized`, and rendered one card.
Catchup and design were explicitly skipped by PRD frontmatter.
No foreign changes overlapped the six card paths.

The operator host contract requires a fresh completion-review session for every
lane. The card's Tess and Ivan build steps ran here; `tasks_done` hands off to
the complete provider-routed Alice, Blake, and Bob review in a fresh process.
No completion review ran in this build session, and `lane_reviewed` was not used.
The source Alice/Blake/Eve/Bob roster is replaced by the host's three complete
lenses, including Bob's doubt and de-slop rubric. Carl is optional and omitted.

Both substantive workers used the card's logical `sonnet` tier, mapped to native
OpenAI `gpt-6.1-sol`, medium effort, with no parent conversation. Their complete
personas were assembled from installed source templates. Anthropic's independent
review route is supported by the host driver; no unsupported implementor provider
was dispatched. No model escalation or retry was needed.

- Tess: `/root/tess`, raw session
  `01a189d7-f5f9-7962-93e8-7b375c13a24c`, dispatch `d4993abe`.
- Ivan: `/root/ivan`, raw session
  `01a189da-e63e-7032-a541-c532c47c0b8a`, dispatch `2029bfe3`.
- Tests committed as `74e19c78`; implementation and documentation as `182e9bd3`.

The initial required red gate returned exit 1: 15 failed, 3 passed, 4 deselected.
The failures named missing instance fields and `effective_excludes`.
After implementation, the complete new module passed 22 cases.

Card gates, in order:

1. Composition selector: 18 passed, 4 deselected, exit 0.
2. Runner/archive selector: 4 passed, 18 deselected, exit 0.
3. Inspection selector: 3 passed, 19 deselected, exit 0.
4. All backup tests: 142 passed, exit 0.
5. Ruff: clean, exit 0.
6. Mypy: clean across 11 source files, exit 0.

Documentation acceptance: `inherit_excludes` appears four times in the tool guide
and once in the changelog. Both scoped commits passed repository hooks (Ruff,
formatting, mypy, framework isolation, tool wiring).

The first test commit attempt stopped because the formatting hook changed the
new test file. The formatted file was re-staged and all hooks passed on retry.
No hooks were bypassed. The command sandbox could not initialize
(`sandbox-exec: sandbox_apply: Operation not permitted`); command executions used
approved `require_escalated` calls. No approval denial occurred.

## Batch suite and disposition

`uv run pytest -q --tb=line`: 5754 passed, 3 failed, 16 skipped, 1 xfailed,
317 warnings, exit 1, elapsed 192.25 seconds.

- `tests/tools/klyreon/test_vault_git.py::TestScopedCommit::test_commit_author_is_klyreon_identity`
  expected `klyreon`, observed `Agent ran by Tomáš Bouška`.
- `tests/tools/klyreon/test_vault_git.py::TestAuthorship::test_human_authored_false_for_klyreon_only`
  expected `False`, observed `True` for Klyreon's commit identity.
- `tests/tools/postup/adapters/test_cli.py::TestCli::test_collect_runs_and_reports`
  expected `no repositories`; output instead scanned the operator's portfolio
  and reported repositories with missing `origin` remotes.

These failures are outside the card's changed paths. Their pre-existing status
was not tested at the base commit; no baseline-green claim is made. No unrelated
implementation or environment change was made to silence them.

The fast-track runbook's Run step 4 requires `fast_track_blocked` on any nonzero
batch-suite exit. The PRD is therefore parked in `prds/hold/`; its test and feature
commits remain reachable on the working branch. No provider review, convergence,
or finalize claim is made. The companion build-state snapshot retains the task
and attempt metadata before the stall's canonical per-PRD reset.

Resume requires resolving the full-suite failures and returning the held PRD to
the eligible lifecycle, with the retained work base and model evidence preserved.
Completion review must still run in a fresh session with the entire provider
roster; this build session does not authorize skipping it.
