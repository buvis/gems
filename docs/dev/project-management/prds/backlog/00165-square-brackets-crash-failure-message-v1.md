---
design: skip
default_model: sonnet
model_tier_rationale: One escape call in one branch with exact tests; every check fails loudly.
---
# A file name with square brackets crashes the failure message or prints the wrong name

Source: agoge run 2026-11-23, finding 6 of 21 (MEDIUM, verified, lane heidi), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

`ConsoleAdapter.report_result` hands failure, warning, info and success text to Rich as markup. A `[...]` in a path is then read as a tag. A name such as `a[/b].txt` raises `rich.errors.MarkupError` and the user gets a traceback. A name such as `Album [live]/Song [remaster].txt` loses its bracketed parts, so the message names a file that does not exist.

If unchanged, `fren`, `puc`, `morph` and `muc` users meet this on any failure, because music and photo files often carry brackets. The same holds for `bim archive`, `bim show` and `bim delete --force`. The defect is older than the probed range.

## Solution

In `report_result` in `src/lib/buvis/pybase/adapters/console/console.py`, the inner `emit` function escapes the message in its non-literal branch: `reporter(escape(message))`, with `escape` from `rich.markup`.

This covers every message `report_result` prints by default: each `result.info` line, each warning, the success line (`success_msg` or `result.output`) and each failure line (`result.error` or `failure_msg`).

Unchanged:

- The `literal=True` branch (it already prints text without markup).
- The `on_success` and `on_failure` callbacks. They get the original result and print it themselves.
- Direct calls to `console.failure`, `console.warning`, `console.success`, `console.panic` and `console.info` outside `report_result`.
- Streams, markers, dedupe of an error that only repeats its warnings, and exit codes.

Finding 15 (`bim doc rules validate` and `rules test` in `src/tools/bim/doc_rules_cli.py`) is the same class at direct call sites. Another PRD owns those call sites. Do not touch them here.

## Requirements

### Must have
- `report_result(CommandResult(success=False, error="a[/b] [live]", warnings=["a[/b] [live]"]))` does not raise. It prints `a[/b] [live]` exactly once, on a ` ✘ ` line, and prints no ` ⚠ ` line (the error only repeats its warnings, so the existing dedupe prints it once).
- `report_result(CommandResult(success=False, error="No file could be renamed", warnings=["Album [live]/Song [remaster].txt"]))` prints `Album [live]/Song [remaster].txt` verbatim on a ` ⚠ ` line.
- `report_result(CommandResult(success=True, output="done a[/b]", info=["i [live]"]))` prints `done a[/b]` and `i [live]` verbatim.
- CHANGELOG.md `[Unreleased]` `### Fixed` gains: `- **console**: a failure, warning or success message that holds square brackets (a file name such as `a[/b].txt` or `Album [live]`) prints as written, instead of a traceback or a message with the bracketed part missing. This covers every command that reports through the shared result printer (`fren`, `puc`, `morph`, `bim` and others).`

### Nice to have
- None.

## Implementation

### Module: report_result escape
- **Location**: `src/lib/buvis/pybase/adapters/console/console.py`, `tests/lib/pybase/adapters/test_console_adapter.py`, `CHANGELOG.md`
- **Responsibility**: Print `CommandResult` text as text, not as Rich markup.
- **Exports**: none (the `report_result` signature does not change).
- New symbols: `test_square_brackets_in_a_failure_print_verbatim_and_do_not_raise`, `test_square_brackets_in_a_warning_print_verbatim`, `test_square_brackets_in_success_and_info_print_verbatim`
- **Risk**: A caller that passes Rich markup on purpose through `report_result` loses it and sees the tags as text. Checked on 2026-11-23: no call in `src/` passes `success_msg`; every `failure_msg` is plain text; `rg` for style tags (`[bold]`, `[dim]`, color names, closing tags) in `src/tools` and `src/lib/buvis/pybase` finds them only in the console adapter itself, `output_formatter.py`, `bim/tui/query.py` and `klyreon/cli.py`, none of which reach `report_result`. The existing `rich.markup.escape` callers (`sysup/cli.py`, `bim/shared/query_paths.py`, `bim/note_read_cli.py`, `bim/doc_cli.py`, `braid/cli.py`, `markdown_zettel_repository.py`) print through `panic`, `info`, `warning` or a direct console print, not through `report_result`, so nothing is escaped twice today. A future command that escapes its own text and then reports through `report_result` would show a stray backslash. The check was a text search; markup built at run time would not be found by it. Emoji codes (`:heart:`) are still replaced in the non-literal branch; only the literal branch keeps them. Direct `console.failure(msg)` calls stay open (finding 15). No existing test pins markup through the non-literal branch: `test_literal_messages_preserve_markup_and_emoji_codes` and `test_literal_failure_preserves_markup_then_exits` use `literal=True` and must stay green unchanged.
- **Risk (ordering)**: Sibling PRDs from the same run touch the same file: 00164 (finding 5, `format_*`, `info` and the literal branch of `report_result` in `console.py`). 00166 (finding 13) is done. 00167 (finding 18) and 00168 (finding 19) touch `click_integration.py` only. 00164 replaces each control character with `?` inside `format_*`, after this PRD's escape; that order is safe, because `?` cannot build a markup tag. Do not add a second filter call here.

### Dependencies
- report_result escape: No dependencies (foundation)

## Test Strategy

Regression check: three tests in `TestReportResult` print through a real `ConsoleAdapter` under `capsys` and compare the text. The first is the lane's proposed test. Its input makes the error equal to the joined warnings, so the existing dedupe prints the line once as a failure; the test asserts one occurrence, not two.

Measured on 2026-11-23 with Rich 15.0.0: `Console.print('[red]' + escape('a[/b] [live] :heart: path\\') + '[/red]')` writes `a[/b] [live] ❤ path\`. Brackets and a trailing backslash survive; the emoji code is still replaced.

The finding's evidence, verbatim:

```
**Evidence** (confirmed). `fren flatten` with a source `a[/b].txt` into a read-only directory ->
rc 1, 56-line traceback ending `rich.errors.MarkupError: closing tag '[/b]' ...`. Same crash for
`puc strip`, `morph pdf2png`, `bim archive`, `bim show`, `bim delete --force`. With
`Album [live]/Song [remaster].txt` the warning names `Album /Song .txt`, a file that does not
exist. Same at `669b74b6` (pre-existing).
```

The lane's proposed test, verbatim:

```
Proposed test: `report_result(CommandResult(success=False, error="a[/b] [live]",
warnings=["a[/b] [live]"]))` prints the text verbatim and does not raise.
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_square_brackets_in_a_failure_print_verbatim_and_do_not_raise`, `test_square_brackets_in_a_warning_print_verbatim` and `test_square_brackets_in_success_and_info_print_verbatim` to `TestReportResult` in `tests/lib/pybase/adapters/test_console_adapter.py`; watch them fail - Acceptance: `uv run pytest tests/lib/pybase/adapters/test_console_adapter.py -k square_brackets` fails on the unmodified code.
- [ ] Escape the message in the non-literal branch of `report_result` with `rich.markup.escape` (depends on: previous task) - Acceptance: `uv run pytest tests/lib/pybase/adapters/test_console_adapter.py -k "square_brackets or ReportResult"` passes.
- [ ] Add the CHANGELOG line under `[Unreleased]` `### Fixed` - Acceptance: `rg -n "holds square brackets" CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest tests/lib/pybase/adapters/test_console_adapter.py -k square_brackets` passes; the project's full test gate (`uv run pytest`) passes.
