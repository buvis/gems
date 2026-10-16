"""Tests for the user-initiated force_update entry point."""

from __future__ import annotations

import json
from collections.abc import Iterator
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.updater import check_and_update, force_update
from buvis.pybase.updater.detector import InstallerInfo


@pytest.fixture(autouse=True)
def _hermetic(tmp_path: Path) -> Iterator[Path]:
    """Keep every test off the real state dir, the network and real installers."""
    with (
        patch("buvis.pybase.updater.DEFAULT_STATE_DIR", tmp_path),
        patch("buvis.pybase.updater.executor.DEFAULT_STATE_DIR", tmp_path),
        patch("buvis.pybase.updater.checker.urlopen", side_effect=OSError("network disabled in tests")),
        patch("subprocess.run", side_effect=AssertionError("real subprocess in test")),
    ):
        yield tmp_path


def _make_settings(installer: str | None = None) -> MagicMock:
    settings = MagicMock()
    settings.installer = installer
    return settings


def _uv_tool_installer() -> InstallerInfo:
    return InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))


def _mise_pipx_installer() -> InstallerInfo:
    return InstallerInfo(method="mise-pipx", upgrade_command=("mise", "upgrade", "pipx:buvis-gems"))


def _unknown_installer() -> InstallerInfo:
    return InstallerInfo(method="unknown", upgrade_command=None)


def _mock_pypi_response(version: str) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps({"info": {"version": version}}).encode()
    response.__enter__ = lambda s: s
    response.__exit__ = MagicMock(return_value=False)
    return response


class TestPackageNotFound:
    def test_returns_one_and_prints(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch(
            "buvis.pybase.updater.pkg_version",
            side_effect=PackageNotFoundError("buvis-gems"),
        ):
            result = force_update(_make_settings())

        assert result == 1
        out = capsys.readouterr().out
        assert "buvis-gems" in out.lower() and "not installed" in out.lower()
        assert "✘" in out  # console.failure's CROSSMARK; proves routing through the console adapter

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
            patch("buvis.pybase.updater.fetch_installable_version", return_value=None),
        ):
            result = force_update(_make_settings())

        assert result == 1
        out = capsys.readouterr().out
        assert "pypi" in out.lower() or "reach" in out.lower() or "unreachable" in out.lower()
        assert "✘" in out  # console.failure's CROSSMARK; proves routing through the console adapter

    def test_logs_error_event(self) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.fetch_installable_version", return_value=None),
            patch("buvis.pybase.updater.append_log") as mock_log,
        ):
            force_update(_make_settings())

        assert any(call.args[1] == "error" for call in mock_log.call_args_list)


class TestAlreadyUpToDate:
    def test_returns_zero_and_prints_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.fetch_installable_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=_uv_tool_installer()),
            patch("buvis.pybase.updater.run_update_interactive") as mock_run,
        ):
            result = force_update(_make_settings())

        assert result == 0
        out = capsys.readouterr().out
        assert "0.8.0" in out
        assert "up to date" in out.lower()
        assert "✔" in out  # console.success's CHECKMARK; proves routing through the console adapter
        mock_run.assert_not_called()

    def test_logs_info_event(self) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.fetch_installable_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.append_log") as mock_log,
        ):
            force_update(_make_settings())

        assert any(call.args[1] == "info" for call in mock_log.call_args_list)

    def test_current_newer_than_pypi_is_up_to_date(self) -> None:
        """Installed pre-release newer than stable PyPI: treat as up to date."""
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.9.0rc1"),
            patch("buvis.pybase.updater.fetch_installable_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.run_update_interactive") as mock_run,
        ):
            result = force_update(_make_settings())

        assert result == 0
        mock_run.assert_not_called()


class TestInstallerIndexLag:
    def test_reports_installer_index_lag_when_pypi_is_newer(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.13.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=_mise_pipx_installer()),
            patch("buvis.pybase.updater.fetch_installable_version", return_value="0.13.0"),
            patch("buvis.pybase.updater.fetch_latest_version", return_value="0.14.1"),
            patch("buvis.pybase.updater.run_update_interactive") as mock_run,
        ):
            result = force_update(_make_settings())

        assert result == 0
        out = " ".join(capsys.readouterr().out.split())
        assert "buvis-gems 0.13.0 is the newest your installer offers (PyPI has 0.14.1)." in out
        assert "✔" in out
        mock_run.assert_not_called()

    def test_lag_report_then_passive_check_does_not_upgrade(
        self, _hermetic: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--update caches both sources; the next passive check trusts only the installer's index."""
        state_dir = _hermetic
        query_calls: list[tuple[str, ...]] = []

        def fake_run(argv: tuple[str, ...], **kwargs: object) -> MagicMock:
            query_calls.append(tuple(argv))
            if tuple(argv) == ("mise", "latest", "pipx:buvis-gems"):
                return MagicMock(returncode=0, stdout="0.13.0\n")
            raise AssertionError(f"unexpected subprocess: {argv}")

        settings = _make_settings()
        settings.auto_update = True
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("buvis.pybase.updater.pkg_version", return_value="0.13.0"),
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.13.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=_mise_pipx_installer()),
            patch("buvis.pybase.updater.checker.urlopen", return_value=_mock_pypi_response("0.14.1")),
            patch("subprocess.run", side_effect=fake_run),
            patch("buvis.pybase.updater.executor.os.execvp") as mock_execvp,
        ):
            result = force_update(settings)
            check_and_update(settings)

        assert result == 0
        out = " ".join(capsys.readouterr().out.split())
        assert "buvis-gems 0.13.0 is the newest your installer offers (PyPI has 0.14.1)." in out
        state = json.loads((state_dir / "updater.json").read_text())
        assert state["latest_version"] == "0.14.1"
        assert state["installer_cache"]["method"] == "mise-pipx"
        assert state["installer_cache"]["latest_version"] == "0.13.0"
        assert query_calls == [("mise", "latest", "pipx:buvis-gems")]  # no upgrade command ever ran
        mock_execvp.assert_not_called()


class TestUnknownInstaller:
    def test_prints_manual_commands_and_returns_one(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.fetch_installable_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=_unknown_installer()),
            patch("buvis.pybase.updater.run_update_interactive") as mock_run,
        ):
            result = force_update(_make_settings())

        assert result == 1
        out = capsys.readouterr().out
        assert "uv tool upgrade buvis-gems" in out
        assert "pipx upgrade buvis-gems" in out
        assert "mise upgrade pipx:buvis-gems" in out
        assert "✘" in out  # console.failure's CROSSMARK; proves routing through the console adapter
        mock_run.assert_not_called()

    def test_logs_error_event(self) -> None:
        with (
            patch("buvis.pybase.updater.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.fetch_installable_version", return_value="0.8.0"),
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
            patch("buvis.pybase.updater.fetch_installable_version", return_value="0.8.0"),
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
            patch("buvis.pybase.updater.fetch_installable_version", return_value="0.8.0"),
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
            patch("buvis.pybase.updater.fetch_installable_version", return_value="0.8.0") as mock_fetch,
        ):
            result = force_update(settings)

        assert result == 0
        mock_fetch.assert_called_once()

    def test_runs_even_in_dev_mode(self) -> None:
        with (
            patch.dict("os.environ", {"BUVIS_DEV_MODE": "1"}),
            patch("buvis.pybase.updater.pkg_version", return_value="0.8.0"),
            patch("buvis.pybase.updater.fetch_installable_version", return_value="0.8.0") as mock_fetch,
        ):
            result = force_update(_make_settings())

        assert result == 0
        mock_fetch.assert_called_once()
