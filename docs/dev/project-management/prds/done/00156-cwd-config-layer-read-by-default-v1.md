---
design: skip
default_model: sonnet
model_tier_rationale: A default flips from True to False in three named signatures; every task carries exact names and every check is a named test or an rg on a named file.
---
# Every tool reads config files from the working directory

Source: agoge run 2026-11-23, finding 2 of 21 (HIGH, verified for the plan, execution not run, lane trudy) and finding 3 of 21 (MEDIUM, mocked, lane trudy), one PRD by operator-approved cluster, `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

Every tool except `braid` reads the working directory as its lowest config layer. A `config.yaml`, `buvis.yaml` or `buvis-<tool>.yaml` in the directory you stand in is deep-merged into the settings and gets `${VAR}` expansion.

Finding 2: a `buvis-sysup.yaml` in the working directory adds steps to the `sysup` update plan. Running `sysup` inside a cloned repository runs what that repository's file says, with the user's rights.

Finding 3: a `buvis-bim.yaml` in the working directory can set a URL that carries an env value, add a Jira proxy, or turn debug logging on. Running `bim` inside a hostile clone can leak one named env variable and note bodies.

Both need a staged directory. Both are cheap for an attacker to stage. Only `braid` opts out today (`config_include_cwd = False` in `src/tools/braid/settings.py`).

## Solution

Drop the working-directory config layer for every tool by default. A tool reads it only when its settings class opts in. No tool opts in. This is a BREAKING change.

How the flag flows today:

- `ConfigResolver.resolve` reads `getattr(settings_class, "config_include_cwd", True)` and passes it as `include_cwd` to `ConfigResolver._load_yaml`.
- `_load_yaml` passes it to `ConfigurationLoader.find_config_files_ranked`.
- `find_config_files_ranked` passes it to `ConfigurationLoader._get_search_paths`, which appends `Path.cwd()` when it is true.
- `ConfigurationLoader.find_config_files` calls `_get_search_paths(config_dir)` and takes the default.
- `load_config` in `src/tools/sysup/config.py` and in `src/tools/backup/config.py` call `find_config_files_ranked` without `include_cwd` and take the default. This is the path finding 2 used.

Exact change in `src/lib/buvis/pybase/configuration/loader.py`:

- `_get_search_paths(config_dir=None, *, include_cwd: bool = False)`.
- `find_config_files_ranked(..., include_cwd: bool = False)`.
- `find_config_files` is not edited. It follows the new default of `_get_search_paths`.
- Update the docstrings of `_get_search_paths`, `find_config_files` and `find_config_files_ranked`. They list the working directory as a default search path. They must say it is searched only with `include_cwd=True`.

Exact change in `src/lib/buvis/pybase/configuration/resolver.py`:

- `_load_yaml(..., include_cwd: bool = False, ...)`.
- `resolve` reads `getattr(settings_class, "config_include_cwd", False)`.

Opt-in contract: a settings class sets `config_include_cwd: ClassVar[bool] = True`. Then the resolver searches the working directory as the lowest layer, as before. A tool that also loads a plan itself (as sysup and backup do) must pass `include_cwd=True` to `find_config_files_ranked` in its own loader.

No tool opts in. The code and tests show no tool that needs a per-directory config:

- `src/tools/sysup/config.py` and `src/tools/backup/config.py` are not edited. They follow the new default.
- `src/tools/braid/settings.py` is not edited. Its explicit `config_include_cwd = False` stays as a pin.

An explicit `--config FILE` and an explicit `--config-dir DIR` are not changed. A user who wants a per-directory file passes `--config ./buvis-<tool>.yaml` or `--config-dir .`.

Docs:

- `docs/source/configuration.rst`, section "File Locations": remove the item `Current directory (except braid, which excludes it)`. The list has three items: `~/.config/buvis/`, `~/.local/.config/buvis/`, `$BUVIS_CONFIG_DIR/`. Add one paragraph after the list: the working directory is not searched; a settings class opts in with `config_include_cwd: ClassVar[bool] = True`; no bundled tool does; use `--config FILE` or `--config-dir DIR` for a per-directory file.
- `docs/source/tools/sysup.rst` and `docs/source/tools/backup.rst`: the config stack line ends with `→ cwd`. Remove that last element.

CHANGELOG, `[Unreleased]`:

- Add under `### Changed`, with the same BREAKING prefix and `config` scope as the other breaking config entries there: tools no longer read `config.yaml`, `buvis.yaml` or `buvis-<tool>.yaml` from the working directory. A file there could add `sysup` commands or point a tool at another host. Move a per-directory file to `~/.config/buvis/` or `~/.local/.config/buvis/`, or pass `--config FILE` or `--config-dir DIR`. A config file linked to a target under the working directory, outside the config directories, is now skipped with the unsafe-path warning.
- The existing `### Fixed` braid entry ends with `; other tools retain their cwd layer.` Remove that clause. It is false after this change.

## Requirements

### Must have
- `sysup` does not put a command from a `buvis-sysup.yaml` in the working directory into its plan.
- `backup` does not put an instance from a `buvis-backup.yaml` in the working directory into its plan.
- `ConfigResolver().resolve(BimSettings)` ignores a `buvis-bim.yaml` in the working directory: `ollama_url` and `debug` keep their defaults.
- `ConfigurationLoader._get_search_paths()` does not hold `Path.cwd()`. With `include_cwd=True` it holds it as the last entry.
- A settings class with `config_include_cwd: ClassVar[bool] = True` still reads a config file from the working directory.
- `braid` behaviour is unchanged: `test_cwd_config_cannot_inject_sources_or_redirect_claude` passes without edits.
- `CHANGELOG.md` has a `### Changed` BREAKING line under `[Unreleased]` for this change.
- `docs/source/configuration.rst` describes three discovered layers and the opt-in.
- `docs/source/tools/sysup.rst` and `docs/source/tools/backup.rst` no longer list `cwd` in the config stack.

### Nice to have
- None.

## Implementation

### Module: cwd layer default
- **Location**: src/lib/buvis/pybase/configuration/loader.py, src/lib/buvis/pybase/configuration/resolver.py, tests/lib/pybase/configuration/test_loader.py, tests/lib/pybase/configuration/test_resolver.py, tests/tools/sysup/test_config.py, tests/tools/backup/test_config.py, tests/tools/bim/test_settings.py, docs/source/configuration.rst, docs/source/tools/sysup.rst, docs/source/tools/backup.rst, CHANGELOG.md
- **Responsibility**: Search the working directory for config only when a caller or a settings class asks for it.
- **Exports**: `ConfigurationLoader.find_config_files_ranked` and `ConfigurationLoader.find_config_files` change behaviour (no working directory by default); the settings-class attribute `config_include_cwd` now defaults to `False`.
- New symbols: `test_ignores_a_plan_file_in_the_working_directory`, `test_ignores_an_instance_file_in_the_working_directory`, `test_ignores_a_config_file_in_the_working_directory`, `test_working_directory_is_not_a_search_path_by_default`, `test_working_directory_is_last_when_a_caller_opts_in`, `test_resolver_ignores_a_config_file_in_the_working_directory`, `test_settings_class_opts_in_to_the_working_directory_layer`
- **Risk**: BREAKING for anyone who keeps a per-directory config file; it stops loading without a message. Existing tests pin the old behaviour and must change: in `tests/lib/pybase/configuration/test_loader.py`, class `TestGetSearchPaths`, the tests `test_with_buvis_config_dir`, `test_without_buvis_config_dir`, `test_cwd_always_last` and `test_explicit_config_dir_argument` assert that `Path.cwd()` is a default search path; in the same file `TestFindConfigFiles::test_retired_twin_warns_once_without_loading` has a `"cwd"` value in its `layer` parameter, which expects a file in the working directory to be found. Side effect: `_is_safe_path` allows a link target only under a search path, so a config file in `~/.config/buvis` linked to a target under the working directory, outside the config directories, is now skipped with `Skipping unsafe config path`. `tests/tools/sysup/test_config.py::TestLoadConfigPriorityOrdering::test_ranked_order_last_wins` names a `cwd_file` but mocks discovery; it still passes and is not edited.

### Dependencies
- cwd layer default: No dependencies (foundation)

## Test Strategy

Regression checks:

- `test_ignores_a_plan_file_in_the_working_directory` in `tests/tools/sysup/test_config.py`. Set `HOME` to an empty tmp directory. Delete `BUVIS_CONFIG_DIR`. `chdir` to a tmp directory that holds `buvis-sysup.yaml` with `commands: {aaa-trudy: {order: 1, steps: [[touch, pwned_sysup]]}}`. Call the real `load_config()`, with no mock on `find_config_files_ranked`. Assert `"aaa-trudy" not in cfg.commands`.
- `test_ignores_an_instance_file_in_the_working_directory` in `tests/tools/backup/test_config.py`. Same isolation. The working directory holds `buvis-backup.yaml` with one `tar-archive` instance named `cwd-leak`. Call the real `load_config()`. Assert `"cwd-leak" not in cfg.instances`.
- `test_ignores_a_config_file_in_the_working_directory` in `tests/tools/bim/test_settings.py`. Same isolation, and delete every `BUVIS_*` variable. The working directory holds `buvis-bim.yaml` with `ollama_url: http://127.0.0.1:9/${HOME}` and `debug: true`. Assert `ConfigResolver().resolve(BimSettings)` has `ollama_url == "http://localhost:11434"` and `debug is False`.
- `test_working_directory_is_not_a_search_path_by_default` and `test_working_directory_is_last_when_a_caller_opts_in` in `tests/lib/pybase/configuration/test_loader.py`, class `TestGetSearchPaths`. They replace `test_cwd_always_last`.
- `test_resolver_ignores_a_config_file_in_the_working_directory` and `test_settings_class_opts_in_to_the_working_directory_layer` in `tests/lib/pybase/configuration/test_resolver.py`. The working directory holds `config.yaml` with `debug: true`. `GlobalSettings` resolves `debug is False`. A subclass with `config_include_cwd: ClassVar[bool] = True` resolves `debug is True`.

Finding 2 evidence, verbatim. The plan was confirmed. The step was not executed, because the lane profile allows `--list` only.

```
**Evidence** (confirmed for the plan; execution not run). In a scratch directory holding
`commands: {aaa-trudy: {order: 1, steps: ["touch <S>/pwned_sysup"]}}`, `sysup --list` shows
`1  aaa-trudy  [run]` first in the plan; from another directory the line is absent. The step was
not executed (the profile allows `--list` only), so "the command runs" is suspected, not seen.
```

Finding 3 evidence, verbatim. This evidence is `mocked`: the listeners were the lane's own, on 127.0.0.1. No real Ollama or Jira host was used. The real check can run on a machine with a reachable Ollama server and a Jira instance, with `bim import` started from a directory that holds the staged `buvis-bim.yaml`.

```
**Evidence** (mocked: the listeners were trudy's own, on 127.0.0.1). cwd `buvis-bim.yaml` with
`ollama_url: http://127.0.0.1:18972/${TRUDY_ENV_SECRET}`; `bim import` from that directory ->
listener log `POST /TRUDYMARK_ENVSUB/api/generate bodybytes=271`. cwd `adapters.jira.proxy` ->
listener saw `CONNECT 127.0.0.1:18973` four times (the token did not reach it). cwd `debug: true`
-> urllib3 debug lines. Held: a cwd file cannot replace the user's `adapters.jira.server`.
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_ignores_a_plan_file_in_the_working_directory`, `test_ignores_an_instance_file_in_the_working_directory`, `test_ignores_a_config_file_in_the_working_directory`, `test_working_directory_is_not_a_search_path_by_default`, `test_working_directory_is_last_when_a_caller_opts_in`, `test_resolver_ignores_a_config_file_in_the_working_directory` and `test_settings_class_opts_in_to_the_working_directory_layer`; watch the default-off ones fail - Acceptance: `uv run pytest -k "ignores_a_plan_file_in_the_working_directory or ignores_an_instance_file_in_the_working_directory or ignores_a_config_file_in_the_working_directory or working_directory_is_not_a_search_path_by_default or resolver_ignores_a_config_file_in_the_working_directory"` fails on the unmodified code.
- [ ] Flip the `include_cwd` default to `False` in `_get_search_paths`, `find_config_files_ranked` and `_load_yaml`, flip the `getattr` default in `resolve`, and update the three loader docstrings (depends on: previous task) - Acceptance: `uv run pytest -k "working_directory"` passes.
- [ ] Change the tests that pin the old default: rewrite `test_with_buvis_config_dir`, `test_without_buvis_config_dir` and `test_explicit_config_dir_argument` to expect no working directory, remove `test_cwd_always_last`, and remove the `"cwd"` value from the `layer` parameter of `test_retired_twin_warns_once_without_loading` (depends on: previous task) - Acceptance: `uv run pytest tests/lib/pybase/configuration/test_loader.py` passes.
- [ ] Check that braid is unchanged (depends on: previous task) - Acceptance: `uv run pytest -k "cwd_config_cannot_inject_sources_or_redirect_claude"` passes.
- [ ] Update `docs/source/configuration.rst`: remove the working-directory item and add the opt-in paragraph - Acceptance: `rg -n "config_include_cwd" docs/source/configuration.rst` prints a match and `rg -n "Current directory \(except braid" docs/source/configuration.rst` prints nothing.
- [ ] Remove `→ cwd` from the config stack line in `docs/source/tools/sysup.rst` and `docs/source/tools/backup.rst` - Acceptance: `rg -n "cwd\)" docs/source/tools/sysup.rst docs/source/tools/backup.rst` prints nothing.
- [ ] Add the BREAKING line under `### Changed` in `CHANGELOG.md` `[Unreleased]` and remove the clause `; other tools retain their cwd layer` from the braid entry - Acceptance: `rg -n "BREAKING.*config.*working directory" CHANGELOG.md` prints a match and `rg -n "other tools retain their cwd layer" CHANGELOG.md` prints nothing.

## Success Criteria

- `uv run pytest -k "working_directory or cwd_config_cannot_inject"` passes; the project's full test gate (`uv run pytest`) passes.
