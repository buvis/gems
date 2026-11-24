---
design: skip
default_model: sonnet
model_tier_rationale: One handler flag with an exact render rule and a measured reproduction; every check fails loudly.
---
# A log record with a long path is hard-wrapped in the middle of a word

Source: agoge run 2026-11-23, finding 19 of 21 (LOW, verified, lane wendy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

The log handler that `--debug` and `log_level` install wraps each record at the terminal width. A long path in a record is split in the middle of a word, with padding and an indent on the next line. Without `--debug` the same text prints on one line, because the probed range gave console errors `soft_wrap` for this exact reason.

If unchanged, paths in debug output cannot be copied whole. The defect is cosmetic.

## Solution

The accepted option is "give the handler's console soft wrapping". Measured on 2026-11-23 with Rich 15.0.0, that alone changes nothing: `RichHandler` renders each record as a table, and a table cell wraps at its column width whether `soft_wrap` is set on the `Console` or passed to `print`. The reproduction is in Test Strategy. So the soft wrapping is done inside the handler, which keeps the option's intent and the level styling.

**Handler** (`src/lib/buvis/pybase/adapters/console/capturing_rich_handler.py`): `CapturingRichHandler.__init__` gains a keyword-only argument `soft_wrap: bool = False`, stored as `self.soft_wrap`.

- `soft_wrap=False` (default): `emit` is unchanged (format, render the table, print).
- `soft_wrap=True`: `emit` formats the record, builds the message with `self.render_message(record, message)`, and prints one text line: `self.console.print(Text.assemble(self.get_level_text(record), " ", message_renderable), soft_wrap=True)`. The level keeps its style and its 8-character padding, so the line starts the same way as today (`DEBUG    probe.tool: ...`). The time and path columns are not printed in this mode.

**Log settings** (`src/lib/buvis/pybase/configuration/click_integration.py`, `_apply_log_settings`): build the handler with `CapturingRichHandler(console=console.err_console, show_time=False, show_path=False, soft_wrap=True)`.

Unchanged: the stream (stderr), the formatter (`%(name)s: %(message)s`), the filter that drops bridged config warnings, the restore on command exit, and `logging_to_console` in `console.py` (it keeps the table render).

## Requirements

### Must have
- A `CapturingRichHandler(console, show_time=False, show_path=False, soft_wrap=True)` on an 80-column console prints a record whose message is `template /tmp/` + 200 times `a` + `/bad.yaml` as exactly one line that holds the whole path.
- The same handler prints the level name (`INFO`) at the start of the line.
- A `CapturingRichHandler` built without `soft_wrap` still calls format, render_message, render and print in that order (`test_emit_calls_format_render_and_print_in_order` stays green unchanged).
- A `@buvis_options` command run with `--debug` that logs a 300-character path without spaces has the whole path, unbroken, in stderr.
- CHANGELOG.md `[Unreleased]` `### Fixed` gains: `- **config**: a log record printed under `--debug` or `log_level` is no longer hard-wrapped at the terminal width, so a long path stays in one piece.`

### Nice to have
- None.

## Implementation

### Module: log handler soft wrap
- **Location**: `src/lib/buvis/pybase/adapters/console/capturing_rich_handler.py`, `src/lib/buvis/pybase/configuration/click_integration.py`, `tests/lib/pybase/adapters/test_capturing_rich_handler.py`, `tests/lib/pybase/configuration/test_click_integration.py`, `CHANGELOG.md`
- **Responsibility**: Print each log record as one line and leave wrapping to the terminal.
- **Exports**: `CapturingRichHandler` gains the keyword-only argument `soft_wrap`.
- New symbols: `test_soft_wrap_prints_a_long_path_on_one_line`, `test_soft_wrap_keeps_the_level_name`, `test_debug_record_with_a_long_path_is_not_hard_wrapped`
- **Risk**: The change is not the literal accepted option: soft wrapping on the console has no effect on Rich's log table, so the handler prints a plain text line when `soft_wrap=True`. In that mode the time and path columns are dropped; `_apply_log_settings` already switches both off, so users see no difference there. A multi-line message (a record with newlines) loses the hanging indent that the table gave its later lines. A terminal wraps the long line at its own width, without the indent. No existing test pins the wrapped form: `test_emit_calls_format_render_and_print_in_order`, `test_emit_outputs_to_console` and `test_works_with_logging` use the default mode and must stay green unchanged; the `TestLogSettingsTakeEffect` tests assert on short probe texts and must stay green unchanged.
- **Risk (ordering)**: Sibling PRDs from the same run touch `click_integration.py`: 00164 (finding 5, the warning bridge), 00167 (finding 18, a log call right after `_apply_log_settings`; its tests compare with whitespace removed until this PRD lands). 00165 (finding 6) touches `console.py` only. The handler does not filter terminal control characters; 00164 names that as still open.

### Dependencies
- log handler soft wrap: No dependencies (foundation)

## Test Strategy

Regression check: the handler tests use the file's `rich_console` fixture (80 columns, a `StringIO` stream) and count lines in the stream. The wrapper test goes in `TestLogSettingsTakeEffect` and reads `result.stderr` from `CliRunner`; the adapter's `err_console` is not a terminal there and falls back to Rich's default of 80 columns, so a 300-character path is folded on the unmodified code. The test deletes `COLUMNS` with `monkeypatch.delenv("COLUMNS", raising=False)` before it builds the command, so a wide terminal setting cannot hide the fold.

Reproduction of why the console-level option has no effect, as it ran on 2026-11-23 (Rich 15.0.0, 40-column console, message `template /tmp/` + 60 times `a` + `/bad.yaml`). All three outputs are the same:

```
plain 'DEBUG    probe.tool: template           \n         /tmp/aaaaaaaaaaaaaaaaaaaaaaaaaa\n         aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n         aaa/bad.yaml                   \n'
print soft_wrap kw 'DEBUG    probe.tool: template           \n         /tmp/aaaaaaaaaaaaaaaaaaaaaaaaaa\n         aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n         aaa/bad.yaml                   \n'
console soft_wrap 'DEBUG    probe.tool: template           \n         /tmp/aaaaaaaaaaaaaaaaaaaaaaaaaa\n         aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n         aaa/bad.yaml                   \n'
```

The chosen render, same console and message, printed with `console.print(Text.assemble(handler.get_level_text(record), ' ', handler.render_message(record, message)), soft_wrap=True)`:

```
'DEBUG    probe.tool: template /tmp/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/bad.yaml\n'
```

The finding's evidence, verbatim:

```
**Evidence** (confirmed). `bim --debug create ...` at `COLUMNS=200`: the template path ends
`bad.yam` / `l` on two lines. Without `--debug` the same record is one line. The range gave
console errors `soft_wrap` for this exact reason.
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_soft_wrap_prints_a_long_path_on_one_line` and `test_soft_wrap_keeps_the_level_name` to `tests/lib/pybase/adapters/test_capturing_rich_handler.py`; watch them fail - Acceptance: `uv run pytest tests/lib/pybase/adapters/test_capturing_rich_handler.py -k soft_wrap` fails on the unmodified code.
- [ ] Add the keyword-only `soft_wrap` argument to `CapturingRichHandler` and the one-line render in `emit` (depends on: previous task) - Acceptance: `uv run pytest tests/lib/pybase/adapters/test_capturing_rich_handler.py` passes.
- [ ] Add `test_debug_record_with_a_long_path_is_not_hard_wrapped` to `TestLogSettingsTakeEffect` in `tests/lib/pybase/configuration/test_click_integration.py`; watch it fail - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_click_integration.py -k long_path_is_not_hard_wrapped` fails on the unmodified code.
- [ ] Pass `soft_wrap=True` to the handler in `_apply_log_settings` (depends on: second and third task) - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_click_integration.py -k "long_path_is_not_hard_wrapped or LogSettingsTakeEffect"` passes.
- [ ] Add the CHANGELOG line under `[Unreleased]` `### Fixed` - Acceptance: `rg -n "no longer hard-wrapped at the terminal width" CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest tests/lib/pybase/adapters/test_capturing_rich_handler.py tests/lib/pybase/configuration/test_click_integration.py -k "soft_wrap or long_path_is_not_hard_wrapped"` passes; the project's full test gate (`uv run pytest`) passes.
