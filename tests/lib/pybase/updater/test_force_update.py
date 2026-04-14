"""Tests for the user-initiated force_update entry point."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.updater import force_update
from buvis.pybase.updater.detector import InstallerInfo


def _make_settings(installer: str | None = None) -> MagicMock:
    settings = MagicMock()
    settings.installer = installer
    return settings


def _uv_tool_installer() -> InstallerInfo:
    return InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))


def _unknown_installer() -> InstallerInfo:
    return InstallerInfo(method="unknown", upgrade_command=None)


class TestPackageNotFound:
    def test_returns_one_and_prints(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch(
            "buvis.pybase.updater.pkg_version",
            side_effect=PackageNotFoundError("buvis-gems"),
        ):
            result = force_update(_make_settings())

        assert result == 1
        err = capsys.readouterr().err
        assert "buvis-gems" in err.lower() and "not installed" in err.lower()

    def test_logs_error_event(self) -> None:
        with (
            patch(
                "buvis.pybase.updater.pkg_version",
                side_effect=PackageNotFoundError("buvis-gems"),
            ),
            patch("buvis.pybase.updater.append_log") as mock_log,
        ):
            force_update(_make_settings())

        assert any(call.args[1] == "error" for call in mock_log.call_args_list)


class TestPypiUnreachable:
    def test_returns_one_and_prints(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.fetch_latest_version", return_value=None),
        ):
            result = force_update(_make_settings())

        assert result == 1
        err = capsys.readouterr().err
        assert "pypi" in err.lower() or "reach" in err.lower() or "unreachable" in err.lower()

    def test_logs_error_event(self) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.fetch_latest_version", return_value=None),
            patch("buvis.pybase.updater.append_log") as mock_log,
        ):
            force_update(_make_settings())

        assert any(call.args[1] == "error" for call in mock_log.call_args_list)


class TestAlreadyUpToDate:
    def test_returns_zero_and_prints_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.fetch_latest_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.detect_installer") as mock_detect,
            patch("buvis.pybase.updater.run_update_interactive") as mock_run,
        ):
            result = force_update(_make_settings())

        assert result == 0
        out = capsys.readouterr().out
        assert "0.8.0" in out
        assert "up to date" in out.lower()
        mock_detect.assert_not_called()
        mock_run.assert_not_called()

    def test_logs_info_event(self) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.fetch_latest_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.append_log") as mock_log,
        ):
            force_update(_make_settings())

        assert any(call.args[1] == "info" for call in mock_log.call_args_list)

    def test_current_newer_than_pypi_is_up_to_date(self) -> None:
        """Installed pre-release newer than stable PyPI: treat as up to date."""
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.9.0rc1"),
            patch("buvis.pybase.updater.fetch_latest_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.run_update_interactive") as mock_run,
        ):
            result = force_update(_make_settings())

        assert result == 0
        mock_run.assert_not_called()


class TestUnknownInstaller:
    def test_prints_manual_commands_and_returns_one(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.fetch_latest_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=_unknown_installer()),
            patch("buvis.pybase.updater.run_update_interactive") as mock_run,
        ):
            result = force_update(_make_settings())

        assert result == 1
        err = capsys.readouterr().err
        assert "uv tool upgrade buvis-gems" in err
        assert "pipx upgrade buvis-gems" in err
        assert "mise upgrade pipx:buvis-gems" in err
        mock_run.assert_not_called()

    def test_logs_error_event(self) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.fetch_latest_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=_unknown_installer()),
            patch("buvis.pybase.updater.append_log") as mock_log,
        ):
            force_update(_make_settings())

        assert any(call.args[1] == "error" for call in mock_log.call_args_list)


class TestUpgradePath:
    def test_delegates_to_run_update_interactive(self) -> None:
        installer = _uv_tool_installer()
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.fetch_latest_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=installer) as mock_detect,
            patch("buvis.pybase.updater.run_update_interactive", return_value=0) as mock_run,
        ):
            result = force_update(_make_settings(installer="uv-tool"))

        assert result == 0
        mock_detect.assert_called_once_with(override="uv-tool")
        mock_run.assert_called_once_with("0.7.0", "0.8.0", installer)

    def test_propagates_nonzero_exit_code(self) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.fetch_latest_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=_uv_tool_installer()),
            patch("buvis.pybase.updater.run_update_interactive", return_value=1),
        ):
            result = force_update(_make_settings())

        assert result == 1


class TestBypassesGuards:
    def test_runs_even_when_auto_update_false(self) -> None:
        settings = _make_settings()
        settings.auto_update = False

        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.fetch_latest_version", return_value="0.8.0") as mock_fetch,
        ):
            result = force_update(settings)

        assert result == 0
        mock_fetch.assert_called_once()

    def test_runs_even_in_dev_mode(self) -> None:
        with (
            patch.dict("os.environ", {"BUVIS_DEV_MODE": "1"}),
            patch("buvis.pybase.updater.pkg_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.fetch_latest_version", return_value="0.8.0") as mock_fetch,
        ):
            result = force_update(_make_settings())

        assert result == 0
        mock_fetch.assert_called_once()
