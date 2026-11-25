---
design: skip
default_model: sonnet
model_tier_rationale: Two small conftest fixtures with exact text and two tests; the only risk is a vacuous regression test, pinned by a fail-first task.
---
# Tool tests can start a real update check

Source: found 2026-11-24 while implementing PRD 00166 on branch `feature/config-local-layer-braid`.

## Problem

Most tool tests run a `@buvis_options` CLI in-process (`CliRunner`) and do not stop the passive update check. The check runs in the patched `parse_args` before the command (`_run_update_check_once` in `src/lib/buvis/pybase/configuration/click_integration.py`). It calls `check_and_update` in `src/lib/buvis/pybase/updater/__init__.py`. That function stops only when `auto_update` is false or `BUVIS_DEV_MODE` is `1`. Otherwise it asks the installer's index for a newer version and runs `run_update`, which can upgrade the shared venv.

Only two tool test directories guard against it: `tests/tools/braid/conftest.py` sets `BUVIS_DEV_MODE=1`, and `tests/tools/sysup/conftest.py` stubs `_run_update_check_once`. The others do not: backup, bim, dot, fctracker, fren, klyreon, postup and zseq. `tests/tools/backup/` has no conftest at all, so its tests also resolve settings from the developer's real `HOME`.

The full suite passes with `BUVIS_DEV_MODE=1` set (7817 passed on 2026-11-24). Only a careful developer who sets it is safe today.

## Solution

1. Add one autouse fixture to `tests/tools/conftest.py` that sets `BUVIS_DEV_MODE=1` for every tool test. `check_and_update` then returns before any network or install step. In-process CLIs see it, and subprocesses that inherit `os.environ` see it too. `BUVIS_DEV_MODE` is read only by `src/lib/buvis/pybase/updater/__init__.py`, and no tool test reads or clears it, so no other behavior changes.
2. Add `tests/tools/backup/conftest.py` with one autouse fixture that points `HOME`, `XDG_CONFIG_HOME` and `XDG_STATE_HOME` at `tmp_path`, as `tests/tools/sysup/conftest.py` does. Backup tests then never read the real config.
3. Add two regression tests in `tests/tools/backup/test_backup_cli.py`. One proves a tool CLI run never reaches the updater's index lookup. The other proves the backup tests run under a scratch `HOME`.

Not changed: `tests/lib/` (its CLI tests already patch `check_and_update` or set `BUVIS_DEV_MODE`). The sysup and braid conftests keep their own guards. `tests/lib/pybase/updater/` tests are outside `tests/tools/` and keep controlling `BUVIS_DEV_MODE` themselves.

Exact fixture for `tests/tools/conftest.py` (the file already imports `pytest`):

```python
@pytest.fixture(autouse=True)
def no_real_update_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop the passive update check from reaching the installer in every tool test."""
    monkeypatch.setenv("BUVIS_DEV_MODE", "1")
```

Exact fixture for the new `tests/tools/backup/conftest.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def isolate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every backup test away from the developer's real config and state."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
```

No CHANGELOG entry: test-only change.

## Requirements

### Must have
- Every test under `tests/tools/` runs with `BUVIS_DEV_MODE=1` unless the test overrides it.
- Every test under `tests/tools/backup/` runs with `HOME`, `XDG_CONFIG_HOME` and `XDG_STATE_HOME` under its `tmp_path`.
- `test_tool_cli_never_reaches_the_updater_index` fails when the `no_real_update_check` fixture is removed and passes with it.
- No test in the regression checks starts a real update: `detect_installer`, `check_for_update` and `run_update` are patched in it.

### Nice to have
- None.

## Implementation

### Module: tool test update guard
- **Location**: `tests/tools/conftest.py`, `tests/tools/backup/conftest.py`, `tests/tools/backup/test_backup_cli.py`
- **Responsibility**: Keep tool tests away from the real updater and, for backup, from the real config.
- **Exports**: none
- New symbols: `no_real_update_check`, `isolate_home`, `TestUpdateCheckIsolation`, `test_tool_cli_never_reaches_the_updater_index`, `test_backup_tests_run_under_a_scratch_home`
- **Risk**: A test that needs the real updater path would now stop at the `BUVIS_DEV_MODE` guard; none exists under `tests/tools/` (`rg -n "BUVIS_DEV_MODE|check_and_update|run_update" tests/tools` shows only guards and mocks). Subprocess tests that build a fresh `env=` dict do not inherit the fixture: `tests/tools/bim/test_create_note_cli_wiring.py` sets `BUVIS_AUTO_UPDATE=false` in both of its subprocess env dicts, so they stay safe.

### Dependencies
- tool test update guard: No dependencies (foundation)

## Test Strategy

Add class `TestUpdateCheckIsolation` to `tests/tools/backup/test_backup_cli.py` with two tests.

`test_tool_cli_never_reaches_the_updater_index`: patch `buvis.pybase.updater.detect_installer`, `buvis.pybase.updater.check_for_update` (`return_value=None`) and `buvis.pybase.updater.run_update`. Patch `backup.config.load_config` with `side_effect=FatalError("bad config")` so the command exits at once. Do NOT patch `check_and_update` or `_run_update_check_once`. Invoke `cli` with `CliRunner`. Assert `check_for_update` was not called and `run_update` was not called. With the backup conftest's scratch `HOME` no config sets `auto_update: false`, so without the `BUVIS_DEV_MODE` fixture `check_and_update` reaches `check_for_update` and the test fails.

`test_backup_tests_run_under_a_scratch_home`: assert `Path.home()` is inside `tmp_path`.

## Tasks

### Phase 0: Fix
- [ ] Add `tests/tools/backup/conftest.py` with the `isolate_home` fixture text from the Solution - Acceptance: `uv run pytest tests/tools/backup -q` passes.
- [ ] Add `TestUpdateCheckIsolation` with both tests to `tests/tools/backup/test_backup_cli.py`; watch `test_tool_cli_never_reaches_the_updater_index` fail (depends on: previous task) - Acceptance: `env -u BUVIS_DEV_MODE uv run pytest tests/tools/backup/test_backup_cli.py -k never_reaches_the_updater_index` fails on code without the `no_real_update_check` fixture.
- [ ] Add the `no_real_update_check` fixture text from the Solution to `tests/tools/conftest.py` (depends on: previous task) - Acceptance: `env -u BUVIS_DEV_MODE uv run pytest tests/tools/backup/test_backup_cli.py -k TestUpdateCheckIsolation` passes.

## Success Criteria

- `env -u BUVIS_DEV_MODE uv run pytest tests/tools/backup` passes.
- The project's full test gate (`uv run pytest`) passes with `BUVIS_DEV_MODE` unset in the shell.
