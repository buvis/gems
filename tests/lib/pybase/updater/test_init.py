"""Tests for check_and_update orchestrator."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from unittest.mock import MagicMock, patch

from buvis.pybase.updater import check_and_update
from buvis.pybase.updater.detector import InstallerInfo


def _make_settings(auto_update: bool = True, installer: str | None = None) -> MagicMock:
    settings = MagicMock()
    settings.auto_update = auto_update
    settings.installer = installer
    return settings


class TestGuards:
    def test_skips_when_auto_update_disabled(self) -> None:
        settings = _make_settings(auto_update=False)

        with patch("buvis.pybase.updater.check_for_update") as mock_check:
            check_and_update(settings)

        mock_check.assert_not_called()

    def test_skips_in_dev_mode(self) -> None:
        settings = _make_settings()

        with (
            patch.dict("os.environ", {"BUVIS_DEV_MODE": "1"}),
            patch("buvis.pybase.updater.check_for_update") as mock_check,
        ):
            check_and_update(settings)

        mock_check.assert_not_called()

    def test_runs_when_dev_mode_not_set(self) -> None:
        settings = _make_settings()

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("buvis.pybase.updater.check_for_update", return_value=None) as mock_check,
        ):
            check_and_update(settings)

        mock_check.assert_called_once()


class TestNoUpdate:
    def test_returns_when_no_update_available(self) -> None:
        settings = _make_settings()

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("buvis.pybase.updater.check_for_update", return_value=None),
            patch("buvis.pybase.updater.detect_installer") as mock_detect,
        ):
            check_and_update(settings)

        mock_detect.assert_not_called()


class TestUpdateAvailable:
    def test_detects_installer_and_runs_update(self) -> None:
        settings = _make_settings(installer="uv-tool")
        installer_info = InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("buvis.pybase.updater.check_for_update", return_value="0.8.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=installer_info) as mock_detect,
            patch("buvis.pybase.updater.run_update") as mock_run,
            patch("buvis.pybase.updater.pkg_version", return_value="0.7.0"),
        ):
            check_and_update(settings)

        mock_detect.assert_called_once_with(override="uv-tool")
        mock_run.assert_called_once_with("0.7.0", "0.8.0", installer_info)

    def test_passes_none_override_when_no_installer_configured(self) -> None:
        settings = _make_settings(installer=None)
        installer_info = InstallerInfo(method="unknown", upgrade_command=None)

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("buvis.pybase.updater.check_for_update", return_value="0.8.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=installer_info) as mock_detect,
            patch("buvis.pybase.updater.run_update"),
            patch("buvis.pybase.updater.pkg_version", return_value="0.7.0"),
        ):
            check_and_update(settings)

        mock_detect.assert_called_once_with(override=None)


class TestPackageNotFound:
    def test_returns_early_when_package_not_found(self) -> None:
        """check_and_update returns without error when pkg_version raises."""
        settings = _make_settings()

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("buvis.pybase.updater.check_for_update", return_value="0.8.0"),
            patch("buvis.pybase.updater.detect_installer") as mock_detect,
            patch("buvis.pybase.updater.pkg_version", side_effect=PackageNotFoundError("buvis-gems")),
        ):
            check_and_update(settings)

        mock_detect.assert_not_called()
