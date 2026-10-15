"""Tests for the installer-index version lookup."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.updater.detector import InstallerInfo
from buvis.pybase.updater.index import fetch_installable_version

_PYPI = "9.9.9"


def _installer(method: str) -> InstallerInfo:
    return InstallerInfo(method=method, upgrade_command=None)


def _lookup(method: str, state_dir: Path, run: MagicMock) -> tuple[str | None, MagicMock]:
    with (
        patch("buvis.pybase.updater.index.subprocess.run", run),
        patch("buvis.pybase.updater.index._query_pypi", return_value=_PYPI) as mock_pypi,
    ):
        return fetch_installable_version(_installer(method), state_dir), mock_pypi


class TestInstallerQueries:
    def test_mise_pipx_uses_mise_latest(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "missing" / "state"
        run = MagicMock(return_value=MagicMock(returncode=0, stdout="0.13.0\n"))

        version, mock_pypi = _lookup("mise-pipx", state_dir, run)

        assert version == "0.13.0"
        mock_pypi.assert_not_called()
        assert run.call_args.args[0] == ("mise", "latest", "pipx:buvis-gems")
        assert run.call_args.kwargs["timeout"] == 10
        assert run.call_args.kwargs["cwd"] == state_dir
        assert state_dir.is_dir()

    def test_pip_venv_parses_pip_index_versions(self, tmp_path: Path) -> None:
        stdout = "buvis-gems (0.14.1)\nAvailable versions: 0.14.1, 0.14.0, 0.13.0\n"
        run = MagicMock(return_value=MagicMock(returncode=0, stdout=stdout))

        version, mock_pypi = _lookup("pip-venv", tmp_path, run)

        assert version == "0.14.1"
        mock_pypi.assert_not_called()
        assert run.call_args.args[0] == ("pip", "index", "versions", "buvis-gems")
        assert run.call_args.kwargs["cwd"] == tmp_path

    @pytest.mark.parametrize("method", ["uv-tool", "uv-venv"])
    def test_uv_uses_pip_compile_no_deps(self, method: str, tmp_path: Path) -> None:
        run = MagicMock(return_value=MagicMock(returncode=0, stdout="buvis-gems==0.14.1\n"))

        version, mock_pypi = _lookup(method, tmp_path, run)

        assert version == "0.14.1"
        mock_pypi.assert_not_called()
        assert run.call_args.args[0] == ("uv", "pip", "compile", "--no-deps", "--no-header", "--quiet", "-")
        assert run.call_args.kwargs["input"] == "buvis-gems"
        assert run.call_args.kwargs["cwd"] == tmp_path


class TestPypiFallback:
    @pytest.mark.parametrize("method", ["pipx", "unknown"])
    def test_pipx_and_unknown_fall_back_to_pypi(self, method: str, tmp_path: Path) -> None:
        run = MagicMock()

        version, mock_pypi = _lookup(method, tmp_path, run)

        assert version == _PYPI
        mock_pypi.assert_called_once()
        run.assert_not_called()

    @pytest.mark.parametrize(
        ("method", "outcome"),
        [
            ("mise-pipx", MagicMock(returncode=1, stdout="0.13.0\n")),
            ("mise-pipx", subprocess.TimeoutExpired(cmd="mise", timeout=10)),
            ("mise-pipx", FileNotFoundError("mise")),
            ("mise-pipx", MagicMock(returncode=0, stdout="not a version\n")),
            ("mise-pipx", MagicMock(returncode=0, stdout="")),
            ("pip-venv", MagicMock(returncode=0, stdout="WARNING: no such option\n")),
            ("uv-tool", MagicMock(returncode=0, stdout="other-pkg==1.0\n")),
        ],
        ids=["nonzero-exit", "timeout", "oserror", "garbage", "empty", "pip-parse-miss", "uv-parse-miss"],
    )
    def test_query_failure_falls_back_to_pypi(self, method: str, outcome: object, tmp_path: Path) -> None:
        run = MagicMock(side_effect=outcome) if isinstance(outcome, BaseException) else MagicMock(return_value=outcome)

        version, mock_pypi = _lookup(method, tmp_path, run)

        assert version == _PYPI
        mock_pypi.assert_called_once()
