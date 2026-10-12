---
design: skip
default_model: sonnet
model_tier_rationale: no escalator row holds; regexes, commands and the back-off predicate are given verbatim; the --version recursion trap is named in the task text
---

# Updater checks the installer's index

## Overview

### Problem Statement

The auto-updater decides "a newer version exists" from PyPI alone: `src/lib/buvis/pybase/updater/checker.py:18` (`_PYPI_URL`) and `src/lib/buvis/pybase/updater/checker.py:22-31` (`_query_pypi`) hardcode `https://pypi.org/pypi/buvis-gems/json`. The installer that then runs (`mise upgrade pipx:buvis-gems`, `uv tool upgrade`, `pipx upgrade`, `pip install --upgrade`) resolves through its own configured index. That index can lag or filter: an Artifactory mirror with a metadata cache or a curation policy, or mise's own `minimum_release_age` (24h default).

When the two disagree, `src/lib/buvis/pybase/updater/executor.py:30-83` (`run_update`) sees the installer exit 0, logs "Updated", and restarts the process. The restart sees PyPI's newer version again. On 2026-10-12 this looped forever and hung every `dot` call on two machines (0.13.0 installed, 0.14.0 and 0.14.1 on PyPI, neither visible to mise). Release 0.14.1 (commit 38ba0212) stops the endless loop with `REEXEC_ENV`, but every command still pays one wasted installer run plus a restart, and the log keeps claiming success.

### Target Users

Anyone running a buvis-gems CLI (`dot`, `bim`, `sysup`, ...) through an installer that sits behind a mirror or a release-age gate. The author runs it behind Artifactory on one machine and mise's 24h gate on the other.

### Success Metrics

- With an installer index that lags PyPI, a CLI run starts no installer subprocess and no restart: `test_mirror_lagging_pypi_does_not_attempt_upgrade` passes.
- An installer that exits 0 without changing the installed version is attempted at most once per target version per 24h: `test_noop_installer_second_invocation_skips_upgrade` passes.
- `--update` never reports success when the installed version did not change: `test_interactive_noop_upgrade_returns_one` passes.
- The regression test from 0.14.1 keeps passing: `test_restarted_process_does_not_update_again`.

## Functional Decomposition

### Capability: Installer-aware version lookup

Ask the installer's own index which version it would install, instead of asking PyPI.

#### Feature: Installable version lookup

- **Description**: Return the newest buvis-gems version the detected installer can actually install.
- **Inputs**: `InstallerInfo` (from `detect_installer`), state dir.
- **Outputs**: version string, or `None` when both the installer query and the PyPI fallback fail.
- **Behavior**: Run one subprocess per installer method, timeout 10s, cwd = state dir (so uv does not pick up a project-level config from the caller's cwd):
  - `mise-pipx`: `mise latest pipx:buvis-gems`; stdout stripped is the version.
  - `pip-venv`: `pip index versions buvis-gems`; version = group 1 of `re.search(r"^buvis-gems \(([^)]+)\)", stdout, re.M)`.
  - `uv-tool`, `uv-venv`: `uv pip compile --no-deps --no-header --quiet -` with `buvis-gems` on stdin; version = group 1 of `re.search(r"^buvis-gems==(\S+)$", stdout, re.M)`.
  - `pipx`, `unknown`: no installer-side query exists; return the PyPI value from `_query_pypi`.
  - Any non-zero exit, timeout, `OSError`, parse miss, or a string that `packaging.version.Version` rejects: fall back to `_query_pypi`. Never raise.

#### Feature: Checker uses the lookup

- **Description**: `check_for_update` takes the version source as a parameter so the cache holds the installable version.
- **Inputs**: a zero-argument `fetch` callable, default `_query_pypi`.
- **Outputs**: unchanged contract (newer version or `None`).
- **Behavior**: `src/lib/buvis/pybase/updater/checker.py:42-78` (`check_for_update`) calls `fetch()` where it calls `_query_pypi()` today. `fetch_latest_version` (`src/lib/buvis/pybase/updater/checker.py:81-101`) stays PyPI-only and stays the source for the `--update` message about PyPI.

### Capability: Verified upgrade and back-off

Never claim an upgrade that did not happen; never retry one that just failed.

#### Feature: Post-upgrade verification

- **Description**: After the installer exits 0, confirm the installed version moved.
- **Inputs**: `InstallerInfo`, the version before the upgrade.
- **Outputs**: installed version string, or `None` when it cannot be read.
- **Behavior**: Run `[argv0, "--version"]` where `argv0` is `_resolve_reexec_argv(installer)[0]`, timeout 10s, with `os.environ` copied and `REEXEC_ENV=1` set in the child. The child guard is required: `--version` runs the update check in `parse_args` before the version option fires, so an unguarded child would start its own upgrade. Parse stdout with `re.search(r"version (\S+)", stdout)`; the shipped format is `buvis-gems, version 0.14.1`. Verified iff `Version(installed) > Version(current)`.

#### Feature: Back-off record

- **Description**: Remember a target version whose upgrade was a no-op so it is not retried for 24h.
- **Inputs**: target version, timestamp.
- **Outputs**: `upgrade_failed` key in `updater.json`: `{"version": "<target>", "ts": "<iso utc>"}`.
- **Behavior**: `run_update` on a verified upgrade clears the key, logs info, then restarts as today. On an installer exit 0 whose verification fails, it writes the key, logs `error` ("Upgrade to X was a no-op: installer index may not offer it yet. Continuing with Y."), prints nothing, does not restart, and returns. When verification cannot run (`None`), it behaves as before: restart once under the `REEXEC_ENV` guard. `check_and_update` skips the upgrade when `failed.version == latest and (now - failed.ts) < timedelta(hours=24)`. A different (newer) `latest`, or an expired `ts`, retries.

#### Feature: Honest `--update`

- **Description**: The user-initiated path reports installer lag instead of success.
- **Inputs**: output of the lookup and of `fetch_latest_version`.
- **Outputs**: exit code and console message.
- **Behavior**: `force_update` (`src/lib/buvis/pybase/updater/__init__.py:64-107`) compares `current` to the installable version. If the installable version is not newer but PyPI's is, print `console.success("buvis-gems {current} is the newest your installer offers (PyPI has {pypi}).")` and return 0. After `run_update_interactive` returns 0, verify as above; if unchanged, `console.failure("Installer reported success but buvis-gems is still {current}; its index may not offer {latest} yet.")`, log `error`, return 1. No back-off is written on this path.

## Structural Decomposition

### Repository Structure

```
src/lib/buvis/pybase/updater/
├── index.py        # Maps to: Installable version lookup
├── state.py        # Maps to: Back-off record
├── checker.py      # Maps to: Checker uses the lookup
├── executor.py     # Maps to: Post-upgrade verification
└── __init__.py     # Maps to: Back-off record, Honest --update
tests/lib/pybase/updater/
├── test_index.py   # new
├── test_state.py
├── test_executor.py
├── test_init.py
└── test_force_update.py
```

### Module: index

- **Maps to capability**: Installer-aware version lookup
- **Responsibility**: One function that asks the installer's index for the newest installable version.
- **Exports**:
  - `fetch_installable_version(installer, state_dir)` - version string or `None`, never raises
- New symbols: `fetch_installable_version`

### Module: state

- **Maps to capability**: Verified upgrade and back-off
- **Responsibility**: Persist and read the `upgrade_failed` key without disturbing `last_check`, `latest_version`, `log`.
- **Exports**:
  - `read_upgrade_failure(state_dir)` - `(version, ts)` or `None`
  - `write_upgrade_failure(state_dir, version)` - sets the key
  - `clear_upgrade_failure(state_dir)` - removes the key
  - `UPGRADE_BACKOFF` - `timedelta(hours=24)`
- New symbols: `read_upgrade_failure`, `write_upgrade_failure`, `clear_upgrade_failure`, `UPGRADE_BACKOFF`, `upgrade_failed`

### Module: executor

- **Maps to capability**: Verified upgrade and back-off
- **Responsibility**: Verify after the installer exits 0, record the no-op, skip the restart.
- **Exports**:
  - `read_installed_version(installer)` - installed version via the child `--version`, or `None`
  - `run_update`, `run_update_interactive` - now verify
- New symbols: `read_installed_version`

### Module: checker and init

- **Maps to capability**: Installer-aware version lookup, Verified upgrade and back-off
- **Responsibility**: Wire the lookup and the back-off into `check_and_update` and `force_update`.
- **Exports**:
  - `check_for_update(state_dir, interval_hours, fetch)` - new `fetch` parameter
  - `check_and_update(settings)` - detects the installer before the check, honors the back-off

### Module: tests

- **Maps to capability**: Installer-aware version lookup, Verified upgrade and back-off
- **Responsibility**: One named regression test per behavior above.
- **Exports**:
  - the tests named in the phase Acceptance lines below
- New symbols: `test_mirror_lagging_pypi_does_not_attempt_upgrade`, `test_noop_installer_second_invocation_skips_upgrade`, `test_interactive_noop_upgrade_returns_one`, `test_upgrade_failure_roundtrip_preserves_cache_and_log`, `test_clear_upgrade_failure_removes_key`, `test_mise_pipx_uses_mise_latest`, `test_pip_venv_parses_pip_index_versions`, `test_uv_uses_pip_compile_no_deps`, `test_pipx_and_unknown_fall_back_to_pypi`, `test_query_failure_falls_back_to_pypi`, `test_noop_upgrade_records_failure_and_skips_reexec`, `test_verification_child_inherits_reexec_guard`, `test_unverifiable_upgrade_still_reexecs`, `test_fetch_parameter_replaces_pypi_query`, `test_backed_off_version_skips_upgrade`, `test_backoff_expires_after_24h`, `test_newer_version_than_failed_retries`, `test_reports_installer_index_lag_when_pypi_is_newer`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **state**: back-off read/write/clear
- **index**: installable version lookup

### Core Layer (Phase 1)
- **executor**: Depends on [state]
- **checker**: Depends on [index]

### Integration Layer (Phase 2)
- **init**: Depends on [executor, checker, state, index]

## Implementation Phases

### Phase 0: Foundation
**Goal**: The two leaf modules exist and are tested alone.

**Tasks**:
- [ ] Add `read_upgrade_failure`, `write_upgrade_failure`, `clear_upgrade_failure`, `UPGRADE_BACKOFF` to `state.py` (no deps) - Acceptance: `pytest tests/lib/pybase/updater/test_state.py -k "upgrade_failure"` passes, including `test_upgrade_failure_roundtrip_preserves_cache_and_log` and `test_clear_upgrade_failure_removes_key`.
- [ ] Add `index.py` with `fetch_installable_version` (no deps) - Acceptance: `pytest tests/lib/pybase/updater/test_index.py` passes: `test_mise_pipx_uses_mise_latest`, `test_pip_venv_parses_pip_index_versions`, `test_uv_uses_pip_compile_no_deps`, `test_pipx_and_unknown_fall_back_to_pypi`, `test_query_failure_falls_back_to_pypi`. Subprocess is mocked; no network.

**Exit Criteria**: both test files pass; `mypy src/lib/buvis/pybase/updater` is clean.

### Phase 1: Core
**Goal**: Upgrades are verified and the checker takes a version source.

**Tasks**:
- [ ] Add `read_installed_version` and verification plus back-off write to `run_update`, verification to `run_update_interactive` in `executor.py` (depends on: Phase 0) - Acceptance: `pytest tests/lib/pybase/updater/test_executor.py` passes, including new `test_noop_upgrade_records_failure_and_skips_reexec`, `test_verification_child_inherits_reexec_guard`, `test_unverifiable_upgrade_still_reexecs`, `test_interactive_noop_upgrade_returns_one`, and the existing `test_nothing_printed_to_stderr` unchanged. Premise: the existing executor tests mock `subprocess.run` with `returncode=0` only; re-check with `rg -c "def test_" tests/lib/pybase/updater/test_executor.py` (expect 20) before editing, and if the count differs stop and report; update those mocks only as far as the new `--version` call requires.
- [ ] Add the `fetch` parameter to `check_for_update` (depends on: Phase 0) - Acceptance: `pytest tests/lib/pybase/updater/test_checker.py` passes with no test changed, plus new `test_fetch_parameter_replaces_pypi_query`.

**Exit Criteria**: executor and checker tests pass.

### Phase 2: Integration
**Goal**: The orchestrator uses the installer's index and honors the back-off; `--update` is honest.

**Tasks**:
- [ ] Rewire `check_and_update` in `__init__.py`: detect installer first, pass `fetch`, skip on back-off (depends on: Phase 1) - Acceptance: `pytest tests/lib/pybase/updater/test_init.py` passes, including new `test_mirror_lagging_pypi_does_not_attempt_upgrade`, `test_backed_off_version_skips_upgrade`, `test_backoff_expires_after_24h`, `test_newer_version_than_failed_retries`, `test_noop_installer_second_invocation_skips_upgrade`, and the existing `test_restarted_process_does_not_update_again`.
- [ ] Make `force_update` report installer lag and no-op upgrades (depends on: Phase 1) - Acceptance: `pytest tests/lib/pybase/updater/test_force_update.py` passes, including new `test_reports_installer_index_lag_when_pypi_is_newer`.
- [ ] Add a `### Fixed` entry under `[Unreleased]` in `CHANGELOG.md` prefixed `**pybase**:` (depends on: Phase 1) - Acceptance: `rg -n "installer's index" CHANGELOG.md` matches under `[Unreleased]`.
- [ ] Docs: the `--update` paragraph in `README.md` (line 42 today) says the check asks the installer's own index and reports when that index lags PyPI (depends on: Phase 1) - Acceptance: `rg -n "installer" README.md` matches within three lines of `--update`.

**Exit Criteria**: `uv run --all-extras --all-groups pytest tests/lib/pybase/updater -q`, `uv run mypy src/lib/ src/tools/` and `pre-commit run --files` on the changed files all exit 0. The pipeline's single full-suite run follows.

## Test Strategy

### Critical Scenarios

- **Happy path**: installer index and PyPI agree on a newer version; the installer upgrades; verification reads the new version; the process restarts once; the back-off key is cleared.
- **Edge case**: PyPI has 0.14.1, `mise latest` says 0.13.0, installed is 0.13.0 -> no subprocess upgrade, no restart, nothing printed (`test_mirror_lagging_pypi_does_not_attempt_upgrade`).
- **Edge case**: installer lookup and PyPI both say 0.14.1 but the installer exits 0 without installing -> back-off written, no restart; a second invocation within 24h starts no installer (`test_noop_installer_second_invocation_skips_upgrade`); 0.14.2 appearing retries.
- **Error case**: lookup subprocess times out or prints garbage -> falls back to PyPI, never raises, never blocks the user's command beyond the 10s timeout.
- **Error case**: `--version` child cannot run -> behaves as before 0.14.1's guard: one restart, then the guard stops the loop.

## Risks

- **Mismatched sources inside one installer**: mise resolves "latest" through its pypi.registry_url setting, but its pipx backend installs through uv, which reads the UV_INDEX_URL variable or a uv.toml file. If only one is pointed at the mirror, the lookup can still be ahead of what installs. Mitigation: verification plus the 24h back-off caps the waste at one attempt per version per day.
- **Extra startup cost**: the lookup runs on a cache miss, so a 10s worst case lands on a command run. Mitigation: it only runs when the 6h cache is stale, and any failure falls back to PyPI.
- **`pip index versions` is marked experimental by pip**: its output shape may change. Mitigation: a parse miss falls back to PyPI and is covered by `test_query_failure_falls_back_to_pypi`.
- **A 24h back-off hides a real fix for a day**: an installer that was only briefly broken is not retried until the TTL. Mitigation: a newer target version retries immediately, and `--update` ignores the back-off.
