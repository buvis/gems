"""Phase 1: the platform-dispatched scheduler installer, subprocess-mocked.

Every external boundary (``launchctl``, ``crontab``) is mocked so the tests run
on any OS. The manifest is isolated via ``$XDG_STATE_HOME``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from klyreon.assets.manifest import load_manifest
from klyreon.schedule import installer
from klyreon.schedule.installer import MANAGED_MARKER, UnsupportedPlatformError

pytestmark = pytest.mark.klyreon


@pytest.fixture(autouse=True)
def isolate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))


def _ok(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str = "boom") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


# --------------------------------------------------------------------------- #
# launchd (macOS)
# --------------------------------------------------------------------------- #


class TestLaunchdInstall:
    def test_install_writes_plist_bootstraps_and_records(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(installer, "_platform", lambda: "darwin")
        monkeypatch.setattr(installer.os, "getuid", lambda: 501, raising=False)
        plist_path = tmp_path / "agents" / "net.buvis.klyreon.plist"
        monkeypatch.setattr(installer, "_plist_path", lambda: plist_path)
        calls: list[list[str]] = []

        def fake_launchctl(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return _ok()

        monkeypatch.setattr(installer, "_launchctl", fake_launchctl)

        res = installer.install(binary="/usr/local/bin/klyreon", hour=3, minute=0, path_env="/bin")
        assert res.success is True
        assert plist_path.is_file()
        # bootout happened before bootstrap (re-run safe), then bootstrap.
        assert any(c[0] == "bootout" for c in calls)
        assert any(c[0] == "bootstrap" for c in calls)
        entries = [e for e in load_manifest().entries if e.kind == "schedule"]
        assert len(entries) == 1
        assert entries[0].path == str(plist_path)

    def test_bootstrap_failure_records_nothing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(installer, "_platform", lambda: "darwin")
        monkeypatch.setattr(installer.os, "getuid", lambda: 501, raising=False)
        plist_path = tmp_path / "agents" / "net.buvis.klyreon.plist"
        monkeypatch.setattr(installer, "_plist_path", lambda: plist_path)

        def fake_launchctl(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
            return _ok() if args[0] == "bootout" else _fail("Load failed")

        monkeypatch.setattr(installer, "_launchctl", fake_launchctl)

        res = installer.install(binary="/usr/local/bin/klyreon", hour=3, minute=0, path_env="/bin")
        assert res.success is False
        assert "launchctl bootstrap failed" in res.message
        # No manifest entry for an artifact that is not loaded.
        assert [e for e in load_manifest().entries if e.kind == "schedule"] == []
        assert not plist_path.exists()

    def test_status_and_uninstall(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(installer, "_platform", lambda: "darwin")
        monkeypatch.setattr(installer.os, "getuid", lambda: 501, raising=False)
        plist_path = tmp_path / "agents" / "net.buvis.klyreon.plist"
        monkeypatch.setattr(installer, "_plist_path", lambda: plist_path)
        monkeypatch.setattr(installer, "_launchctl", lambda args, check=False: _ok())

        installer.install(binary="/usr/local/bin/klyreon", hour=4, minute=0, path_env="/bin")
        info = installer.status(last_maintain="2026-04-10T03:00:00+02:00")
        assert info.installed and info.present_on_disk and info.hash_matches and info.loaded
        assert info.scheduled_time == "04:00"
        assert info.last_maintain == "2026-04-10T03:00:00+02:00"

        res = installer.uninstall()
        assert res.success
        assert not plist_path.exists()
        assert [e for e in load_manifest().entries if e.kind == "schedule"] == []

    def test_edited_artifact_reported_not_rewritten(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(installer, "_platform", lambda: "darwin")
        monkeypatch.setattr(installer.os, "getuid", lambda: 501, raising=False)
        plist_path = tmp_path / "agents" / "net.buvis.klyreon.plist"
        monkeypatch.setattr(installer, "_plist_path", lambda: plist_path)
        monkeypatch.setattr(installer, "_launchctl", lambda args, check=False: _ok())

        installer.install(binary="/usr/local/bin/klyreon", hour=4, minute=0, path_env="/bin")
        plist_path.write_text(plist_path.read_text() + "\n<!-- hand edit -->\n", encoding="utf-8")
        info = installer.status()
        assert info.hash_matches is False
        assert "edited" in info.message


# --------------------------------------------------------------------------- #
# cron (Linux)
# --------------------------------------------------------------------------- #


class TestCronInstall:
    def test_install_then_reinstall_leaves_one_marked_line_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(installer, "_platform", lambda: "linux")
        crontab: dict[str, str] = {"text": "# existing user line\n0 0 * * * echo hi\n"}
        monkeypatch.setattr(installer, "_crontab_read", lambda: crontab["text"])
        monkeypatch.setattr(installer, "_crontab_write", lambda text: crontab.__setitem__("text", text))

        installer.install(binary="/usr/local/bin/klyreon", hour=3, minute=0, path_env="/bin")
        installer.install(binary="/usr/local/bin/klyreon", hour=3, minute=0, path_env="/bin")

        managed = [ln for ln in crontab["text"].splitlines() if MANAGED_MARKER in ln]
        schedule_lines = [ln for ln in managed if ln.lstrip()[0:1].isdigit()]
        assert len(schedule_lines) == 1  # exactly one schedule line after re-install
        assert "# existing user line" in crontab["text"]  # user content preserved
        entries = [e for e in load_manifest().entries if e.kind == "schedule"]
        assert len(entries) == 1

    def test_status_reports_loaded_and_time(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(installer, "_platform", lambda: "linux")
        crontab: dict[str, str] = {"text": ""}
        monkeypatch.setattr(installer, "_crontab_read", lambda: crontab["text"])
        monkeypatch.setattr(installer, "_crontab_write", lambda text: crontab.__setitem__("text", text))

        installer.install(binary="/usr/local/bin/klyreon", hour=6, minute=15, path_env="/bin")
        info = installer.status()
        assert info.installed and info.loaded and info.hash_matches
        assert info.scheduled_time == "06:15"

    def test_uninstall_strips_managed_lines_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(installer, "_platform", lambda: "linux")
        crontab: dict[str, str] = {"text": "0 0 * * * echo keep-me\n"}
        monkeypatch.setattr(installer, "_crontab_read", lambda: crontab["text"])
        monkeypatch.setattr(installer, "_crontab_write", lambda text: crontab.__setitem__("text", text))

        installer.install(binary="/usr/local/bin/klyreon", hour=3, minute=0, path_env="/bin")
        installer.uninstall()
        assert "echo keep-me" in crontab["text"]
        assert MANAGED_MARKER not in crontab["text"]
        assert [e for e in load_manifest().entries if e.kind == "schedule"] == []


class TestUnsupportedPlatform:
    def test_windows_fails_with_manual_equivalent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(installer, "_platform", lambda: "win32")
        with pytest.raises(UnsupportedPlatformError, match="ingest; .*maintain"):
            installer.install(binary="C:/klyreon.exe", hour=3, minute=0, path_env="C:/bin")
        assert [e for e in load_manifest().entries if e.kind == "schedule"] == []


class TestStatusNotInstalled:
    def test_reports_not_installed(self) -> None:
        info = installer.status()
        assert info.installed is False
