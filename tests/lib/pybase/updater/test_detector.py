"""Tests for installer detection."""

from __future__ import annotations

from pathlib import PurePosixPath
from unittest.mock import MagicMock, patch

from buvis.pybase.updater.detector import detect_installer


class TestDetectInstallerOverride:
    def test_override_uv_tool(self) -> None:
        result = detect_installer(override="uv-tool")
        assert result.method == "uv-tool"
        assert result.upgrade_command == ("uv", "tool", "upgrade", "buvis-gems")

    def test_override_pipx(self) -> None:
        result = detect_installer(override="pipx")
        assert result.method == "pipx"
        assert result.upgrade_command == ("pipx", "upgrade", "buvis-gems")

    def test_override_pip(self) -> None:
        result = detect_installer(override="pip")
        assert result.method == "pip-venv"
        assert result.upgrade_command == ("pip", "install", "--upgrade", "buvis-gems")

    def test_override_uv(self) -> None:
        result = detect_installer(override="uv")
        assert result.method == "uv-venv"
        assert result.upgrade_command == ("uv", "pip", "install", "--upgrade", "buvis-gems")

    def test_override_unknown_value_returns_unknown(self) -> None:
        result = detect_installer(override="homebrew")
        assert result.method == "unknown"
        assert result.upgrade_command is None


class TestDetectInstallerUvTool:
    def test_uv_tool_detected_from_path(self) -> None:
        dist = MagicMock()
        dist.read_text.return_value = "uv\n"
        dist._path = PurePosixPath(
            "/home/user/.local/share/uv/tools/buvis-gems/lib/python3.12/site-packages/buvis_gems-0.7.0.dist-info"
        )

        with patch("buvis.pybase.updater.detector.distribution", return_value=dist):
            result = detect_installer(override=None)

        assert result.method == "uv-tool"
        assert result.upgrade_command == ("uv", "tool", "upgrade", "buvis-gems")


class TestDetectInstallerMisePipx:
    def test_mise_pipx_detected_from_path(self) -> None:
        dist = MagicMock()
        dist.read_text.return_value = "uv\n"
        dist._path = PurePosixPath(
            "/home/user/.local/share/mise/installs/pipx-buvis-gems/0.8.0/buvis-gems/lib/python3.12/site-packages/buvis_gems-0.8.0.dist-info"
        )

        with patch("buvis.pybase.updater.detector.distribution", return_value=dist):
            result = detect_installer(override=None)

        assert result.method == "mise-pipx"
        assert result.upgrade_command == ("mise", "upgrade", "pipx:buvis-gems")

    def test_override_mise_pipx(self) -> None:
        result = detect_installer(override="mise-pipx")
        assert result.method == "mise-pipx"
        assert result.upgrade_command == ("mise", "upgrade", "pipx:buvis-gems")


class TestDetectInstallerPipx:
    def test_pipx_detected_from_path(self) -> None:
        dist = MagicMock()
        dist.read_text.return_value = "pip\n"
        dist._path = PurePosixPath(
            "/home/user/.local/pipx/venvs/buvis-gems/lib/python3.12/site-packages/buvis_gems-0.7.0.dist-info"
        )

        with patch("buvis.pybase.updater.detector.distribution", return_value=dist):
            result = detect_installer(override=None)

        assert result.method == "pipx"
        assert result.upgrade_command == ("pipx", "upgrade", "buvis-gems")


class TestDetectInstallerVenv:
    def test_pip_in_venv(self) -> None:
        dist = MagicMock()
        dist.read_text.return_value = "pip\n"
        dist._path = PurePosixPath("/home/user/project/.venv/lib/python3.12/site-packages/buvis_gems-0.7.0.dist-info")

        with (
            patch("buvis.pybase.updater.detector.distribution", return_value=dist),
            patch("buvis.pybase.updater.detector.sys") as mock_sys,
        ):
            mock_sys.prefix = "/home/user/project/.venv"
            mock_sys.base_prefix = "/usr"
            result = detect_installer(override=None)

        assert result.method == "pip-venv"
        assert result.upgrade_command == ("pip", "install", "--upgrade", "buvis-gems")

    def test_uv_in_venv(self) -> None:
        dist = MagicMock()
        dist.read_text.return_value = "uv\n"
        dist._path = PurePosixPath("/home/user/project/.venv/lib/python3.12/site-packages/buvis_gems-0.7.0.dist-info")

        with (
            patch("buvis.pybase.updater.detector.distribution", return_value=dist),
            patch("buvis.pybase.updater.detector.sys") as mock_sys,
        ):
            mock_sys.prefix = "/home/user/project/.venv"
            mock_sys.base_prefix = "/usr"
            result = detect_installer(override=None)

        assert result.method == "uv-venv"
        assert result.upgrade_command == ("uv", "pip", "install", "--upgrade", "buvis-gems")


class TestDetectInstallerUnknown:
    def test_unknown_when_no_heuristic_matches(self) -> None:
        dist = MagicMock()
        dist.read_text.return_value = "pip\n"
        dist._path = PurePosixPath("/usr/lib/python3.12/site-packages/buvis_gems-0.7.0.dist-info")

        with (
            patch("buvis.pybase.updater.detector.distribution", return_value=dist),
            patch("buvis.pybase.updater.detector.sys") as mock_sys,
        ):
            mock_sys.prefix = "/usr"
            mock_sys.base_prefix = "/usr"
            result = detect_installer(override=None)

        assert result.method == "unknown"
        assert result.upgrade_command is None

    def test_unknown_when_installer_file_missing(self) -> None:
        dist = MagicMock()
        dist.read_text.return_value = None
        dist._path = PurePosixPath("/usr/lib/python3.12/site-packages/buvis_gems-0.7.0.dist-info")

        with (
            patch("buvis.pybase.updater.detector.distribution", return_value=dist),
            patch("buvis.pybase.updater.detector.sys") as mock_sys,
        ):
            mock_sys.prefix = "/usr"
            mock_sys.base_prefix = "/usr"
            result = detect_installer(override=None)

        assert result.method == "unknown"

    def test_unknown_when_distribution_not_found(self) -> None:
        with patch(
            "buvis.pybase.updater.detector.distribution",
            side_effect=Exception("not found"),
        ):
            result = detect_installer(override=None)

        assert result.method == "unknown"
        assert result.upgrade_command is None
