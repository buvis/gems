"""Tests for check_and_update orchestrator."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.updater import check_and_update
from buvis.pybase.updater.detector import InstallerInfo
from buvis.pybase.updater.executor import REEXEC_ENV


@pytest.fixture(autouse=True)
def state_dir(tmp_path: Path) -> Iterator[Path]:
    """Keep every test off the real state dir, the network and real installers."""
    with (
        patch("buvis.pybase.updater.DEFAULT_STATE_DIR", tmp_path),
        patch("buvis.pybase.updater.executor.DEFAULT_STATE_DIR", tmp_path),
        patch("buvis.pybase.updater.checker.urlopen", side_effect=OSError("network disabled in tests")),
        patch("subprocess.run", side_effect=AssertionError("real subprocess in test")),
    ):
        yield tmp_path


def _mise_pipx_installer() -> InstallerInfo:
    return InstallerInfo(method="mise-pipx", upgrade_command=("mise", "upgrade", "pipx:buvis-gems"))


def _seed_upgrade_failure(state_dir: Path, version: str, age: timedelta) -> None:
    ts = (datetime.now(tz=timezone.utc) - age).isoformat()
    (state_dir / "updater.json").write_text(json.dumps({"upgrade_failed": {"version": version, "ts": ts}}))


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

    def test_skips_in_process_restarted_by_update(self) -> None:
        settings = _make_settings()

        with (
            patch.dict("os.environ", {REEXEC_ENV: "1"}),
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
            patch("buvis.pybase.updater.detect_installer", return_value=_mise_pipx_installer()),
            patch("buvis.pybase.updater.run_update") as mock_run,
        ):
            check_and_update(settings)

        mock_run.assert_not_called()


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


class TestInstallerExitsZeroWithoutInstalling:
    def test_restarted_process_does_not_update_again(self, tmp_path: Path) -> None:
        """mise hides releases younger than minimum_release_age and exits 0: no re-exec loop."""
        settings = _make_settings()
        installer_info = InstallerInfo(method="mise-pipx", upgrade_command=("mise", "upgrade", "pipx:buvis-gems"))

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("buvis.pybase.updater.check_for_update", return_value="0.14.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=installer_info),
            patch("buvis.pybase.updater.pkg_version", return_value="0.13.0"),
            patch("buvis.pybase.updater.executor.DEFAULT_STATE_DIR", tmp_path),
            patch("buvis.pybase.updater.executor.subprocess.run", return_value=MagicMock(returncode=0)) as mock_run,
            patch("buvis.pybase.updater.executor._resolve_reexec_argv", return_value=["dot", "status"]),
            # The --version check cannot run here, so the 0.14.1 path applies: restart once under the guard.
            patch("buvis.pybase.updater.executor.read_installed_version", return_value=None),
            patch("buvis.pybase.updater.executor.os.execvp") as mock_execvp,
        ):
            check_and_update(settings)  # first process: upgrades, re-execs
            check_and_update(settings)  # restarted process inherits the environment

        mock_run.assert_called_once()
        mock_execvp.assert_called_once()


class TestInstallerIndex:
    def test_mirror_lagging_pypi_does_not_attempt_upgrade(
        self, state_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """PyPI has 0.14.1, the installer's index only 0.13.0: no upgrade, no restart, no output."""
        calls: list[tuple[str, ...]] = []

        def fake_run(argv: tuple[str, ...], **kwargs: object) -> MagicMock:
            calls.append(tuple(argv))
            if tuple(argv) == ("mise", "latest", "pipx:buvis-gems"):
                return MagicMock(returncode=0, stdout="0.13.0\n")
            raise AssertionError(f"unexpected subprocess: {argv}")

        response = MagicMock()
        response.read.return_value = json.dumps({"info": {"version": "0.14.1"}}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("buvis.pybase.updater.pkg_version", return_value="0.13.0"),
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.13.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=_mise_pipx_installer()),
            patch("buvis.pybase.updater.checker.urlopen", return_value=response),
            patch("subprocess.run", side_effect=fake_run),
            patch("buvis.pybase.updater.executor.os.execvp") as mock_execvp,
        ):
            check_and_update(_make_settings())

        assert calls == [("mise", "latest", "pipx:buvis-gems")]
        mock_execvp.assert_not_called()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestUpgradeBackoff:
    def _run(self, latest: str) -> MagicMock:
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("buvis.pybase.updater.pkg_version", return_value="0.13.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=_mise_pipx_installer()),
            patch("buvis.pybase.updater.check_for_update", return_value=latest),
            patch("buvis.pybase.updater.run_update") as mock_run,
        ):
            check_and_update(_make_settings())
        return mock_run

    def test_backed_off_version_skips_upgrade(self, state_dir: Path) -> None:
        _seed_upgrade_failure(state_dir, "0.14.1", timedelta(hours=1))

        self._run("0.14.1").assert_not_called()

    def test_backoff_expires_after_24h(self, state_dir: Path) -> None:
        _seed_upgrade_failure(state_dir, "0.14.1", timedelta(hours=25))

        self._run("0.14.1").assert_called_once()

    def test_newer_version_than_failed_retries(self, state_dir: Path) -> None:
        _seed_upgrade_failure(state_dir, "0.14.1", timedelta(hours=1))

        self._run("0.14.2").assert_called_once()

    def test_noop_installer_second_invocation_skips_upgrade(self, state_dir: Path) -> None:
        """Installer exits 0 without installing: one attempt, then the back-off holds."""
        upgrade_calls: list[tuple[str, ...]] = []

        def fake_run(argv: tuple[str, ...] | list[str], **kwargs: object) -> MagicMock:
            if tuple(argv) == ("mise", "upgrade", "pipx:buvis-gems"):
                upgrade_calls.append(tuple(argv))
                return MagicMock(returncode=0, stderr=b"")
            if list(argv) == ["dot", "--version"]:
                return MagicMock(returncode=0, stdout="buvis-gems, version 0.13.0\n")
            raise AssertionError(f"unexpected subprocess: {argv}")

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("buvis.pybase.updater.pkg_version", return_value="0.13.0"),
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.13.0"),
            patch("buvis.pybase.updater.detect_installer", return_value=_mise_pipx_installer()),
            patch("buvis.pybase.updater.fetch_installable_version", return_value="0.14.1"),
            patch("subprocess.run", side_effect=fake_run),
            patch("buvis.pybase.updater.executor._resolve_reexec_argv", return_value=["dot", "status"]),
            patch("buvis.pybase.updater.executor.os.execvp") as mock_execvp,
        ):
            check_and_update(_make_settings())  # attempts, verification shows a no-op
            check_and_update(_make_settings())  # a fresh process within 24h

        assert len(upgrade_calls) == 1
        mock_execvp.assert_not_called()
        state = json.loads((state_dir / "updater.json").read_text())
        assert state["upgrade_failed"]["version"] == "0.14.1"


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
