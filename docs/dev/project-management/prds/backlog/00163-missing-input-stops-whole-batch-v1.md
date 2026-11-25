---
design: skip
default_model: sonnet
model_tier_rationale: Three small CLI edits and one command check with exact messages; every check fails loudly.
---
# "Some inputs succeed, exit 0" is not true when the bad input is a missing path

Source: agoge run 2026-11-23, finding 20 of 21 (LOW, verified, lane wendy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

`morph pdf2png`, `puc strip` and `fren slug` stop before they process anything when one input path is missing. The changelog entry for these tools says that a run where some inputs succeed exits 0 with warnings. That is not true for a missing path.

- `morph pdf2png` and `puc strip` check every path in the CLI callback and stop at the first missing one with ` ✘ file not found: <path>`, exit 1.
- `fren slug` uses the parse-time validator `click.Path(exists=True)`, so Click prints its own `Usage: ... Error: Invalid value for 'PATHS...'` form and exits 2. This is against the "Click argument validation" rule in `AGENTS.md`.

One typo in a batch stops the whole batch. The three tools disagree with the `bim` batch commands, which warn and continue, and with their own changelog entry.

## Solution

The three commands warn on a missing input path and continue with the rest. A run where every input failed still exits 1 with the existing error. A partly good run exits 0 with warnings.

**`fren slug`** (`src/tools/fren/cli.py`). The `paths` argument type changes from `click.Path(exists=True)` to `click.Path()`. Nothing else changes: `CommandSlug.execute` already checks each path, adds the warning `Path not found: <path>`, continues, and fails with `No file could be renamed` when every input failed.

**`puc strip`** (`src/tools/puc/cli.py`). The loop that stops with `file not found: <path>` is removed from the callback. Nothing else changes: `CommandStrip.execute` already adds the warning `Skipping <path>: not a file`, continues, and fails with `No file could be processed` when no input was processed.

**`morph pdf2png`** (`src/tools/morph/cli.py`, `src/tools/morph/commands/pdf2png/pdf2png.py`). The loop that stops with `file not found: <path>` is removed from the callback. `CommandPdf2Png.execute` gains a check as the first step for each input, before the "output already exists" check: when `path.is_file()` is false, it adds the warning `File not found: <path>`, counts the input as failed, and continues. `<path>` is the path as the caller passed it. The end of `execute` is unchanged: when at least one input failed and none was converted, the result fails with `No file could be converted`.

Resulting behaviour:

| Command | Output | Exit |
|---|---|---|
| `fren slug "sl/Hello World.txt" sl/nosuch.txt` | ` ⚠ Path not found: sl/nosuch.txt`, then ` ✔ Renamed 1 file(s)`; the file is renamed to `hello-world.txt` | 0 |
| `fren slug sl/nosuch.txt` | ` ⚠ Path not found: sl/nosuch.txt`, then ` ✘ No file could be renamed`; no Click `Usage:` text | 1 |
| `puc strip pic3.jpg nosuch.jpg` | ` ⚠ Skipping nosuch.jpg: not a file`, then ` ✔ Processed 1 file(s)`; the good file is stripped | 0 |
| `puc strip nosuch.jpg` | ` ⚠ Skipping nosuch.jpg: not a file`, then ` ✘ No file could be processed` | 1 |
| `morph pdf2png fourth.pdf nosuch.pdf` | ` ⚠ File not found: nosuch.pdf`, then ` ✔ Processed 1 file(s)`; the PNG of the good file is made | 0 |
| `morph pdf2png nosuch.pdf` | ` ⚠ File not found: nosuch.pdf`, then ` ✘ No file could be converted` | 1 |

A missing external tool (`pdftoppm`, `exiftool`) still stops the command as today.

## Requirements

### Must have
- `fren slug <good> <missing>` through the CLI exits 0, the output holds `Path not found`, the output does not hold `Usage:`, and the good file is renamed.
- `fren slug <missing>` through the CLI exits 1, the output holds `No file could be renamed`, and the output does not hold `Usage:`.
- `rg -n "exists=True" src/tools/fren/cli.py` shows no hit on the `slug` command.
- `puc strip <good> <missing>` through the CLI builds `CommandStrip` with both paths; the callback does not stop on the missing one.
- `morph pdf2png <good> <missing>` through the CLI builds `CommandPdf2Png` with both paths; the callback does not stop on the missing one.
- `CommandPdf2Png.execute` with one good and one missing input returns `success is True`, `output == "Processed 1 file(s)"` and `warnings == [f"File not found: {missing}"]`.
- `CommandPdf2Png.execute` with only a missing input returns `success is False` and `error == "No file could be converted"`, also when a `.png` with the same stem exists.
- `CHANGELOG.md` gains this line under `[Unreleased]` / `### Fixed`: `- **fren**, **morph**, **puc**: \`fren slug\`, \`morph pdf2png\` and \`puc strip\` warn about a missing input path and go on with the rest, instead of stopping before any file is processed. A run where every input failed still fails. \`fren slug\` reports a missing path through the console instead of Click's \`Usage:\` error.`

### Nice to have
- None.

## Implementation

### Module: missing input is a warning
- **Location**: `src/tools/fren/cli.py`, `src/tools/puc/cli.py`, `src/tools/morph/cli.py`, `src/tools/morph/commands/pdf2png/pdf2png.py`, `tests/tools/fren/test_cli_exit_code.py`, `tests/tools/puc/test_cli_exit_code.py`, `tests/tools/morph/test_cli_exit_code.py`, `tests/tools/morph/test_pdf2png.py`, `CHANGELOG.md`
- **Responsibility**: let the three batch commands warn on a missing input and process the rest
- **Exports**: none
- New symbols: `test_slug_missing_path_is_a_warning_and_the_rest_is_renamed`, `test_slug_with_only_missing_paths_fails_through_the_console`, `test_strip_missing_file_reaches_the_command`, `test_pdf2png_missing_file_reaches_the_command`, `test_missing_input_is_a_warning_and_the_rest_is_converted`, `test_missing_input_fails_even_when_its_png_exists`
- **Risk**: A typo no longer stops the run; for a rename tool, fail-fast on a typo is arguably safer. The message `file not found: <path>` disappears from `morph pdf2png` and `puc strip`; the three commands keep three different warning texts (`Path not found`, `Skipping ...: not a file`, `File not found`), and this PRD does not unify them. No existing test pins the old behaviour: no test in `tests/tools/morph`, `tests/tools/puc` or `tests/tools/fren` asserts the CLI `file not found` stop or the Click `Usage:` error, and the command-level tests `test_nonexistent_path` (fren) and `test_file_not_found` (puc) already pin the warnings and must stay green unchanged. `puc strip` still prints its status line with the count of all given paths, the missing ones too. Out of scope, same parse-time validator: `fren directorize`, `fren flatten` (its `source` argument) and `fren normalize` use `click.Path(exists=True, file_okay=False)` and still print Click's `Usage:` error for a missing directory. Out of scope, same fail-fast loop: `morph deblank` still stops at the first missing file with `file not found: <path>`. `morph html2md` already validates in the callback, and `puc` has no other command.

### Dependencies
- missing input is a warning: No dependencies (foundation)

## Test Strategy

CLI tests use the shared `runner` fixture or `CliRunner`, as their neighbours do.

- `tests/tools/fren/test_cli_exit_code.py`, class `TestSlugExitCode`, with the real `CommandSlug`:
  - `test_slug_missing_path_is_a_warning_and_the_rest_is_renamed`: `tmp_path / "Hello World.txt"` exists, `tmp_path / "nosuch.txt"` does not; exit code 0; `Path not found` in the output; `Usage:` not in the output; `tmp_path / "hello-world.txt"` exists.
  - `test_slug_with_only_missing_paths_fails_through_the_console`: exit code 1; `No file could be renamed` in the output; `Usage:` not in the output.
- `tests/tools/puc/test_cli_exit_code.py`, class `TestStripExitCode`: `test_strip_missing_file_reaches_the_command` patches `CommandStrip` the way the neighbouring tests do, returns a successful result, passes one real file and one missing path, and asserts exit code 0 and that the class was built with both paths in `files`.
- `tests/tools/morph/test_cli_exit_code.py`, class `TestPdf2PngExitCode`: `test_pdf2png_missing_file_reaches_the_command` does the same for `CommandPdf2Png`.
- `tests/tools/morph/test_pdf2png.py`, class `TestPdf2PngExecute`, with the patches `test_process_pdf` uses:
  - `test_missing_input_is_a_warning_and_the_rest_is_converted`: one good PDF and one missing path; `success`, `output == "Processed 1 file(s)"`, `warnings == [f"File not found: {missing}"]`, and the render subprocess ran once.
  - `test_missing_input_fails_even_when_its_png_exists`: only a missing PDF path, with a PNG of the same stem present; the result fails with `No file could be converted` and the warning is `File not found: <path>`, not the "output already exists" one.

Evidence from the report, verbatim:

```
**Evidence** (confirmed). `morph pdf2png fourth.pdf nosuch.pdf` -> ` ✘ file not found:
nosuch.pdf`, rc 1, and `fourth.png` was not made. `puc strip pic3.jpg nosuch.jpg` -> same, rc 1.
`fren slug "sl/Hello World.txt" sl/nosuch.txt` -> Click `Usage: ... Error: Invalid value for
'PATHS...'`, rc 2 (a parse-time validator, against the AGENTS.md rule; pre-existing). The `bim`
batch commands warn and continue instead.
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_slug_missing_path_is_a_warning_and_the_rest_is_renamed` and `test_slug_with_only_missing_paths_fails_through_the_console` to `tests/tools/fren/test_cli_exit_code.py`, `test_strip_missing_file_reaches_the_command` to `tests/tools/puc/test_cli_exit_code.py`, `test_pdf2png_missing_file_reaches_the_command` to `tests/tools/morph/test_cli_exit_code.py`, and `test_missing_input_is_a_warning_and_the_rest_is_converted` and `test_missing_input_fails_even_when_its_png_exists` to `tests/tools/morph/test_pdf2png.py`; watch them fail - Acceptance: `uv run pytest tests/tools/fren/test_cli_exit_code.py tests/tools/puc/test_cli_exit_code.py tests/tools/morph/test_cli_exit_code.py tests/tools/morph/test_pdf2png.py -k "missing_path or only_missing_paths or missing_file_reaches or missing_input"` fails on the unmodified code.
- [ ] Change the `slug` argument type in `src/tools/fren/cli.py` to `click.Path()` (depends on: previous task) - Acceptance: `uv run pytest tests/tools/fren -k "missing_path or only_missing_paths"` passes.
- [ ] Remove the missing-file loop from the `strip` callback in `src/tools/puc/cli.py` (depends on: previous task) - Acceptance: `uv run pytest tests/tools/puc` passes.
- [ ] Remove the missing-file loop from the `pdf2png` callback in `src/tools/morph/cli.py` and add the `File not found: <path>` check as the first step for each input in `CommandPdf2Png.execute` (depends on: previous task) - Acceptance: `uv run pytest tests/tools/morph` passes.
- [ ] Add the `### Fixed` line to `CHANGELOG.md` under `[Unreleased]` (depends on: previous task) - Acceptance: `rg -n "warn about a missing input path" CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest -m "fren or morph or puc"` passes; the project's full test gate (`uv run pytest`) passes.
