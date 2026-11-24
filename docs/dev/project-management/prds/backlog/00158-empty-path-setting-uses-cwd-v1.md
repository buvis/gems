---
design: skip
default_model: sonnet
model_tier_rationale: One validator on five named fields with an exact message; every check is a named test that fails loudly.
---
# An empty `BUVIS_BIM_PATH_*` variable makes bim act on the working directory

Source: agoge run 2026-11-23, finding 11 of 21 (LOW, verified, lanes heidi and trudy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

An env variable that is set but empty beats the YAML value with `''`. For a bim path setting an empty value means "here": `Path("").expanduser().resolve()` is the working directory. `bim query` then lists notes from the working directory, and `bim archive` moves a note into it. The exit code is 0 and there is no warning.

A stray `export BUVIS_BIM_PATH_ARCHIVE=` in a shell profile sends reads and writes to whatever directory the user stands in. It is rare, and confusing when it happens.

## Solution

Reject an empty path setting with a config error that names the field and the variable.

Add one validator to `BimSettings` in `src/tools/bim/settings.py`:

- Name: `_reject_empty_path`. It is a `pydantic.field_validator` (default `after` mode) on `path_zettelkasten`, `path_archive`, `path_projects`, `path_daily` and `path_articles`.
- Rule: when `value.strip() == ""`, raise `ValueError` with the message `must not be empty; give a directory, or unset BUVIS_BIM_<FIELD>`, where `<FIELD>` is the field name in upper case (from the `field_name` of the validator's pydantic ValidationInfo argument). Otherwise return the value unchanged.
- The rule holds for every source: environment, YAML, and a direct `BimSettings(...)` call. Field defaults are not empty and are not validated.

Resulting behaviour, through the existing error path (`ConfigResolver.resolve` raises `ConfigurationError`, the `buvis_options` wrapper prints it with the failure marker):

- `BUVIS_BIM_PATH_ARCHIVE= bim archive <note>` prints a failure that holds the line `  path_archive: Value error, must not be empty; give a directory, or unset BUVIS_BIM_PATH_ARCHIVE` under `Configuration validation failed:`, and exits 1. No note is moved.
- A YAML file with `path_daily: ""` gives the same line with the file path after the field name, as `_format_validation_errors` already does for YAML sources, and exit 1.
- No traceback is printed.

fctracker `transactions_dir` (`src/tools/fctracker/settings.py`) is a path field but is not changed. Its default is `""`, which means "not configured"; `FCTrackerConfig.transactions_dir` in `src/tools/fctracker/adapters/config/config.py` raises `FileNotFoundError("transactions_dir not configured")` for an empty value and never builds `Path("")`. A `fctracker --config-create` template writes that empty default into the file, so a validator there would reject a freshly generated config.

Docs: in `docs/source/tools/bim.rst`, after the sentence that lists the `BUVIS_BIM_PATH_*` env vars, add: an empty value for a path setting is a configuration error; unset the variable to use the config file or the default.

CHANGELOG, `[Unreleased]`, `### Fixed`: `- **bim**: an empty path setting (`BUVIS_BIM_PATH_ZETTELKASTEN=`, or `path_archive: ""` in a config file) stops bim with a configuration error that names the setting. Before, bim silently read and wrote in the working directory.`

## Requirements

### Must have
- An empty or whitespace-only value in any of the five `BUVIS_BIM_PATH_*` variables makes `ConfigResolver().resolve(BimSettings)` raise `ConfigurationError`. The message holds the field name and the variable name.
- An empty value for a `path_*` key in YAML raises `ConfigurationError`. The message holds the field name and the file path.
- `bim archive` with `BUVIS_BIM_PATH_ARCHIVE=` exits 1, prints `path_archive` and `BUVIS_BIM_PATH_ARCHIVE`, prints no traceback, and moves no file.
- The five defaults in `tests/tools/bim/test_settings.py::TestBimDefaultVaultFolder` still hold.
- `CHANGELOG.md` has the `### Fixed` line under `[Unreleased]`.

### Nice to have
- None.

## Implementation

### Module: bim path validator
- **Location**: src/tools/bim/settings.py, tests/tools/bim/test_settings.py, docs/source/tools/bim.rst, CHANGELOG.md
- **Responsibility**: Refuse an empty bim path setting before any command runs.
- **Exports**: none (`BimSettings` gains a private validator)
- New symbols: `_reject_empty_path`, `test_rejects_an_empty_path_variable`, `test_rejects_an_empty_path_in_yaml`, `test_empty_path_variable_stops_bim_before_the_command_runs`
- **Risk**: The rule is per field; non-path fields keep the "an empty set variable wins" rule, and fctracker `transactions_dir` keeps it too. A user with an empty `BUVIS_BIM_PATH_*` export that happened to work from the right directory now gets an error and exit 1. No existing test sets an empty bim path. The passive update check resolves the same settings and swallows the configuration error by design; the command's own resolution reports it.

### Dependencies
- bim path validator: No dependencies (foundation)

## Test Strategy

Regression checks, all in `tests/tools/bim/test_settings.py`. Each test sets `HOME` to a tmp directory, deletes every `BUVIS_*` variable, and sets `BUVIS_CONFIG_DIR` to an empty tmp directory.

- `test_rejects_an_empty_path_variable`: parametrized over the five fields and the values `""` and `"  "`. Set `BUVIS_BIM_<FIELD>` to the value. Assert `ConfigResolver().resolve(BimSettings)` raises `ConfigurationError`, and the message holds the field name, `must not be empty` and `BUVIS_BIM_<FIELD>`.
- `test_rejects_an_empty_path_in_yaml`: a file with `path_daily: ""` passed as `config_path`. Assert `ConfigurationError`, and the message holds `path_daily`, the file path and `must not be empty`.
- `test_empty_path_variable_stops_bim_before_the_command_runs`: a vault note in a tmp directory, `BUVIS_BIM_PATH_ZETTELKASTEN` set to the vault, `BUVIS_BIM_PATH_ARCHIVE` set to `""`, `chdir` to a second tmp directory. Run `CliRunner().invoke(cli, ["archive", str(note)])` with `bim.cli.cli`. Assert `exit_code == 1`, the output holds `path_archive` and `BUVIS_BIM_PATH_ARCHIVE`, the output does not hold `Traceback`, the note still exists, and the second directory is still empty.

Finding evidence, verbatim (verified):

```
**Evidence** (confirmed). `BUVIS_BIM_PATH_ZETTELKASTEN= bim query ...` lists the note in the cwd,
not the vault, rc 0, no warning. `BUVIS_BIM_PATH_ARCHIVE= bim archive <vault note>` moved the note
into the cwd. For bim this predates the range; `BUVIS_FCTRACKER_TRANSACTIONS_DIR=` now also wins
with `''` (new, by the "a set variable always wins" rule).
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_rejects_an_empty_path_variable`, `test_rejects_an_empty_path_in_yaml` and `test_empty_path_variable_stops_bim_before_the_command_runs`; watch them fail - Acceptance: `uv run pytest tests/tools/bim/test_settings.py -k "empty_path"` fails on the unmodified code.
- [ ] Add `_reject_empty_path` to `BimSettings` with the exact message from the Solution (depends on: previous task) - Acceptance: `uv run pytest tests/tools/bim/test_settings.py` passes.
- [ ] Add the empty-value sentence to `docs/source/tools/bim.rst` - Acceptance: `rg -n "empty value for a path setting" docs/source/tools/bim.rst` prints a match.
- [ ] Add the `### Fixed` line to `CHANGELOG.md` `[Unreleased]` - Acceptance: `rg -n "an empty path setting" CHANGELOG.md` prints a match.

## Success Criteria

- `uv run pytest tests/tools/bim/test_settings.py -k "empty_path"` passes; the project's full test gate (`uv run pytest`) passes.
