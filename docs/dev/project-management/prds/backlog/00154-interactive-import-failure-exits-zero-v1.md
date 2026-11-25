---
design: skip
default_model: sonnet
model_tier_rationale: A return value and one exit call with exact names; every check fails loudly.
---
# `bim import <missing file>` prints a failure line and exits 0

Source: agoge run 2026-11-23, finding 14 of 21 (LOW, verified, lane wendy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

The interactive form of `bim import` (no `--tags`, `--force` or `--remove-original`) prints its failure line and returns normally. `interactive_import` in `src/tools/bim/shared/import_helpers.py` returns `None` at both failure sites, and `import_note` in `src/tools/bim/note_write_cli.py` ignores the outcome.

The two failure sites:

- the path is not a file: ` ✘ {path_note} doesn't exist`
- the note has no ID: ` ✘ Note at {path_note} has no ID, skipping`

The scripted form (`--force`) exits 1 for the same missing path. The CHANGELOG console entry says failures now exit non-zero. `bim import x && next-step` runs the next step after a failed import.

## Solution

`interactive_import` returns its outcome as a `bool`, and the CLI exits 1 on `False`.

- Signature: `def interactive_import(path_note: Path, path_zettelkasten: Path, global_settings: GlobalSettings) -> bool`.
- It returns `False` after `console.failure(f"{path_note} doesn't exist")`.
- It returns `False` after `console.failure(f"Note at {path_note} has no ID, skipping")`.
- It returns `True` when the user declines the import (`_confirm_import` returns `False`, "Import cancelled by user"). A cancel is the user's choice, not a failure, and stays exit 0.
- It returns `True` at the end of a completed import.
- The two failure messages do not change.
- `resolve_output_path` does not change. Its `console.panic(f"Can't import {path_note}")` already exits 1.

In `import_note`, the interactive branch becomes: call `interactive_import(...)`; when it returns `False`, call `ctx.exit(1)`; then `return`. This matches the `ctx.exit(1)` the same function already uses for "interactive import requires a single path".

Exit codes for interactive `bim import`: 1 for a missing path, 1 for a note with no ID, 0 for a cancelled import, 0 for a completed import.

## Requirements

### Must have
- `bim import <missing path>` with no flags prints one ` ✘ ` line containing `doesn't exist` and exits 1.
- `bim import <note with no ID>` with no flags prints `has no ID, skipping` and exits 1.
- `interactive_import` returns `False` at both failure sites and `True` when the user cancels at the confirmation prompt.
- `CHANGELOG.md` gains this line under `[Unreleased]` / `### Fixed`: `- **bim**: interactive \`bim import\` (no \`--tags\`, \`--force\` or \`--remove-original\`) now exits 1 when the path does not exist or the note has no ID. Before, it printed the failure and exited 0. A cancelled import still exits 0.`

### Nice to have
- None.

## Implementation

### Module: interactive import outcome
- **Location**: `src/tools/bim/shared/import_helpers.py`, `src/tools/bim/note_write_cli.py`, `tests/tools/bim/test_note_write_cli_exit_code.py`, `tests/tools/bim/test_import_helpers.py`, `CHANGELOG.md`
- **Responsibility**: report the interactive import outcome to the CLI so a failure exits 1
- **Exports**: `interactive_import` (return type changes from `None` to `bool`)
- New symbols: `test_import_of_missing_path_exits_nonzero_without_flags`, `test_import_of_note_without_id_exits_nonzero_without_flags`, `test_cancelled_import_is_not_a_failure`
- **Risk**: A script that relied on exit 0 after a failed interactive import now stops. `test_import_existing_file` in `tests/tools/bim/test_note_write_cli.py` patches `interactive_import` with a `MagicMock` and asserts exit 0; the mock's return value is truthy, so it stays green unchanged, but an implementation that tests `is True` or `is False` would break it. Use `if not interactive_import(...)`. `interactive_import` has one caller (`import_note`), so the new return type breaks nothing else. No existing test pins exit 0 for a failed interactive import.

### Dependencies
- interactive import outcome: No dependencies (foundation)

## Test Strategy

The two CLI tests go in `tests/tools/bim/test_note_write_cli_exit_code.py`, class `TestImportExitCode`. Both patch `bim.note_write_cli.get_settings` with `_settings(tmp_path)` and run `bim import <path>` with no flags.

- `test_import_of_missing_path_exits_nonzero_without_flags`: the path does not exist. Assert exit code 1 and `doesn't exist` in the output.
- `test_import_of_note_without_id_exits_nonzero_without_flags`: the file exists; patch `bim.shared.import_helpers._load_note_for_import` to return a mock note with `id = None`. Assert exit code 1 and `has no ID, skipping` in the output with line breaks removed.

`test_cancelled_import_is_not_a_failure` goes in `tests/tools/bim/test_import_helpers.py`, class `TestInteractiveImport`. It mocks the console and the reader as the existing test in that class does, makes `console.confirm` return `False`, and asserts `interactive_import(...) is True`.

Hold stub `docs/dev/project-management/prds/hold/00145-triage-prd-metric-no-tool-cli-exits-0-after-pri-v1.md` was checked. It covers `report_result` callers in dot and postup that lack `exit_on_failure`. It is the same class of defect but a different gap, and this PRD does not close it.

Evidence from the report, verbatim:

```
**Evidence** (confirmed). `bim import missing-src.md` -> ` ✘ missing-src.md doesn't exist`, rc 0.
`bim import --force missing-src.md` -> same line, rc 1.
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_import_of_missing_path_exits_nonzero_without_flags` and `test_import_of_note_without_id_exits_nonzero_without_flags` to `tests/tools/bim/test_note_write_cli_exit_code.py`, and `test_cancelled_import_is_not_a_failure` to `tests/tools/bim/test_import_helpers.py`; watch them fail - Acceptance: `uv run pytest tests/tools/bim/test_note_write_cli_exit_code.py tests/tools/bim/test_import_helpers.py -k "exits_nonzero_without_flags or cancelled_import_is_not_a_failure"` fails on the unmodified code.
- [ ] Make `interactive_import` return `bool` as specified and make `import_note` call `ctx.exit(1)` on `False` (depends on: previous task) - Acceptance: `uv run pytest tests/tools/bim/test_note_write_cli_exit_code.py tests/tools/bim/test_import_helpers.py tests/tools/bim/test_note_write_cli.py` passes.
- [ ] Add the `### Fixed` line to `CHANGELOG.md` under `[Unreleased]` (depends on: previous task) - Acceptance: `rg -n "interactive .bim import." CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest tests/tools/bim/test_note_write_cli_exit_code.py tests/tools/bim/test_import_helpers.py tests/tools/bim/test_note_write_cli.py` passes; the project's full test gate (`uv run pytest`) passes.
