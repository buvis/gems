"""Phase 0: the single-instance vault lock."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from klyreon.run.lock import LockBusyError, lock_path, vault_lock

pytestmark = pytest.mark.klyreon


class TestVaultLock:
    def test_second_in_process_acquisition_is_busy(self, tmp_path: Path) -> None:
        root = tmp_path / "vault"
        root.mkdir()
        with vault_lock(root):
            with pytest.raises(LockBusyError):
                with vault_lock(root):
                    pass

    def test_released_after_keyboard_interrupt(self, tmp_path: Path) -> None:
        root = tmp_path / "vault"
        root.mkdir()
        with pytest.raises(KeyboardInterrupt):
            with vault_lock(root):
                raise KeyboardInterrupt
        # Lock is free again: a fresh acquisition succeeds.
        with vault_lock(root):
            pass

    def test_killed_process_leaves_no_stale_lock(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        root = tmp_path / "vault"
        root.mkdir()
        state_home = str(tmp_path / "state")
        monkeypatch.setenv("XDG_STATE_HOME", state_home)
        # A child holds the lock, then is SIGKILLed. The kernel releases the
        # flock on process death, so the parent can take it immediately after.
        src_root = Path(__file__).resolve().parents[4] / "src"
        env = dict(os.environ)
        env["XDG_STATE_HOME"] = state_home
        env["PYTHONPATH"] = os.pathsep.join([str(src_root / "tools"), str(src_root / "lib")])
        holder = (
            "import time\n"
            "from pathlib import Path\n"
            "from klyreon.run.lock import vault_lock\n"
            f"with vault_lock(Path({str(root)!r})):\n"
            "    print('locked', flush=True)\n"
            "    time.sleep(30)\n"
        )
        proc = subprocess.Popen([sys.executable, "-c", holder], stdout=subprocess.PIPE, env=env)
        assert proc.stdout is not None
        line = proc.stdout.readline().strip()
        assert line == b"locked", line
        proc.kill()
        proc.wait(timeout=5)
        # No stale lock: acquisition succeeds right away.
        with vault_lock(root):
            pass

    def test_lock_path_is_stable_and_hashed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        root = tmp_path / "vault"
        root.mkdir()
        p1 = lock_path(root)
        p2 = lock_path(root)
        assert p1 == p2
        assert p1.suffix == ".lock"
        assert p1.name != "vault.lock"  # hashed, not the raw name
