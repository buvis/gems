# Build evidence

PRD: `00109-backup-bundle-items-and-skip-outcomes-v1.md`.
Work base: `5a3ab34deb025e2a4223f9af876ec0256c2de177`.
Code selected fast-track, card_sized; one card rendered. Catchup and design skipped by PRD frontmatter. No foreign edits overlapped the ten card paths. Dependency 00107 implementation remains present on the working branch; its earlier batch-suite failure is retained in its report.

The host requires a fresh completion-review session for every lane. Tess and Ivan build steps ran here; no completion reviewer, convergence, lane_reviewed or finalize ran. Source Alice/Blake/Eve/Bob coverage is represented by the host three-lens Alice/Blake/Bob policy in a fresh process, with Bob retaining doubt and de-slop. Optional Carl omitted. A red batch suite prevents even the tasks_done handoff.

Both native workers ran logical opus, actual OpenAI gpt-6.1-sol/high, isolated from parent history. Full personas were assembled from installed source templates. The rendered card loses detailed functional decomposition, so Tess received the exact full PRD contract. Ivan received tests and bounded existing interface context, without PRD acceptance criteria. The first assembled Ivan prompt was measured but not dispatched at 100863 bytes; trimming complete relevant tests plus existing-test diff and public dependency interfaces reduced it to 49229 bytes. Only that bounded prompt was dispatched. Focused required selection helpers were permitted to satisfy mandatory Ruff complexity gates; no lint exemption or broad refactor was added.

Tess: /root/tess, session 01a189e3-fda3-7f33-a75e-a79c274a1805, dispatch f136dd3d. Ivan: /root/ivan, session 01a189ea-2b25-7660-b52b-8e814f9d387a, dispatch 328ad5f6. Observed turn_context and session_meta copies back the sibling implementation-model audit. The native provider has independent Anthropic review support. No implementation retry, model switch, unsupported provider fallback or escalation occurred. review-route validated fingerprint, line hashes and full task coverage and returned anthropic.

Tests committed as 877afe2d; implementation, guide and changelog as 3d4d2cd4. Initial Tess run: 69 failed, 49 passed, exit 1, before fixture corrections. Coordinator final red gate: `uv run pytest tests/tools/backup/test_skip_outcomes.py -k step_result -q`, 2 failed, 16 deselected, exit 1 (missing skipped field). Tests committed before implementation. First test commit attempt reformatted four test files through the required hook; restaging and retry passed every hook. Implementation commit passed every hook. No hooks bypassed. Worker final named-module suite: 118 passed.

Card gates in order:

1. `uv run pytest tests/tools/backup/test_skip_outcomes.py -k step_result -q`: 2 passed, 16 deselected, exit 0.
2. `uv run pytest tests/tools/backup/test_skip_outcomes.py tests/tools/backup/test_tar_archive.py -q`: 44 passed, exit 0.
3. `uv run pytest tests/tools/backup/test_bundle_items.py -q`: 34 passed, exit 0.
4. `uv run pytest tests/tools/backup/test_backup_cli.py -k "skip or summary" -q`: 12 passed, 24 deselected, exit 0.
5. `uv run pytest tests/tools/backup -q`: 210 passed, exit 0.
6. `uv run ruff check src/tools/backup tests/tools/backup`: clean, exit 0.
7. `uv run mypy src/tools/backup`: clean across 11 source files, exit 0.

Documentation acceptance: items appears seven times in guide; skipped appears ten times in changelog. Coordinator verified `_report_step` routes skipped results through console.warning and summary through console.info. Schema validation and 1/1 task-count consistency passed. git diff --check passed. No task-owned worktrees, branches or plan files were created. Live recovery prompt/card scratch remains under ignored docs/dev/tmp and must not replace durable evidence.

## Batch suite and disposition

`uv run pytest -q --tb=line`: 5822 passed, 3 failed, 16 skipped, 1 xfailed, 317 warnings, exit 1; pytest elapsed 178.30 seconds, subprocess elapsed 179.22 seconds. Full raw output: `reports/00109-batch-suite.log`.

- tests/tools/klyreon/test_vault_git.py::TestScopedCommit::test_commit_author_is_klyreon_identity: expected klyreon, observed Agent ran by Tomas Bouska (accented in raw log).
- tests/tools/klyreon/test_vault_git.py::TestAuthorship::test_human_authored_false_for_klyreon_only: expected False, observed True.
- tests/tools/postup/adapters/test_cli.py::TestCli::test_collect_runs_and_reports: expected no repositories; scanned operator portfolio and reported missing origin remotes.

These exact failures were already recorded in PRD 00107 build evidence before this PRD started. No unrelated repair or environment change was used to silence them. The fast-track Run step 4 mandates fast_track_blocked for any nonzero batch-suite exit. The canonical stall moves the PRD to hold and retains test/feature commits. The companion build-state snapshot preserves task/attempt provenance before the stall resets per-PRD state. Resume requires resolving the red batch suite, preserving this work base and all provenance, returning the PRD to the eligible lifecycle, and running fresh provider-routed completion review. No review file or successful review receipt exists for this build.

Dispatch counts:

fast-track:ivan 1
fast-track:tess 1

Command sandbox initialization failed sandbox_apply: Operation not permitted. Approved require_escalated commands executed the work; no approval denial occurred.
