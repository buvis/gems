---
design: skip
model_tier_rationale: One condition in one function changes to an existing helper; one new test.
---
# Lowercase `buvis_auto_update=false` does not stop the update check

Source: agoge run 2026-11-23, finding 12 of 21 (LOW, mocked, lane heidi), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

The global update switch is looked up case-sensitively. `_update_enabled` in `src/lib/buvis/pybase/configuration/click_integration.py` tests `_GLOBAL_AUTO_UPDATE_ENV in os.environ`, so only the exact name `BUVIS_AUTO_UPDATE` counts. Every other setting reads env names in any case, and the per-tool switch in the same function does too, through `_env_set_fields(env_prefix)`.

A user who writes the variable in lowercase still gets update checks from every tool that has its own env prefix. It is rare and nobody is harmed. The two halves of one function disagree.

## Solution

Use the same helper for the global test as for the tool test.

In `_update_enabled`, replace the condition `_GLOBAL_AUTO_UPDATE_ENV in os.environ` with `"auto_update" in _env_set_fields("BUVIS_")`. The branch body stays: `return GlobalSettings().auto_update`. `GlobalSettings` already reads the variable case-insensitively (`case_sensitive=False`), so the value follows the name.

Remove the constant `_GLOBAL_AUTO_UPDATE_ENV`; nothing else uses it. Keep `import os`; `_create_buvis_options` still uses `os.path.isdir`.

Resulting behaviour for a tool settings class with its own prefix (`BUVIS_FOO_`), with no `BUVIS_FOO_AUTO_UPDATE` set:

- `buvis_auto_update=false` gives `_update_enabled(FooSettings, FooSettings()) is False`.
- `Buvis_Auto_Update=false` gives the same.
- `BUVIS_AUTO_UPDATE=false` still gives `False`, and `BUVIS_AUTO_UPDATE=true` still gives `True` over a YAML `auto_update: false`.
- The tool variable still wins in any case: `buvis_foo_auto_update=false` with `BUVIS_AUTO_UPDATE=true` gives `False`. `_env_set_fields("BUVIS_")` maps that tool variable to the field `foo_auto_update`, not `auto_update`, so it does not trigger the global branch.

No docs change: `docs/source/configuration.rst` already states the rule without a case restriction.

CHANGELOG, `[Unreleased]`, `### Fixed`: `- **config**: the global `BUVIS_AUTO_UPDATE` is read in any letter case, like every other setting; `buvis_auto_update=false` used to be ignored by tools with their own env prefix.`

## Requirements

### Must have
- With `buvis_auto_update=false` or `Buvis_Auto_Update=false` in the environment and no tool variable, `_update_enabled` returns `False` for a settings class with its own env prefix.
- Every existing test in `tests/lib/pybase/configuration/test_click_integration_auto_update.py` passes without edits.
- `_GLOBAL_AUTO_UPDATE_ENV` no longer exists in `src/lib/buvis/pybase/configuration/click_integration.py`.
- `CHANGELOG.md` has the `### Fixed` line under `[Unreleased]`.

### Nice to have
- None.

## Implementation

### Module: global update switch lookup
- **Location**: src/lib/buvis/pybase/configuration/click_integration.py, tests/lib/pybase/configuration/test_click_integration_auto_update.py, CHANGELOG.md
- **Responsibility**: Read the global update switch in any letter case.
- **Exports**: none
- New symbols: `test_global_auto_update_variable_is_read_in_any_letter_case`
- **Risk**: None found for the chosen option. No existing test pins the case-sensitive lookup; `test_lowercase_tool_env_false_still_beats_global_env_true` covers the tool half and must keep passing. On Windows, env names are already upper-cased by the OS, so the new test passes there before the change too.

### Dependencies
- global update switch lookup: No dependencies (foundation)

## Test Strategy

Regression check: `test_global_auto_update_variable_is_read_in_any_letter_case` in `tests/lib/pybase/configuration/test_click_integration_auto_update.py`, class `TestEnvPrecedence`. Parametrize the variable name over `buvis_auto_update` and `Buvis_Auto_Update`. Set it to `false` with `monkeypatch.setenv`. Import `_update_enabled` from `buvis.pybase.configuration.click_integration`. Assert `_update_enabled(FooSettings, FooSettings()) is False`. The file's `isolated_env` fixture already deletes every upper-case `BUVIS_*` variable.

The evidence below is `mocked`: the lane replaced `check_and_update` with a recorder, so no real update check ran. The real check can run on a machine with an installed `buvis-gems`, by running a prefixed tool (for example `zseq --help`) with `buvis_auto_update=false` and watching whether `updater.json` in the config directory changes.

Finding evidence, verbatim:

```
**Evidence** (mocked: `check_and_update` replaced by a recorder). `buvis_auto_update=false` ->
`calls=[True]`; `Buvis_Auto_Update=false` -> `calls=[True]`; while
`buvis_zseq_auto_update=false BUVIS_AUTO_UPDATE=true` -> `calls=[]`. Same at `669b74b6`.
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_global_auto_update_variable_is_read_in_any_letter_case`; watch it fail - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_click_integration_auto_update.py -k "global_auto_update_variable_is_read_in_any_letter_case"` fails on the unmodified code.
- [ ] Change the global condition in `_update_enabled` to `"auto_update" in _env_set_fields("BUVIS_")` and remove `_GLOBAL_AUTO_UPDATE_ENV` (depends on: previous task) - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_click_integration_auto_update.py` passes and `rg -n "_GLOBAL_AUTO_UPDATE_ENV" src/lib/buvis/pybase/configuration/click_integration.py` prints nothing.
- [ ] Add the `### Fixed` line to `CHANGELOG.md` `[Unreleased]` - Acceptance: `rg -n "read in any letter case" CHANGELOG.md` prints a match.

## Success Criteria

- `uv run pytest tests/lib/pybase/configuration/test_click_integration_auto_update.py tests/lib/pybase/configuration/test_click_integration.py` passes; the project's full test gate (`uv run pytest`) passes.
