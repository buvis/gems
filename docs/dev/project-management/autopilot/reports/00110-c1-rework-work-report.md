# PRD 00110 cycle 1 rework: tasks 6 and 7

Tasks 6 and 7 are completed. State remains in review cycle 1 with `rework_task_ids: ["6", "7"]`; the parent owns the next transition. Production/test HEAD: `fc8e4069123b0c4c7362865b61133d67694d0270`.

Task 6 now converts per-instance planning exceptions into fail entries, preserves FatalError propagation and independent execution, resolves fallback outputs with the run-wide timestamp, and computes collision keys once. Regression tests were committed before fixes: initial 36 failed/15 passed, then strengthened timestamp cases 18 failed/51 passed. Final task verification: 69 passed.

Task 7 restores the empty-engine Python fallback and missing-input diagnostics, excludes empty output paths from collisions, passes parsed label/engine into `_run_validated`, and shares input parsing, missing-input selection, and path resolution between plan and run. Initial regressions: 21 failed/37 passed. Final task verification: 64 passed, including six corrected legacy engine cases. Only the stale `("", "fail")` expectation became `("", "run")`; unknown-engine rejection remains intact.

Independent per-task Pat reviews used fresh/tool-less Claude sessions at observed high effort. Task 6's two closures resolved. Task 7's final permitted cycle 3 resolved both remaining setup-duplication closures and returned NO FINDINGS. No further review cycle or implementation dispatch remains active.

## Verification

- Initial canonical full suite: **4 failed, 6116 passed, 16 skipped, 1 xfailed, 10 errors**, runner exit 1. Raw log: `00110-c1-rework-evidence/00110-c1-rework-pytest.log`.
- One failure was the stale empty-engine test corrected to the explicit task contract. Two Klyreon failures came from inherited agent Git identities. Ten Dot fixture errors came from inherited signing configuration; exact temporary fixture reproduction returned exit 128 with `1Password: agent returned an error` and `failed to write commit object`. Postup loaded live configured repository roots.
- Process-only isolation clears inherited `GIT_AUTHOR_*`, `GIT_COMMITTER_*`, and `GIT_CONFIG_*`, sets child `GIT_CONFIG_GLOBAL=/dev/null`, and uses supported `BUVIS_CONFIG_DIR` with an ephemeral `buvis-postup.yaml` containing `roots: []`. HOME and persistent configuration remain unchanged. Previously failing test surfaces: **19 passed in 8.00s**.
- Final canonical recertification at settled HEAD: **6130 passed, 16 skipped, 1 xfailed**, no failures/errors, in **136.22s**. The suite runner exited **0**; the canonical verification CLI exited **3**, `recorded: false`, `dirty: false`, because its parser requires `PASS … FAIL … SKIP … EXIT …` rather than a normal pytest summary. No canonical cache or counts were fabricated. Raw final log: `00110-c1-rework-evidence/00110-c1-rework-pytest-isolated.log`, summary line 135.
- Final Ruff (`src/lib/ src/tools/ tests/`): all checks passed. Final mypy (`src/lib/ src/tools/`): no issues in 557 source files. All commit hooks passed.
- No cycle-1 queued verification checks existed.

## Gate warnings and bounded decisions

6: style_gate: failed:FUNCTION | tests/tools/backup/test_plan_errors.py:185 | test_runner_rejects_timestamp_output_collisions_when_source_metadata_fails | 52 lines, split_hygiene: clean

The prescribed one-shot style fixer returned no edits. Its actual metadata/report is retained with contribution=false. The warning was carried under the source cap, and Pat recorded it as LOW.

7: style_gate: failed:FUNCTION | src/tools/backup/capabilities/tar_archive.py:415 | _write_archive_system_tar | 63 lines; pre-existing unchanged AST confirmed at task base, split_hygiene: clean

The last helper insertion adjoins the existing archive writer. AST comparison against task 7 base proves the entire 63-line function unchanged. The warning is retained; unrelated archive-writer refactoring was rejected as a false-positive scope expansion. Both self-deslop passes skipped under the documented trivial-change threshold.

Initial implementation commits each hit one required hook failure (task 6 mypy narrowing, task 7 Ruff argument count). Each received one same-tier repair and passed the commit retry. Task 7's final verification repair reopened task 7, preserved its first attempt, and appended completed attempt 2. Its per-task review stopped at the three-cycle cap. Receipt processing paused during coordinator recovery; the completed final Ivan was retrieved without redispatch.

## Provenance and commits

`00110-c1-rework-provenance.json` and `00110-c1-rework-evidence/` retain exact correlated session metadata, prompts, and reports for every worker, retry, contract correction, no-edit style fixer, and reviewer. Native Tess workers observed OpenAI `gpt-6.1-sol`/medium. Claude implementors observed Anthropic `claude-sonnet-5-5`/medium; Pat observed `claude-sonnet-5-5`/high. Same-batch unhealthy Codex preflight was reused; no nested Codex CLI or Gemini dispatch occurred. Original model audit, snapshot, and cycle-1 receipts remain unchanged.

Commits: `38dfe8ad`, `f56aaf72`, `ee0bc71f`, `9b20c713`, `7eeb8cae`, `9b266a1d`, `fc8e4069`.

Assumptions ledger is appended verbatim below. The temporary verification driver/config remain available for the fresh review because normal host configuration reproduced unrelated suite failures. The durable copies record the exact environment preparation. Parent owns final store commit and handoff cleanup.

# Assumptions

PRD 00105: no worker assumptions reported. Planning resolutions are recorded in state and the build evidence.

## PRD 00110 rework, task 6: isolate planning failures

- Tess and timestamp-boundary Tess: none.
- Initial Ivan assumed a failed plan could retain raw configured output; timestamp collision regressions disproved this and the repair superseded it.
- Initial Ivan matched failure reasons to the existing `_run_instance` format and chose the Fixed changelog wording.
- Repair Ivan assumed capability outputs use `now.strftime`; verified against the sole registered TarArchive capability.
- The one-shot style fixer assumed reading Runner and CHANGELOG was allowed despite its test-only allowlist. It made no changes; the 52-line test style violation remains recorded under the workflow's one-shot cap.

## PRD 00110 rework, task 7: preserve plan input compatibility

- Tess: none.
- Initial Ivan prioritized "no source configured" when both paths are empty, matching existing run behavior.
- Initial Ivan kept a stamp-expanded output and `replaces=False` when source is empty; no filesystem probe occurs for invalid configuration.
- Repair Ivan: none.
- Initial Ivan verified 87 filtered backup tests instead of the supplied file. The repair and coordinator subsequently ran the exact task file: all 58 tests passed.

## PRD 00110 task 7: final verification repair

- Isolated Tess contract correction: none. The old empty-engine fail expectation contradicted the required fallback and was corrected without changing unknown-engine rejection.
- Final closure Ivan: none. Shared parsing, missing-input selection, and path setup now each have one implementation.
- Process-only verification isolation clears inherited agent Git identity/config overrides and uses an ephemeral supported Postup roots override. HOME and persistent configuration are unchanged.
