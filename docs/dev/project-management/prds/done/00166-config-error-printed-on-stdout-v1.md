---
design: skip
default_model: sonnet
model_tier_rationale: A stream change at five named call sites with exact tests per site; every check fails loudly.
---
# `bim create --json` prints a non-JSON line on stdout when the config fails to load

Source: agoge run 2026-11-23, finding 13 of 21 (LOW, verified, lane heidi), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

A config error is printed as a console line on stdout before the command starts. For `bim create --json` the stdout contract is one JSON object (AGENTS.md, "sanctioned exceptions"), and that failure class breaks it: stdout holds ` ✘ YAML syntax error in ...` instead. The same holds for every tool: the error line goes to stdout, while the bridged config warnings already go to stderr.

If unchanged, a script that parses stdout without checking the exit code first gets a parse error. The exit code is 1, so careful scripts are safe.

## Solution

Print config errors on stderr for every tool, through the console adapter's `err_console`. Message text, marker, soft wrapping and exit codes do not change.

1. **Shared settings errors** (`src/lib/buvis/pybase/configuration/click_integration.py`, the `except ConfigurationError` branch of the options wrapper): print with `console.err_console.print(console.format_failure(escape(str(exc))), soft_wrap=True)`. The exit code stays `config_error_exit_code` (1 by default, 2 for braid).
2. **Console adapter** (`src/lib/buvis/pybase/adapters/console/console.py`): `ConsoleAdapter.failure` and `ConsoleAdapter.panic` gain a keyword-only argument `stderr: bool = False`. When it is `True` the line prints on `self.err_console`; otherwise on `self.console` as today. `panic` still exits with code 1.
3. **sysup plan errors** (`src/tools/sysup/cli.py`): both handlers that catch `FatalError` from `load_config` (the root `cli` callback and `refresh`) call `console.panic(str(exc), soft_wrap=True, stderr=True)`. Exit code 1, as today.
4. **backup plan errors** (`src/tools/backup/cli.py`, `_load_config`): `console.panic(str(exc), soft_wrap=True, stderr=True)`. Exit code 1, as today.
5. **braid** (`src/tools/braid/cli.py`): the error line for `result.error` prints with `console.err_console.print(console.format_failure(escape(result.error)), soft_wrap=True)`. Exit code 2, as today. braid's warnings and its plan lines stay on stdout.

After the change, `bim create --json` with a broken config writes nothing on stdout, writes the ` ✘ ` line on stderr and exits 1. It does not emit `{"error": ...}` for this failure class: the config fails before the command and its `--json` flag are seen.

Not changed: `_instantiate_settings_or_exit` (the `--update` path) already writes `Configuration error: ...` on stderr. Runtime failures (`console.panic(str(exc))` after a runner `FatalError` in sysup and backup, and every `report_result` failure) stay on stdout.

## Requirements

### Must have
- A `@buvis_options` command run with `--config-dir missing-dir` exits with its config-error code, has `not a directory` in stderr and not in stdout.
- `ConsoleAdapter().failure("m", stderr=True)` writes `m` on stderr and nothing on stdout; `panic("m", stderr=True)` does the same and exits 1. Without the argument both still write on stdout.
- `sysup` with a `FatalError` from `load_config` has the message in stderr, not in stdout, and exits 1.
- `backup` with a `FatalError` from `load_config` has the message in stderr, not in stdout, and exits 1.
- `python -m braid --config <file with a malformed sources entry>` exits 2 with the key and the entry in stderr, not in stdout.
- `python -m bim create -t note --title Probe --dry-run --json` with `buvis-bim.yaml` holding `path_zettelkasten: [oops` exits 1 with empty stdout and `YAML syntax error` in stderr.
- CHANGELOG.md `[Unreleased]` `### Fixed` gains: `- **config**: configuration errors print on stderr for every tool (sysup and backup plan errors and braid's error line too), so stdout stays clean for machine-read output such as `bim create --json`. Exit codes do not change.`

### Nice to have
- None.

## Implementation

### Module: config errors on stderr
- **Location**: `src/lib/buvis/pybase/configuration/click_integration.py`, `src/lib/buvis/pybase/adapters/console/console.py`, `src/tools/sysup/cli.py`, `src/tools/backup/cli.py`, `src/tools/braid/cli.py`, `tests/lib/pybase/configuration/test_config_errors.py`, `tests/lib/pybase/adapters/test_console_adapter.py`, `tests/tools/sysup/test_sysup_cli.py`, `tests/tools/backup/test_backup_cli.py`, `tests/tools/braid/test_configured_paths.py`, `tests/tools/bim/test_create_note_cli_wiring.py`, `CHANGELOG.md`
- **Responsibility**: Send every config error line to stderr and keep stdout for command output.
- **Exports**: `ConsoleAdapter.failure` and `ConsoleAdapter.panic` gain the keyword-only argument `stderr`.
- New symbols: `test_settings_config_error_prints_on_stderr_not_stdout`, `test_failure_with_stderr_flag_prints_on_stderr_only`, `test_panic_with_stderr_flag_prints_on_stderr_and_exits_one`, `test_plan_config_error_prints_on_stderr_not_stdout`, `test_config_error_leaves_json_stdout_empty`
- **Risk**: The stream changes for every tool, so a script that reads config errors from stdout stops seeing them. A script that expects a JSON object from `bim create --json` on every failure gets empty stdout for this failure class and must check the exit code. braid has one error line for every `BraidError` and `OSError` (malformed `sources` / `policies` entries, no sources configured, state file and disk errors), and no error class separates config errors from the rest, so the whole line moves to stderr. **One existing test pins stdout and must change**: `TestMalformedConfiguredPaths.test_real_cli_exits_cleanly_without_filesystem_changes` in `tests/tools/braid/test_configured_paths.py` asserts `key in result.stdout` and `repr(entry) in result.stdout`; both assertions move to `result.stderr`. Tests that stay green unchanged, because Click 8.5 `CliRunner` puts stdout and stderr together in `result.output`: all of `TestConfigurationErrors` in `tests/lib/pybase/configuration/test_config_errors.py`, `TestSysupCliErrors.test_config_fatal_error_panics_not_traceback`, `TestBackupCliErrors.test_config_fatal_error_panics_not_traceback`, and the exit-2 tests in `tests/tools/braid/test_cli.py` and `tests/tools/braid/test_rules_cli.py`. The `isolated_config` fixtures in `test_config_errors.py` and `test_tool_config_keys.py` widen `console.console` to 240 columns; after the change the error prints on `err_console`, which they do not widen. The line is printed with `soft_wrap=True`, so paths stay whole and the fixtures need no change. Not covered: `bim doc` prints `issuers.yml` errors on stdout through `console.panic` (`src/tools/bim/doc_cli.py`).
- **Risk (ordering)**: Sibling PRDs from the same run touch the same two files: 00164 (finding 5, `format_*` in `console.py` and the warning bridge in `click_integration.py`), 00165 (finding 6, `report_result` in `console.py`), 00167 (finding 18, the options wrapper in `click_integration.py`, next to the error branch this PRD edits), 00168 (finding 19, `_apply_log_settings` in `click_integration.py`).

### Dependencies
- config errors on stderr: No dependencies (foundation)

## Test Strategy

Regression check: each call site gets a test that reads stdout and stderr apart. `CliRunner` results expose `result.stdout` and `result.stderr` (see `test_debug_records_print_on_stderr_not_stdout` in `tests/lib/pybase/configuration/test_click_integration.py`). The bim check runs a real subprocess, as `test_config_warnings_keep_json_stdout_parseable` does, with `HOME` set to a temporary directory and `BUVIS_AUTO_UPDATE=false`.

The finding's evidence, verbatim:

```
**Evidence** (confirmed). `buvis-bim.yaml` = `path_zettelkasten: [oops`;
`bim create -t note --title "Probe note" --dry-run --json` -> rc 1, stdout
` ✘ YAML syntax error in .../buvis-bim.yaml:2: ...`. Control: `-t nosuchtype` -> stdout
`{"error": "Unknown template: nosuchtype"}`. Baseline not checked.
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_failure_with_stderr_flag_prints_on_stderr_only` and `test_panic_with_stderr_flag_prints_on_stderr_and_exits_one` to `tests/lib/pybase/adapters/test_console_adapter.py`; watch them fail - Acceptance: `uv run pytest tests/lib/pybase/adapters/test_console_adapter.py -k stderr_flag` fails on the unmodified code.
- [ ] Add the keyword-only `stderr: bool = False` argument to `ConsoleAdapter.failure` and `ConsoleAdapter.panic` (depends on: previous task) - Acceptance: `uv run pytest tests/lib/pybase/adapters/test_console_adapter.py` passes.
- [ ] Add `test_settings_config_error_prints_on_stderr_not_stdout` to `TestConfigurationErrors` in `tests/lib/pybase/configuration/test_config_errors.py` (parametrized over braid `--check` and sysup `--list`, with `--config-dir missing-dir`); watch it fail - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_config_errors.py -k settings_config_error_prints_on_stderr` fails on the unmodified code.
- [ ] Print the `ConfigurationError` line on `err_console` in the options wrapper in `click_integration.py` (depends on: previous task) - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_config_errors.py` passes.
- [ ] Add `test_plan_config_error_prints_on_stderr_not_stdout` to `TestSysupCliErrors` in `tests/tools/sysup/test_sysup_cli.py` and to `TestBackupCliErrors` in `tests/tools/backup/test_backup_cli.py`; watch them fail - Acceptance: `uv run pytest tests/tools/sysup/test_sysup_cli.py tests/tools/backup/test_backup_cli.py -k plan_config_error_prints_on_stderr` fails on the unmodified code.
- [ ] Pass `stderr=True` at the two `load_config` handlers in `src/tools/sysup/cli.py` and at `_load_config` in `src/tools/backup/cli.py` (depends on: second task) - Acceptance: `uv run pytest tests/tools/sysup/test_sysup_cli.py tests/tools/backup/test_backup_cli.py -k "plan_config_error or config_fatal_error"` passes.
- [ ] Change `test_real_cli_exits_cleanly_without_filesystem_changes` in `tests/tools/braid/test_configured_paths.py` to assert the key and the entry in `result.stderr` and their absence from `result.stdout`; watch it fail - Acceptance: `uv run pytest tests/tools/braid/test_configured_paths.py -k real_cli_exits_cleanly` fails on the unmodified code.
- [ ] Print braid's `result.error` line on `err_console` in `src/tools/braid/cli.py` (depends on: previous task) - Acceptance: `uv run pytest tests/tools/braid` passes.
- [ ] Add `test_config_error_leaves_json_stdout_empty` to `TestCreateJsonStdoutContract` in `tests/tools/bim/test_create_note_cli_wiring.py` (depends on: fourth task) - Acceptance: `uv run pytest tests/tools/bim/test_create_note_cli_wiring.py -k config_error_leaves_json_stdout_empty` passes.
- [ ] Add the CHANGELOG line under `[Unreleased]` `### Fixed` - Acceptance: `rg -n "configuration errors print on stderr for every tool" CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest tests/lib/pybase/configuration/test_config_errors.py tests/lib/pybase/adapters/test_console_adapter.py tests/tools/sysup/test_sysup_cli.py tests/tools/backup/test_backup_cli.py tests/tools/braid tests/tools/bim/test_create_note_cli_wiring.py` passes; the project's full test gate (`uv run pytest`) passes.
