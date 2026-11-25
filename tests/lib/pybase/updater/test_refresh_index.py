"""Tests for clearing uv's cached package index before an upgrade."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.updater.detector import InstallerInfo
from buvis.pybase.updater.executor import _refresh_package_index, run_update, run_update_interactive

_CLEAN_ARGS = ("uv", "cache", "clean", "buvis-gems")
_WARNING_PREFIX = "Could not refresh uv cache for buvis-gems:"


def _installer(method: str) -> InstallerInfo:
    return InstallerInfo(method=method, upgrade_command=("installer", "upgrade", "buvis-gems"))


def _mise_pipx_installer() -> InstallerInfo:
    return InstallerInfo(method="mise-pipx", upgrade_command=("mise", "upgrade", "pipx:buvis-gems"))


def _warnings(mock_log: MagicMock) -> list[tuple[Path, str, str]]:
    return [call.args for call in mock_log.call_args_list if call.args[1] == "warning"]


class TestRefreshPackageIndex:
    @pytest.mark.parametrize("method", ["mise-pipx", "uv-tool", "uv-venv"])
    def test_cleans_uv_cache_for_uv_backed_installers(self, method: str, tmp_path: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess.run") as mock_run,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")

            _refresh_package_index(_installer(method), tmp_path)

        mock_run.assert_called_once()
        assert mock_run.call_args.args == (_CLEAN_ARGS,)
        assert mock_run.call_args.kwargs == {"capture_output": True, "timeout": 30, "cwd": tmp_path}
        mock_log.assert_not_called()

    @pytest.mark.parametrize("method", ["pipx", "pip-venv", "unknown"])
    def test_skips_installers_that_do_not_use_uv(self, method: str, tmp_path: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess.run") as mock_run,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            _refresh_package_index(_installer(method), tmp_path)

        mock_run.assert_not_called()
        mock_log.assert_not_called()

    def test_missing_uv_logs_warning_and_returns(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess.run", side_effect=FileNotFoundError("uv")) as mock_run,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            _refresh_package_index(_installer("uv-tool"), tmp_path)

        mock_run.assert_called_once()
        warnings = _warnings(mock_log)
        assert len(warnings) == 1
        assert warnings[0][0] == tmp_path
        assert warnings[0][2].startswith(_WARNING_PREFIX)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_timeout_logs_warning_and_returns(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        timeout = subprocess.TimeoutExpired(cmd="uv", timeout=30)
        with (
            patch("buvis.pybase.updater.executor.subprocess.run", side_effect=timeout) as mock_run,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            _refresh_package_index(_installer("mise-pipx"), tmp_path)

        mock_run.assert_called_once()
        warnings = _warnings(mock_log)
        assert len(warnings) == 1
        assert warnings[0][0] == tmp_path
        assert warnings[0][2].startswith(_WARNING_PREFIX)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_failed_clean_logs_warning_with_stderr(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess.run") as mock_run,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_run.return_value = MagicMock(returncode=2, stderr=b"lock busy")

            _refresh_package_index(_installer("uv-venv"), tmp_path)

        warnings = _warnings(mock_log)
        assert len(warnings) == 1
        assert warnings[0][0] == tmp_path
        assert warnings[0][2].startswith(_WARNING_PREFIX)
        assert "lock busy" in warnings[0][2]
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestUpgradeRunsAfterRefresh:
    def test_auto_update_cleans_cache_before_upgrade(self, tmp_path: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os"),
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.read_installed_version", return_value="0.8.0"),
        ):
            mock_sub.run.return_value = MagicMock(returncode=0, stderr=b"")
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            mock_sys.argv = ["bim", "list"]

            run_update("0.7.0", "0.8.0", _mise_pipx_installer(), state_dir=tmp_path)

        assert mock_sub.run.call_args_list[0].args[0] == _CLEAN_ARGS
        assert mock_sub.run.call_args_list[1].args[0] == ("mise", "upgrade", "pipx:buvis-gems")

    def test_interactive_update_cleans_cache_before_upgrade(self, tmp_path: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os"),
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.read_installed_version", return_value="0.8.0"),
        ):
            mock_sub.run.return_value = MagicMock(returncode=0, stderr=b"")
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            mock_sys.argv = ["bim", "--update"]

            result = run_update_interactive("0.7.0", "0.8.0", _mise_pipx_installer(), state_dir=tmp_path)

        assert result == 0
        assert mock_sub.run.call_args_list[0].args[0] == _CLEAN_ARGS
        assert mock_sub.run.call_args_list[1].args[0] == ("mise", "upgrade", "pipx:buvis-gems")

    def test_upgrade_still_runs_when_clean_fails(self, tmp_path: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os"),
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.read_installed_version", return_value="0.8.0"),
        ):
            mock_sub.run.side_effect = [FileNotFoundError("uv"), MagicMock(returncode=0, stderr=b"")]
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            mock_sys.argv = ["bim", "list"]

            run_update("0.7.0", "0.8.0", _mise_pipx_installer(), state_dir=tmp_path)

        assert mock_sub.run.call_args_list[0].args[0] == _CLEAN_ARGS
        assert mock_sub.run.call_args_list[1].args[0] == ("mise", "upgrade", "pipx:buvis-gems")
