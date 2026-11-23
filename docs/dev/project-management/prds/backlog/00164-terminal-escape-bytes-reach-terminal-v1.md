---
design: skip
default_model: sonnet
model_tier_rationale: One small filter with an exact character set, applied at named call sites; every check fails loudly.
---
# Terminal escape bytes in file names, query keys and config keys reach the terminal

Source: agoge run 2026-11-23, finding 5 of 21 (MEDIUM, verified, lane trudy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

Console messages print user text with ESC bytes intact. Rich drops BEL and CR, but ESC (U+001B) and the C1 controls pass through. The text comes from file names, inline query keys, `--config` paths, `DOTFILES_ROOT` and config key names. A config key in a `config.yaml` in the working directory reaches stderr through the unknown-key warning of any tool, with no user mistake needed.

If unchanged, a file name or a config key in a cloned directory can recolor, retitle, or erase and rewrite lines of tool output. The likelihood is low, but the attack is cheap to stage.

## Solution

Add one filter and apply it to message text only. The adapter's own styling (markers, Rich markup, colors) is not filtered.

**The filter.** A new module-level function `strip_control_chars(text: str) -> str` in `src/lib/buvis/pybase/adapters/console/console.py`. It removes every character that matches the regular expression `[\x00-\x08\x0b-\x1f\x7f-\x9f]`:

- C0 controls U+0000 to U+0008 and U+000B to U+001F (this includes ESC U+001B, BEL, CR, VT, FF).
- DEL U+007F.
- C1 controls U+0080 to U+009F (U+009B is a one-character CSI on some terminals).

It keeps TAB (U+0009) and LF (U+000A). Characters are removed, not replaced. Example: `strip_control_chars("a\x1b[31mb\x00\x07\x7f\x9bc\td\ne")` returns `"a[31mbc\td\ne"`.

**Where it applies** (`ConsoleAdapter` in `console.py`):

- `format_success`, `format_warning`: the `message` argument, before it is put between the style tags.
- `format_failure`: the `message` and the `details` arguments.
- `info`: the `message` argument.
- `report_result`, literal branch of the inner `emit`: the `message`, before `Text.append`.

`success`, `warning`, `failure`, `panic` and the non-literal branch of `report_result` are covered through the three `format_*` methods. The config error line in `click_integration.py` and braid's own lines already call `format_failure` / `format_warning`, so they are covered too.

**The warning bridge.** `_ConsoleWarningHandler.emit` in `src/lib/buvis/pybase/configuration/click_integration.py` sets `message = strip_control_chars(record.getMessage())` as its first step, before the `_seen` check. Two warnings that differ only in control characters then print once.

**Where it does not apply.** `ConsoleAdapter.print`, `render`, `print_side_by_side`, `status`, `confirm`, `choose`. These carry content (note bodies, tables), not status messages.

Streams, markers, exit codes and message wording do not change.

## Requirements

### Must have
- `strip_control_chars("a\x1b[31mb\x00\x07\x7f\x9bc\td\ne") == "a[31mbc\td\ne"`.
- `ConsoleAdapter.success`, `warning`, `failure` and `info` print no `\x1b` when the message holds `\x1b]0;TITLE\x1b[31mRED\x1b[0m`; the words `TITLE` and `RED` still print.
- `format_failure("m", "d\x1b[2K")` holds no `\x1b`.
- `report_result(CommandResult(success=False, error="x\x1b[31my"), literal=True)` prints no `\x1b`.
- `_ConsoleWarningHandler.emit` passes no `\x1b` to `err_console.print` for a record whose message is `key '\x1b[2K\x1b[1ATRUDY-KEY'`; the text `TRUDY-KEY` is still there.
- A message with a TAB and a newline keeps both in the string returned by `format_warning`.
- CHANGELOG.md `[Unreleased]` `### Fixed` gains: `- **console**: status messages (success, warning, failure, info) and config warnings no longer pass terminal control characters from file names, query keys or config keys to the terminal; the characters are removed, and tab and newline are kept.`

### Nice to have
- None.

## Implementation

### Module: console control filter
- **Location**: `src/lib/buvis/pybase/adapters/console/console.py`, `src/lib/buvis/pybase/configuration/click_integration.py`, `tests/lib/pybase/adapters/test_console_adapter.py`, `tests/lib/pybase/configuration/test_click_integration.py`, `CHANGELOG.md`
- **Responsibility**: Remove terminal control characters from status message text before Rich renders it.
- **Exports**: `strip_control_chars` (new, module-level in `console.py`).
- New symbols: `strip_control_chars`, `test_strip_control_chars_removes_c0_del_and_c1_but_keeps_tab_and_newline`, `test_status_messages_never_print_escape_bytes`, `test_failure_details_never_hold_escape_bytes`, `test_literal_report_result_never_prints_escape_bytes`, `test_warning_bridge_strips_escape_bytes_before_printing`
- **Risk**: A legitimate name that holds control characters is shown altered, so the printed name is not the name on disk. Command output echoed through `console.info` / `console.failure` (the shell adapter) loses its color codes and shows the leftover text such as `[31m`. Not covered, and still open after this PRD: content printed with `console.print` (note bodies), direct `Console(...)` objects that tools build themselves (`src/tools/klyreon/cli.py`), and log records printed by the `--debug` handler (`CapturingRichHandler`), which pass ESC through unchanged. No existing test pins ESC passing through a message. `test_format_success`, `test_format_warning`, `test_format_failure` and `test_handler_emit_dedupes_identical_message_but_not_distinct_ones` use messages without control characters and must stay green unchanged.
- **Risk (ordering)**: Sibling PRDs from the same run touch the same two files: 00165 (finding 6, `report_result` in `console.py`), 00166 (finding 13, `failure` / `panic` in `console.py` and the config error line in `click_integration.py`), 00167 (finding 18, the options wrapper in `click_integration.py`), 00168 (finding 19, `_apply_log_settings` in `click_integration.py`). With 00165 the order inside `report_result` is: strip first, then escape.

### Dependencies
- console control filter: No dependencies (foundation)

## Test Strategy

Regression check: the unit test on `strip_control_chars` pins the exact character set. The output tests print through a real `ConsoleAdapter` under `capsys` (no terminal, so Rich adds no color codes of its own) and assert that `\x1b` is absent. The bridge test patches `err_console.print` on the live adapter, as `test_handler_emit_dedupes_identical_message_but_not_distinct_ones` does.

Measured on 2026-11-23 with Rich 15.0.0: `Console.print(' x [bold]a\x1b[31mred\x07bel\rcr\x9b31m[/bold]')` writes `' x a\x1b[31mredbelcr\x9b31m\n'`. Rich drops BEL and CR and keeps ESC and U+009B.

The finding's evidence, verbatim:

```
**Evidence** (confirmed, output captured through a pipe). `bim show 'missing-<payload>.md'` ->
stdout contains `\x1b]0;TRUDY-TITLE\x1b[31mTRUDY-RED\x1b[0m`. Same for `bim archive`, an inline
query key, `sysup --config`, `dot unstage`, and a `DOTFILES_ROOT` name. A cwd `config.yaml` key
`"\e[2K\e[1ATRUDY-KEY"` reaches stderr in the unknown-key warning of any tool.
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_strip_control_chars_removes_c0_del_and_c1_but_keeps_tab_and_newline`, `test_status_messages_never_print_escape_bytes` (parametrized over `success`, `warning`, `failure`, `info`), `test_failure_details_never_hold_escape_bytes` and `test_literal_report_result_never_prints_escape_bytes` to `tests/lib/pybase/adapters/test_console_adapter.py`; watch them fail - Acceptance: `uv run pytest tests/lib/pybase/adapters/test_console_adapter.py -k "control_chars or escape_bytes"` fails on the unmodified code.
- [ ] Add `test_warning_bridge_strips_escape_bytes_before_printing` to `TestConsoleWarningBridge` in `tests/lib/pybase/configuration/test_click_integration.py`; watch it fail - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_click_integration.py -k warning_bridge_strips_escape_bytes` fails on the unmodified code.
- [ ] Add `strip_control_chars` to `console.py` and call it in `format_success`, `format_warning`, `format_failure` (message and details), `info` and the literal branch of `report_result` (depends on: first task) - Acceptance: `uv run pytest tests/lib/pybase/adapters/test_console_adapter.py` passes.
- [ ] Call `strip_control_chars` first in `_ConsoleWarningHandler.emit` (depends on: previous task) - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_click_integration.py -k "warning_bridge or handler_emit"` passes.
- [ ] Add the CHANGELOG line under `[Unreleased]` `### Fixed` - Acceptance: `rg -n "no longer pass terminal control characters" CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest tests/lib/pybase/adapters/test_console_adapter.py tests/lib/pybase/configuration/test_click_integration.py -k "control_chars or escape_bytes"` passes; the project's full test gate (`uv run pytest`) passes.
