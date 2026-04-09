"""Tests for update execution and re-exec."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from buvis.pybase.updater.detector import InstallerInfo
from buvis.pybase.updater.executor import run_update


class TestRunUpdateKnownInstaller:
    def test_runs_upgrade_command(self) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os"),
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.click"),
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_sys.argv = ["bim", "list"]

            run_update("0.7.0", "0.8.0", installer)

        mock_sub.run.assert_called_once_with(
            ("uv", "tool", "upgrade", "buvis-gems"),
            capture_output=True,
            timeout=120,
        )

    def test_prints_updating_message_to_stderr(self) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os"),
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.click") as mock_click,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_sys.argv = ["bim", "list"]

            run_update("0.7.0", "0.8.0", installer)

        echo_calls = [str(c) for c in mock_click.echo.call_args_list]
        assert any("0.7.0" in c and "0.8.0" in c for c in echo_calls)

    def test_reexecs_on_success(self) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.click"),
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_sys.argv = ["bim", "list"]

            run_update("0.7.0", "0.8.0", installer)

        mock_os.execvp.assert_called_once_with("bim", ["bim", "list"])


class TestRunUpdateFailure:
    def test_warns_on_nonzero_exit(self) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.click") as mock_click,
        ):
            mock_sub.run.return_value = MagicMock(returncode=1, stderr=b"permission denied")
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", installer)

        mock_os.execvp.assert_not_called()
        echo_calls = [str(c) for c in mock_click.echo.call_args_list]
        assert any("failed" in c.lower() or "permission denied" in c.lower() for c in echo_calls)

    def test_warns_on_timeout(self) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.click"),
        ):
            mock_sub.run.side_effect = subprocess.TimeoutExpired(cmd="uv", timeout=120)
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", installer)

        mock_os.execvp.assert_not_called()

    def test_warns_on_file_not_found(self) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.click"),
        ):
            mock_sub.run.side_effect = FileNotFoundError("uv not found")
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", installer)

        mock_os.execvp.assert_not_called()

    def test_warns_on_os_error(self) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.click"),
        ):
            mock_sub.run.side_effect = OSError("broken pipe")
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", installer)

        mock_os.execvp.assert_not_called()


class TestRunUpdateExecvpFailure:
    def test_warns_on_execvp_os_error(self) -> None:
        installer = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.click") as mock_click,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_os.execvp.side_effect = OSError("No such file or directory")
            mock_sys.argv = ["bim", "list"]

            run_update("0.7.0", "0.8.0", installer)

        echo_calls = [str(c) for c in mock_click.echo.call_args_list]
        assert any("restart failed" in c.lower() for c in echo_calls)


class TestRunUpdateUnknownInstaller:
    def test_prints_notification_only(self) -> None:
        installer = InstallerInfo(method="unknown", upgrade_command=None)

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.click") as mock_click,
        ):
            run_update("0.7.0", "0.8.0", installer)

        mock_sub.run.assert_not_called()
        echo_calls = [str(c) for c in mock_click.echo.call_args_list]
        assert any("0.8.0" in c and "0.7.0" in c for c in echo_calls)
