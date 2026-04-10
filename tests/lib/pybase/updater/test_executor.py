"""Tests for update execution and re-exec."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.updater.detector import InstallerInfo
from buvis.pybase.updater.executor import run_update


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    return tmp_path


class TestRunUpdateKnownInstaller:
    def test_runs_upgrade_command(self, state_dir: Path) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os"),
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_sys.argv = ["bim", "list"]

            run_update("0.7.0", "0.8.0", installer, state_dir=state_dir)

        mock_sub.run.assert_called_once_with(
            ("uv", "tool", "upgrade", "buvis-gems"),
            capture_output=True,
            timeout=120,
        )

    def test_logs_updating_message(self, state_dir: Path) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os"),
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_sys.argv = ["bim", "list"]

            run_update("0.7.0", "0.8.0", installer, state_dir=state_dir)

        log_calls = [call.args for call in mock_log.call_args_list]
        assert any("0.7.0" in msg and "0.8.0" in msg for _, level, msg in log_calls if level == "info")

    def test_reexecs_on_success(self, state_dir: Path) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_sys.argv = ["bim", "list"]

            run_update("0.7.0", "0.8.0", installer, state_dir=state_dir)

        mock_os.execvp.assert_called_once_with("bim", ["bim", "list"])

    def test_nothing_printed_to_stderr(self, state_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os"),
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", installer, state_dir=state_dir)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestRunUpdateFailure:
    def test_logs_on_nonzero_exit(self, state_dir: Path) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.return_value = MagicMock(returncode=1, stderr=b"permission denied")
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", installer, state_dir=state_dir)

        mock_os.execvp.assert_not_called()
        log_calls = [call.args for call in mock_log.call_args_list]
        assert any(
            level == "error" and ("failed" in msg.lower() or "permission denied" in msg.lower())
            for _, level, msg in log_calls
        )

    def test_logs_on_timeout(self, state_dir: Path) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.side_effect = subprocess.TimeoutExpired(cmd="uv", timeout=120)
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", installer, state_dir=state_dir)

        mock_os.execvp.assert_not_called()
        assert any(level == "error" for _, level, _ in (call.args for call in mock_log.call_args_list))

    def test_logs_on_file_not_found(self, state_dir: Path) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.side_effect = FileNotFoundError("uv not found")
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", installer, state_dir=state_dir)

        mock_os.execvp.assert_not_called()
        assert any(level == "error" for _, level, _ in (call.args for call in mock_log.call_args_list))

    def test_logs_on_os_error(self, state_dir: Path) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.side_effect = OSError("broken pipe")
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", installer, state_dir=state_dir)

        mock_os.execvp.assert_not_called()
        assert any(level == "error" for _, level, _ in (call.args for call in mock_log.call_args_list))


class TestRunUpdateExecvpFailure:
    def test_logs_on_execvp_os_error(self, state_dir: Path) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_os.execvp.side_effect = OSError("No such file or directory")
            mock_sys.argv = ["bim", "list"]

            run_update("0.7.0", "0.8.0", installer, state_dir=state_dir)

        log_calls = [call.args for call in mock_log.call_args_list]
        assert any("restart failed" in msg.lower() for _, _, msg in log_calls)


class TestRunUpdateUnknownInstaller:
    def test_logs_notification_only(self, state_dir: Path) -> None:
        installer = InstallerInfo(method="unknown", upgrade_command=None)

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            run_update("0.7.0", "0.8.0", installer, state_dir=state_dir)

        mock_sub.run.assert_not_called()
        log_calls = [call.args for call in mock_log.call_args_list]
        assert any("0.8.0" in msg and "0.7.0" in msg for _, _, msg in log_calls)
