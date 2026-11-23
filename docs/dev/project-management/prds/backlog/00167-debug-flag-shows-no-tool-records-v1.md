---
design: skip
default_model: sonnet
model_tier_rationale: Two log points with exact record text, logger names and layer labels; every check fails loudly.
---
# `--debug` prints library noise or nothing; the tools themselves log nothing

Source: agoge run 2026-11-23, finding 18 of 21 (LOW, verified, lane wendy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

The probed range wired `--debug` and `log_level` to the `logging` module, but no buvis code emits a debug or info record that reaches the user. A user who passes `--debug` to diagnose a tool gets third-party chunk dumps (PIL) or an empty stderr.

If unchanged, `--debug` stays of little use, and the CHANGELOG entry and `docs/source/configuration.rst` promise more than users get.

## Solution

Add debug records at the two points a user asks about: which config files were read and from which layer, and which external commands run through the shell adapter. Records go through the `logging` module only (AGENTS.md: the library does not print outside the console adapter). Records hold keys and paths, never config values.

### 1. Config files read

**The gap to respect.** `ConfigResolver.resolve` runs before `_apply_log_settings` installs the stderr handler, so a record logged while the config loads is never shown. The resolver therefore keeps what it read, and the options wrapper logs a summary after the handler is installed.

**Resolver** (`src/lib/buvis/pybase/configuration/resolver.py`): `ConfigResolver` gains a read-only property `files_read` that returns a copy of `list[tuple[Path, str]]`: each YAML file the last `resolve()` call loaded, in merge order (lowest precedence first), with its layer label. `_load_yaml` clears the list at its start and fills it as each file loads. A resolve that fails leaves the files loaded so far.

Layer labels, compared on absolute paths, first match wins:

| Label | The file is |
|---|---|
| `explicit` | the `--config FILE` path (`config_path` is given) |
| `override` | in the override directory: `config_dir` when given, else `$BUVIS_CONFIG_DIR` when set and not empty |
| `local` | in `~/.local/.config/buvis` |
| `shared` | in `~/.config/buvis` |
| `cwd` | in any other directory (the working directory) |

**Options wrapper** (`src/lib/buvis/pybase/configuration/click_integration.py`): right after the `_apply_log_settings(...)` call, on the module logger `buvis.pybase.configuration.click_integration`, at `DEBUG`:

- one record per entry of `resolver.files_read`, in order: `config file read: %s (layer: %s)` with the path and the label;
- when the list is empty, one record: `no config file read`.

With `--debug` the user sees, on stderr, for example: `DEBUG    buvis.pybase.configuration.click_integration: config file read: /home/u/.config/buvis/config.yaml (layer: shared)`. Without `--debug` and without a `DEBUG` `log_level`, nothing prints.

### 2. External commands

**Shell adapter** (`src/lib/buvis/pybase/adapters/shell/shell.py`): a module logger `logging.getLogger(__name__)` (`buvis.pybase.adapters.shell.shell`). `ShellAdapter.exe` and `ShellAdapter.interact` log one `DEBUG` record right before `subprocess.run`: `running command: %s (cwd: %s)`.

The first argument is the command with a leading alias replaced by its registered body, **before** environment variables are expanded. An alias body `git --git-dir=${DOTFILES_ROOT}/.buvis/` is logged with `${DOTFILES_ROOT}` as written, so no environment value is copied into a log record. The second argument is the resolved working directory.

The record is logged whether or not `suppress_logging` is set. That flag only governs the console echo of the command's output, and `dot` sets it on every adapter.

### 3. Docs

`docs/source/configuration.rst`, the paragraph on `--debug` and `log_level`: keep "Records logged while the configuration itself loads are not shown." and add after it: "The config files that were read, and the layer of each, are logged once the configuration has loaded. Tools that run commands through the shell adapter log each command and its working directory."

## Requirements

### Must have
- `ConfigResolver.files_read` lists a `config.yaml` in `~/.config/buvis` and one in `~/.local/.config/buvis` as `shared` then `local`, in that order.
- `ConfigResolver.files_read` is `[(path, "explicit")]` after `resolve(..., config_path=path)`.
- A `@buvis_options` command run with `--debug --config-dir DIR`, where `DIR/config.yaml` exists, has `config file read: DIR/config.yaml (layer: override)` on stderr and not on stdout.
- The same command run with `--debug` and no config file anywhere has `no config file read` on stderr.
- The same command run without `--debug` prints neither text.
- With a config file that holds `adapters: {jira: {token: s3cret-7c1e}}` and `--debug`, `s3cret-7c1e` is in neither stdout nor stderr.
- `ShellAdapter().exe("echo hi", tmp_path)` logs `running command: echo hi (cwd: <tmp_path>)` at `DEBUG` on `buvis.pybase.adapters.shell.shell`; `interact` logs the same form.
- With `alias("cfg", "git --git-dir=${ROOT_7C1E}/.buvis/")` and `ROOT_7C1E=/secret-root` in the environment, the record for `exe("cfg status", None)` holds `${ROOT_7C1E}` and does not hold `/secret-root`.
- `ShellAdapter(suppress_logging=True).exe(...)` still logs the record.
- `rg -n "logged once the configuration has loaded" docs/source/configuration.rst` prints one line.
- CHANGELOG.md `[Unreleased]` `### Added` gains: `- **config**: `--debug` now names each config file that was read and its layer (`explicit`, `override`, `local`, `shared`, `cwd`) on stderr, and tools that run commands through the shell adapter (`dot`) log each command and its working directory.`

### Nice to have
- None.

## Implementation

### Module: debug records
- **Location**: `src/lib/buvis/pybase/configuration/resolver.py`, `src/lib/buvis/pybase/configuration/click_integration.py`, `src/lib/buvis/pybase/adapters/shell/shell.py`, `tests/lib/pybase/configuration/test_resolver.py`, `tests/lib/pybase/configuration/test_click_integration.py`, `tests/lib/pybase/adapters/test_shell_adapter.py`, `docs/source/configuration.rst`, `CHANGELOG.md`
- **Responsibility**: Give `--debug` records about config files and external commands, without config values.
- **Exports**: `ConfigResolver.files_read` (new property).
- New symbols: `files_read`, `test_files_read_lists_each_loaded_file_with_its_layer_lowest_first`, `test_files_read_labels_an_explicit_config_file`, `test_debug_names_each_config_file_and_its_layer_on_stderr`, `test_debug_says_when_no_config_file_was_read`, `test_config_file_records_are_silent_without_debug`, `test_config_file_records_hold_no_config_values`, `test_exe_logs_the_command_and_cwd_at_debug`, `test_interact_logs_the_command_and_cwd_at_debug`, `test_debug_record_keeps_alias_env_variables_unexpanded`, `test_command_is_logged_when_console_echo_is_suppressed`
- **Risk**: This is a feature, not a fix, and it widens what `--debug` prints for every tool. The shell adapter record holds the caller's command text: today's only caller is `dot` (git subcommands, paths, commit messages), but a future caller that puts a secret in a command line would have it logged at `DEBUG`. Only the shell adapter is covered: tools that call `subprocess` directly (`sysup`, `puc strip`, `morph pdf2png`, `backup` and others) log no command record, so for those tools `--debug` gains only the config-file records. The plan loaders of sysup and backup (`sysup.config.load_config`, `backup.config.load_config`) read their files in a second pass that is not logged; the settings pass reads the same discovered files, so the list is the same in practice. The update check resolves the config once more before the command and logs nothing. Records logged while the config loads (`Config '<field>' from <source>`) are still not shown. The `cwd` label exists only while the working-directory layer exists: the PRD for findings 2 and 3 of the same run drops that layer for every tool. No existing test pins the absence of these records: `test_no_log_output_unless_asked` and `test_debug_records_print_on_stderr_not_stdout` assert on the `probe-7c1e` text only and must stay green unchanged.
- **Risk (ordering)**: Sibling PRDs from the same run touch `click_integration.py`: 00164 (finding 5, the warning bridge), 00166 (finding 13, the config error branch right above the new log call), 00168 (finding 19, `_apply_log_settings`). 00165 (finding 6) touches `console.py` only. Until 00168 lands, the log handler hard-wraps a long record at the console width, so the new `CliRunner` tests must compare with all whitespace removed from both the expected text and `result.stderr`.

### Dependencies
- debug records: No dependencies (foundation)

## Test Strategy

Regression check: resolver tests read `files_read` directly, with `HOME` set to a temporary directory and every `BUVIS_*` variable removed (as the `isolated_config` fixture in `tests/lib/pybase/configuration/test_config_errors.py` does). Wrapper tests go in `TestLogSettingsTakeEffect` and run a `@buvis_options` command through `CliRunner`, reading `result.stderr` and `result.stdout` apart; they use the same isolation and compare with whitespace removed. Shell adapter tests use `caplog.at_level(logging.DEBUG, logger="buvis.pybase.adapters.shell.shell")` and mock `subprocess.run` as the existing tests in that file do.

The finding's evidence, verbatim:

```
**Evidence** (confirmed). `morph --debug pdf2png again.pdf` -> stderr
`DEBUG PIL.PngImagePlugin: STREAM b'IHDR' 16 13`. `sysup --debug --list`, `puc --debug strip` ->
stderr empty. So the entry is true, but a user who passes `--debug` to diagnose a buvis tool gets
PIL chunk dumps or nothing.
```

After this PRD, `sysup --debug --list` and `puc --debug strip` print the config-file records on stderr. The PIL records of `morph --debug` stay.

## Tasks

### Phase 0: Feature
- [ ] Add `test_files_read_lists_each_loaded_file_with_its_layer_lowest_first` and `test_files_read_labels_an_explicit_config_file` to `tests/lib/pybase/configuration/test_resolver.py`; watch them fail - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_resolver.py -k files_read` fails on the unmodified code.
- [ ] Add the `files_read` property to `ConfigResolver` and fill it in `_load_yaml` with the layer labels of the Solution table (depends on: previous task) - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_resolver.py` passes.
- [ ] Add `test_debug_names_each_config_file_and_its_layer_on_stderr`, `test_debug_says_when_no_config_file_was_read`, `test_config_file_records_are_silent_without_debug` and `test_config_file_records_hold_no_config_values` to `TestLogSettingsTakeEffect` in `tests/lib/pybase/configuration/test_click_integration.py`; watch the first two fail - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_click_integration.py -k "config_file"` fails on the unmodified code.
- [ ] Log the `files_read` summary in the options wrapper right after `_apply_log_settings` (depends on: second and third task) - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_click_integration.py -k "config_file or LogSettingsTakeEffect"` passes.
- [ ] Add `test_exe_logs_the_command_and_cwd_at_debug`, `test_interact_logs_the_command_and_cwd_at_debug`, `test_debug_record_keeps_alias_env_variables_unexpanded` and `test_command_is_logged_when_console_echo_is_suppressed` to `tests/lib/pybase/adapters/test_shell_adapter.py`; watch them fail - Acceptance: `uv run pytest tests/lib/pybase/adapters/test_shell_adapter.py -k "logs_the_command or alias_env_variables_unexpanded or command_is_logged"` fails on the unmodified code.
- [ ] Log the `running command` record in `ShellAdapter.exe` and `ShellAdapter.interact` (depends on: previous task) - Acceptance: `uv run pytest tests/lib/pybase/adapters/test_shell_adapter.py` passes.
- [ ] Add the two sentences to the `--debug` paragraph in `docs/source/configuration.rst` - Acceptance: `rg -n "logged once the configuration has loaded" docs/source/configuration.rst` prints one line.
- [ ] Add the CHANGELOG line under `[Unreleased]` `### Added` - Acceptance: `rg -n "names each config file that was read and its layer" CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest tests/lib/pybase/configuration/test_resolver.py tests/lib/pybase/configuration/test_click_integration.py tests/lib/pybase/adapters/test_shell_adapter.py` passes; the project's full test gate (`uv run pytest`) passes.
