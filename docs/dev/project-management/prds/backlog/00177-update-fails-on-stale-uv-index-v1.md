---
design: skip
default_model: sonnet
model_tier_rationale: transcription only - exact helper code, call sites and test edits given; wrong code breaks named tests
---
# The update fails right after a release because uv reads an old index

Source: release of 0.21.0 on 2026-11-25, reproduced in the session that shipped it.

## Problem

Right after a release, `bim --update` (and the silent auto-update) fails with `Because there is no version of buvis-gems[all]==0.21.0 ... your requirements are unsatisfiable`. The version check asks the installer's index (`mise latest pipx:buvis-gems`) and sees the new release. The upgrade then runs through uv, which reads its cached copy of the PyPI simple index for `buvis-gems`. That copy was fetched before the release and does not list the new version, so the install fails.

Evidence from 2026-11-25, about 70 minutes after 0.21.0 reached PyPI: the PyPI simple index listed all 21 files of 0.21.0, and `mise latest pipx:buvis-gems` printed `0.21.0`. `uv pip compile` of `buvis-gems[all]==0.21.0` failed with the same error. The same command with `--refresh-package buvis-gems` succeeded.

Impact: the manual `--update` fails, and the silent auto-update fails on every tool start (each start runs the failing installer again) until uv's cache expires. Every release can hit this.

## Solution

Before the upgrade command runs, an installer that resolves through uv first runs `uv cache clean buvis-gems`. That removes uv's cached index and wheels for `buvis-gems` only, so the following install reads the current index. The step is best effort: if `uv` is missing, times out or exits non-zero, the updater logs a warning and runs the upgrade anyway. Neither uv nor mise has an environment variable that forces an index refresh, and mise cannot pass `--refresh-package` to uv, so a separate step is the only option that covers `mise-pipx`. `UV_NO_CACHE=1` was rejected: it downloads every dependency of `buvis-gems[all]` again on each upgrade and risks the 120-second timeout.

The methods that resolve through uv are `mise-pipx` (mise installs pipx tools with uv), `uv-tool` and `uv-venv`. `pipx` and `pip-venv` use pip, which revalidates the index after 10 minutes, so they are not changed.

## Requirements

### Must have
- `run_update` and `run_update_interactive` call `_refresh_package_index(installer, state_dir)` after the `upgrade_command is None` check and before the upgrade `subprocess.run`.
- For `installer.method` in `mise-pipx`, `uv-tool`, `uv-venv`, the helper runs `("uv", "cache", "clean", "buvis-gems")` with `capture_output=True`, `timeout=30` and `cwd=state_dir`. For every other method it runs nothing.
- A missing `uv` (`FileNotFoundError`), a timeout, any other `OSError` or a non-zero exit logs one `warning` entry starting `Could not refresh uv cache for buvis-gems:` and never raises. The upgrade then runs as before.
- The helper prints nothing to stdout or stderr.
- A `Fixed` entry in `CHANGELOG.md` under `[Unreleased]`.

### Nice to have
- None.

## Implementation

### Module: updater executor
- **Location**: `src/lib/buvis/pybase/updater/executor.py`
- **Responsibility**: refresh uv's cache for buvis-gems before an upgrade through a uv-backed installer.
- **Exports**: none (the helper is private; `__all__` does not change)
- New symbols: `_refresh_package_index`, `_UV_BACKED_METHODS`, `_CACHE_CLEAN_TIMEOUT`

Exact code. Add beside the other timeouts:

```python
_CACHE_CLEAN_TIMEOUT = 30
# Installers that resolve through uv. uv caches the PyPI index, so right after a release
# its copy can lack the version the installer's index already offers.
_UV_BACKED_METHODS = frozenset({"mise-pipx", "uv-tool", "uv-venv"})
```

Add before `run_update`:

```python
def _refresh_package_index(installer: InstallerInfo, state_dir: Path) -> None:
    """Drop uv's cached index and wheels for buvis-gems so the upgrade sees a fresh release.

    Best effort: a missing uv, a timeout or a failed clean is logged and the upgrade runs anyway.
    """
    if installer.method not in _UV_BACKED_METHODS:
        return
    try:
        result = subprocess.run(
            ("uv", "cache", "clean", "buvis-gems"),
            capture_output=True,
            timeout=_CACHE_CLEAN_TIMEOUT,
            cwd=state_dir,
        )
    except (TimeoutExpired, OSError) as exc:
        append_log(state_dir, "warning", f"Could not refresh uv cache for buvis-gems: {exc}")
        return
    if result.returncode != 0:
        stderr_snippet = result.stderr.decode(errors="replace").strip()[:200]
        append_log(state_dir, "warning", f"Could not refresh uv cache for buvis-gems: {stderr_snippet}")
```

In `run_update`, insert `_refresh_package_index(installer, state_dir)` directly after the `append_log(state_dir, "info", f"Updating buvis-gems {current} -> {latest} via {installer.method}")` line. In `run_update_interactive`, insert the same call directly after its `Updating buvis-gems {current} → {latest}` `append_log` call.

### Module: updater tests
- **Location**: `tests/lib/pybase/updater/test_refresh_index.py` (new), `tests/lib/pybase/updater/test_executor.py`, `tests/lib/pybase/updater/test_init.py`
- **Responsibility**: pin the refresh behavior; keep the existing tests on the upgrade call alone.
- **Exports**: none
- New symbols: `TestRefreshPackageIndex`, `TestUpgradeRunsAfterRefresh`, `_no_cache_refresh`, `buvis.pybase.updater.executor._refresh_package_index`, `test_cleans_uv_cache_for_uv_backed_installers`, `test_skips_installers_that_do_not_use_uv`, `test_missing_uv_logs_warning_and_returns`, `test_timeout_logs_warning_and_returns`, `test_failed_clean_logs_warning_with_stderr`, `test_auto_update_cleans_cache_before_upgrade`, `test_interactive_update_cleans_cache_before_upgrade`, `test_upgrade_still_runs_when_clean_fails`

### Module: changelog
- **Location**: `CHANGELOG.md`
- **Responsibility**: record the user-visible fix.
- **Exports**: none

### Dependencies
- updater executor: No dependencies (foundation)
- updater tests: Depends on [updater executor]
- changelog: Depends on [updater executor]

## Tasks

### Phase 0: Fix
- [ ] Add `_CACHE_CLEAN_TIMEOUT`, `_UV_BACKED_METHODS` and `_refresh_package_index` to `src/lib/buvis/pybase/updater/executor.py` and call it from `run_update` and `run_update_interactive`, exactly as in the Implementation section - Acceptance: `rg -c "_refresh_package_index\(installer, state_dir\)" src/lib/buvis/pybase/updater/executor.py` prints `2`.
- [ ] Keep the existing tests on the upgrade call (depends on: previous task). Premise: `rg -c "call_args_list\[0\]" tests/lib/pybase/updater/test_executor.py` prints `3` and `rg -c "mock_run.assert_called_once\(\)" tests/lib/pybase/updater/test_init.py` prints `1`; if either count differs, stop and report instead of editing. In `tests/lib/pybase/updater/test_executor.py` add a module-level autouse fixture `_no_cache_refresh` that patches `buvis.pybase.updater.executor._refresh_package_index`. In `tests/lib/pybase/updater/test_init.py`, test `test_restarted_process_does_not_update_again`, add `patch("buvis.pybase.updater.executor._refresh_package_index")` to its `with` block - Acceptance: `uv run pytest tests/lib/pybase/updater/test_executor.py tests/lib/pybase/updater/test_init.py -q` passes with no test removed.
- [ ] Create `tests/lib/pybase/updater/test_refresh_index.py` (depends on: first task). Class `TestRefreshPackageIndex`, each test patching `buvis.pybase.updater.executor.subprocess.run` and `buvis.pybase.updater.executor.append_log`: `test_cleans_uv_cache_for_uv_backed_installers` (parametrized over `mise-pipx`, `uv-tool`, `uv-venv`; asserts one call with args `("uv", "cache", "clean", "buvis-gems")` and kwargs `capture_output=True, timeout=30, cwd=state_dir`); `test_skips_installers_that_do_not_use_uv` (parametrized over `pipx`, `pip-venv`, `unknown`; asserts `subprocess.run` not called); `test_missing_uv_logs_warning_and_returns` (side effect `FileNotFoundError`); `test_timeout_logs_warning_and_returns` (side effect `subprocess.TimeoutExpired`); `test_failed_clean_logs_warning_with_stderr` (return code 2, stderr `b"lock busy"`; the warning message contains `lock busy`); each failure test asserts exactly one `warning` log whose message starts with `Could not refresh uv cache for buvis-gems:` and that nothing reached `capsys`. Class `TestUpgradeRunsAfterRefresh`: `test_auto_update_cleans_cache_before_upgrade` and `test_interactive_update_cleans_cache_before_upgrade` drive `run_update` / `run_update_interactive` with the `mise-pipx` installer `InstallerInfo(method="mise-pipx", upgrade_command=("mise", "upgrade", "pipx:buvis-gems"))`, patch `executor.subprocess` (return code 0), `executor.os`, `executor.sys` and `executor.read_installed_version` (returns `"0.8.0"`), and assert `mock_sub.run.call_args_list[0].args[0] == ("uv", "cache", "clean", "buvis-gems")` and `mock_sub.run.call_args_list[1].args[0] == ("mise", "upgrade", "pipx:buvis-gems")`; `test_upgrade_still_runs_when_clean_fails` makes the first `subprocess.run` call raise `FileNotFoundError` and asserts the upgrade command still ran - Acceptance: `uv run pytest tests/lib/pybase/updater/test_refresh_index.py -q` passes; with the two `_refresh_package_index(installer, state_dir)` calls removed from `executor.py`, the `TestUpgradeRunsAfterRefresh` tests fail.

### Phase 1: Record
- [ ] Add under `### Fixed` in `[Unreleased]` of `CHANGELOG.md` (depends on: Phase 0): `- **updater**: right after a release, \`--update\` and the automatic update no longer fail with "no version of buvis-gems[all]==X" when installed with mise, \`uv tool\` or \`uv pip\`; the updater clears uv's cached index for buvis-gems before it upgrades.` - Acceptance: `rg -c "clears uv's cached index for buvis-gems" CHANGELOG.md` prints `1`.

## Success Criteria

- `uv run pytest tests/lib/pybase/updater -q` passes, including `TestRefreshPackageIndex` and `TestUpgradeRunsAfterRefresh`.
- `uv run mypy src/lib/` reports no new error in `src/lib/buvis/pybase/updater/executor.py`.
- The project's full test gate passes.
