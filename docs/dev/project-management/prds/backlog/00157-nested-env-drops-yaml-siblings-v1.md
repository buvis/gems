---
design: skip
default_model: opus
model_tier_rationale: A new merge rule in the shared resolver, with case-insensitive key matching against pydantic-settings output; a wrong predicate changes precedence for every tool.
---
# A nested env variable for one key drops the YAML values beside it

Source: agoge run 2026-11-23, finding 8 of 21 (MEDIUM, verified, lane heidi), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

Setting one nested key through the environment replaces the whole top-level field. The YAML values beside that key vanish without a warning. The cause is `_merge_overrides` in `src/lib/buvis/pybase/configuration/resolver.py`: it drops the YAML value of every field that `_env_set_fields` reports, and a nested variable (`<PREFIX>ADAPTERS__JIRA__SERVER`) counts for its top-level field (`adapters`).

A user who overrides one nested value per machine gets a confusing validation error in bim (`token / Field required`), or silently wrong output in fctracker (amounts shown with the wrong currency symbol). The behaviour is stable and predates the probed range.

## Solution

When the environment sets a field only through nested variables, deep-merge: the YAML value is the base, and each env-set leaf is laid over it. A variable that names the whole field still replaces the whole field.

Exact rules, all in `src/lib/buvis/pybase/configuration/resolver.py`:

1. Add `_env_nested_paths(env_prefix: str, field: str) -> list[tuple[str, ...]]`. It scans `os.environ` and compares names case-insensitively, as `_env_set_fields` does. For each variable named `<env_prefix><field>__<a>__<b>...` it returns the lowercased key path `("<a>", "<b>", ...)`, split on `__`. When a variable named exactly `<env_prefix><field>` exists, it returns `[]`: the environment owns the whole field. Paths are sorted by length, shortest first, then by name.
2. Add `_overlay_env_leaves(yaml_value: dict[str, Any], env_value: dict[str, Any], paths: list[tuple[str, ...]]) -> dict[str, Any] | None`. It deep-copies `yaml_value`. For each path it reads the leaf from `env_value` and writes it at the same path in the copy.
   - `env_value` is `base_settings.model_dump()[field]`. It holds the values as pydantic-settings parsed them, so no env string is parsed twice.
   - Keys match case-insensitively at every level, in `env_value` and in the copy. pydantic-settings lowercases nested key names when `case_sensitive=False`.
   - When a key in the copy matches a path segment ignoring case, the copy keeps its own spelling (YAML `EUR` stays `EUR`). When no key matches, the spelling from `env_value` is used.
   - When a segment on the way down holds a non-mapping in the copy, it is replaced by a new mapping.
   - When a path cannot be found in `env_value`, the function returns `None`.
3. In `_merge_overrides`, for a YAML key that is a model field and is in `env_fields`:
   - If `_env_nested_paths` is non-empty, the YAML value is a mapping, `base_settings.model_dump()[key]` is a mapping, and `_overlay_env_leaves` returns a mapping: use that mapping as the value for the key.
   - In every other case keep today's behaviour: the YAML value is dropped and the env value wins.
4. Nothing else changes. A field the environment does not set takes the YAML value. CLI overrides still win over both. `_track_sources` still reports `ConfigSource.ENV` for a field that any variable sets. A variable that names a nested mapping (`<PREFIX>ADAPTERS__JIRA='{"server": "x"}'`) replaces that mapping; YAML keys inside it are dropped, YAML keys beside it are kept.

Expected results for the evidence cases:

- YAML `adapters: {jira: {server: https://yaml.example, token: T}, other: {k: v}}` plus `<PREFIX>ADAPTERS__JIRA__SERVER=http://127.0.0.1:2` gives `adapters == {"jira": {"server": "http://127.0.0.1:2", "token": "T"}, "other": {"k": "v"}}`.
- fctracker YAML `local_currency: {code: EUR, symbol: E}` plus `BUVIS_FCTRACKER_LOCAL_CURRENCY__CODE=USD` gives `code == "USD"`, `symbol == "E"`, `precision == 2`.
- fctracker YAML `foreign_currencies: {EUR: {symbol: "€", precision: 2}}` plus `BUVIS_FCTRACKER_FOREIGN_CURRENCIES__EUR__PRECISION=0` gives exactly one key, `EUR`, with `symbol == "€"` and `precision == 0`. No second key `eur` appears.

Docs: in `docs/source/configuration.rst`, after the paragraph "For nested fields, use double underscores" and its code block, add: a nested variable overrides only the key it names; YAML keys beside it are kept; a variable that names the whole field replaces the whole field.

CHANGELOG, `[Unreleased]`, `### Fixed`: `- **config**: an environment variable for one nested key (for example `BUVIS_BIM_ADAPTERS__JIRA__SERVER`) now overrides only that key; YAML values beside it are kept. Before, the whole field was replaced, so bim lost the Jira `token` and fctracker showed the default currency symbol. A variable that sets the whole field still replaces it.`

## Requirements

### Must have
- A nested env variable for `adapters.jira.server` keeps the YAML `adapters.jira.token` and the YAML `adapters.other`.
- A nested env variable for fctracker `local_currency.code` keeps the YAML `local_currency.symbol`.
- A nested env variable for one key of one fctracker foreign currency keeps the YAML spelling of the currency code and adds no lowercase twin key.
- A variable that sets the whole field (`<PREFIX>ADAPTERS` as JSON) still replaces the YAML value of that field.
- `test_set_env_var_beats_yaml_even_at_the_default_value` and `test_yaml_still_applies_when_only_another_field_is_set_in_env` in `tests/lib/pybase/configuration/test_config_errors.py` pass without edits.
- `CHANGELOG.md` has the `### Fixed` line under `[Unreleased]`.
- `docs/source/configuration.rst` states the nested-variable rule.

### Nice to have
- None.

## Implementation

### Module: nested env overlay
- **Location**: src/lib/buvis/pybase/configuration/resolver.py, tests/lib/pybase/configuration/test_resolver.py, tests/tools/fctracker/test_settings.py, docs/source/configuration.rst, CHANGELOG.md
- **Responsibility**: Keep YAML siblings when the environment sets a field only through nested variables.
- **Exports**: none (the two new functions are module-private; `ConfigResolver.resolve` returns different values for the mixed case)
- New symbols: `_env_nested_paths`, `_overlay_env_leaves`, `test_nested_env_for_one_adapter_key_keeps_yaml_siblings`, `test_whole_field_env_still_replaces_the_yaml_value`, `test_nested_env_for_currency_code_keeps_yaml_symbol`, `test_nested_env_for_a_currency_keeps_the_yaml_key_spelling`
- **Risk**: Precedence gets one more case, after "a set variable always wins" was just simplified. A user who relied on a nested variable to blank the YAML siblings now keeps them. No existing test pins the old replace behaviour for nested variables. `tests/tools/fctracker/conftest.py` sets `BUVIS_FCTRACKER_LOCAL_CURRENCY__*` and `BUVIS_FCTRACKER_FOREIGN_CURRENCIES` for every fctracker test; the new fctracker tests must delete every `BUVIS_FCTRACKER_*` variable first. The key-lowercasing case rests on pydantic-settings lowercasing nested keys; the fail-first run of `test_nested_env_for_a_currency_keeps_the_yaml_key_spelling` confirms it.

### Dependencies
- nested env overlay: No dependencies (foundation)

## Test Strategy

Regression checks. Each test isolates `HOME`, deletes every `BUVIS_*` variable, and passes the YAML as `config_path` to `ConfigResolver().resolve(...)`.

- `test_nested_env_for_one_adapter_key_keeps_yaml_siblings` in `tests/lib/pybase/configuration/test_resolver.py`. A local settings class with `env_prefix="BUVIS_FOO_"` and `env_nested_delimiter="__"`. YAML `adapters: {jira: {server: https://yaml.example, token: T}, other: {k: v}}`. Env `BUVIS_FOO_ADAPTERS__JIRA__SERVER=http://127.0.0.1:2`. Assert the `adapters` value given in the Solution.
- `test_whole_field_env_still_replaces_the_yaml_value` in the same file. Same YAML. Env `BUVIS_FOO_ADAPTERS={"jira": {"server": "x"}}`. Assert `adapters == {"jira": {"server": "x"}}`. This test passes before and after the change; it guards the kept rule.
- `test_nested_env_for_currency_code_keeps_yaml_symbol` in the new file `tests/tools/fctracker/test_settings.py`, with `FctrackerSettings`. The `local_currency` case from the Solution.
- `test_nested_env_for_a_currency_keeps_the_yaml_key_spelling` in the same new file. The `foreign_currencies` case from the Solution. This case is not in the packet evidence below; it comes from the lane notes.

Finding evidence, verbatim (verified, same values at `669b74b6`):

```
**Evidence** (confirmed). YAML `adapters: {jira: {server, token}, other: {k: v}}` plus
`BUVIS_BIM_ADAPTERS__JIRA__SERVER=http://127.0.0.1:2` -> `adapters = {'jira': {'server': ...}}`;
at the CLI ` ✘ 1 validation error for JiraSettings / token / Field required`. fctracker: YAML
`local_currency: {code: EUR, symbol: E}` plus `..._LOCAL_CURRENCY__CODE=USD` ->
`code='USD', symbol='Kč'`, a silent wrong symbol. Same values at `669b74b6` (pre-existing).
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_nested_env_for_one_adapter_key_keeps_yaml_siblings`, `test_whole_field_env_still_replaces_the_yaml_value`, `test_nested_env_for_currency_code_keeps_yaml_symbol` and `test_nested_env_for_a_currency_keeps_the_yaml_key_spelling`; watch the three nested ones fail - Acceptance: `uv run pytest -k "nested_env_for_one_adapter_key or nested_env_for_currency_code or nested_env_for_a_currency"` fails on the unmodified code.
- [ ] Add `_env_nested_paths` and `_overlay_env_leaves` and use them in `_merge_overrides` as the Solution states (depends on: previous task) - Acceptance: `uv run pytest -k "nested_env_for or whole_field_env_still_replaces"` passes.
- [ ] Check that scalar precedence is unchanged (depends on: previous task) - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_config_errors.py tests/lib/pybase/configuration/test_resolver.py tests/lib/pybase/configuration/test_click_integration_auto_update.py` passes.
- [ ] Add the nested-variable rule to `docs/source/configuration.rst` - Acceptance: `rg -n "overrides only the key it names" docs/source/configuration.rst` prints a match.
- [ ] Add the `### Fixed` line to `CHANGELOG.md` `[Unreleased]` - Acceptance: `rg -n "one nested key" CHANGELOG.md` prints a match.

## Success Criteria

- `uv run pytest -k "nested_env_for or whole_field_env_still_replaces"` passes; the project's full test gate (`uv run pytest`) passes.
