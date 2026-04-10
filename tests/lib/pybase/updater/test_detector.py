"""Tests for installer detection."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from pathlib import PurePosixPath
from unittest.mock import MagicMock, patch

from buvis.pybase.updater.detector import _installed_extras, detect_installer


def _no_extras():
    return patch("buvis.pybase.updater.detector._installed_extras", return_value=())


class TestDetectInstallerOverride:
    def test_override_uv_tool(self) -> None:
        with _no_extras():
            result = detect_installer(override="uv-tool")
        assert result.method == "uv-tool"
        assert result.upgrade_command == ("uv", "tool", "upgrade", "buvis-gems")

    def test_override_pipx(self) -> None:
        with _no_extras():
            result = detect_installer(override="pipx")
        assert result.method == "pipx"
        assert result.upgrade_command == ("pipx", "upgrade", "buvis-gems")

    def test_override_pip(self) -> None:
        with _no_extras():
            result = detect_installer(override="pip")
        assert result.method == "pip-venv"
        assert result.upgrade_command == ("pip", "install", "--upgrade", "buvis-gems")

    def test_override_uv(self) -> None:
        with _no_extras():
            result = detect_installer(override="uv")
        assert result.method == "uv-venv"
        assert result.upgrade_command == ("uv", "pip", "install", "--upgrade", "buvis-gems")

    def test_override_unknown_value_returns_unknown(self) -> None:
        with _no_extras():
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

        with (
            patch("buvis.pybase.updater.detector.distribution", return_value=dist),
            _no_extras(),
        ):
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

        with (
            patch("buvis.pybase.updater.detector.distribution", return_value=dist),
            _no_extras(),
        ):
            result = detect_installer(override=None)

        assert result.method == "mise-pipx"
        assert result.upgrade_command == ("mise", "upgrade", "pipx:buvis-gems")

    def test_override_mise_pipx(self) -> None:
        with _no_extras():
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

        with (
            patch("buvis.pybase.updater.detector.distribution", return_value=dist),
            _no_extras(),
        ):
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
            _no_extras(),
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
            _no_extras(),
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
            _no_extras(),
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
            _no_extras(),
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


class TestPipVenvUpgradeIncludesExtras:
    def test_pip_venv_appends_detected_extras(self) -> None:
        """pip install --upgrade drops extras unless they are re-specified."""
        with patch("buvis.pybase.updater.detector._installed_extras", return_value=("dot", "bim")):
            result = detect_installer(override="pip")
        assert result.upgrade_command == ("pip", "install", "--upgrade", "buvis-gems[dot,bim]")

    def test_uv_venv_appends_detected_extras(self) -> None:
        """uv pip install --upgrade drops extras unless they are re-specified."""
        with patch("buvis.pybase.updater.detector._installed_extras", return_value=("all",)):
            result = detect_installer(override="uv")
        assert result.upgrade_command == ("uv", "pip", "install", "--upgrade", "buvis-gems[all]")

    def test_pip_venv_detected_from_path_includes_extras(self) -> None:
        dist = MagicMock()
        dist.read_text.return_value = "pip\n"
        dist._path = PurePosixPath("/home/user/project/.venv/lib/python3.12/site-packages/buvis_gems-0.7.0.dist-info")

        with (
            patch("buvis.pybase.updater.detector.distribution", return_value=dist),
            patch("buvis.pybase.updater.detector.sys") as mock_sys,
            patch("buvis.pybase.updater.detector._installed_extras", return_value=("all",)),
        ):
            mock_sys.prefix = "/home/user/project/.venv"
            mock_sys.base_prefix = "/usr"
            result = detect_installer(override=None)

        assert result.method == "pip-venv"
        assert result.upgrade_command == ("pip", "install", "--upgrade", "buvis-gems[all]")


class TestStaticInstallersIgnoreExtras:
    """uv-tool / pipx / mise-pipx track extras internally; command stays static."""

    def test_uv_tool_command_unchanged_with_extras(self) -> None:
        with patch("buvis.pybase.updater.detector._installed_extras", return_value=("dot",)):
            result = detect_installer(override="uv-tool")
        assert result.upgrade_command == ("uv", "tool", "upgrade", "buvis-gems")

    def test_pipx_command_unchanged_with_extras(self) -> None:
        with patch("buvis.pybase.updater.detector._installed_extras", return_value=("dot",)):
            result = detect_installer(override="pipx")
        assert result.upgrade_command == ("pipx", "upgrade", "buvis-gems")

    def test_mise_pipx_command_unchanged_with_extras(self) -> None:
        with patch("buvis.pybase.updater.detector._installed_extras", return_value=("all",)):
            result = detect_installer(override="mise-pipx")
        assert result.upgrade_command == ("mise", "upgrade", "pipx:buvis-gems")


class TestInstalledExtras:
    def _dist(self, provides_extra, requires):
        dist = MagicMock()
        dist.metadata.get_all.return_value = list(provides_extra)
        dist.requires = list(requires)
        return dist

    def test_returns_empty_when_distribution_missing(self) -> None:
        with patch(
            "buvis.pybase.updater.detector.distribution",
            side_effect=PackageNotFoundError("buvis-gems"),
        ):
            assert _installed_extras("buvis-gems") == ()

    def test_returns_empty_when_no_provides_extra(self) -> None:
        dist = self._dist(provides_extra=[], requires=["click==8"])
        with patch("buvis.pybase.updater.detector.distribution", return_value=dist):
            assert _installed_extras("buvis-gems") == ()

    def test_detects_extras_whose_deps_are_installed(self) -> None:
        dist = self._dist(
            provides_extra=["dot", "bim", "fren"],
            requires=[
                "click==8",
                "textual==8.2.3; extra == 'dot'",
                "jira==3.10.5; extra == 'bim'",
                "textual==8.2.3; extra == 'bim'",
                "python-slugify==8.0.4; extra == 'fren'",
            ],
        )

        def fake_distribution(name: str):
            if name == "buvis-gems":
                return dist
            if name in {"textual", "jira"}:
                return MagicMock()
            raise PackageNotFoundError(name)

        with patch(
            "buvis.pybase.updater.detector.distribution",
            side_effect=fake_distribution,
        ):
            result = _installed_extras("buvis-gems")

        assert result == ("dot", "bim")

    def test_skips_extras_with_no_tagged_requirements(self) -> None:
        dist = self._dist(
            provides_extra=["dot", "empty"],
            requires=["textual; extra == 'dot'"],
        )
        with patch(
            "buvis.pybase.updater.detector.distribution",
            side_effect=lambda name: dist if name == "buvis-gems" else MagicMock(),
        ):
            assert _installed_extras("buvis-gems") == ("dot",)

    def test_preserves_declaration_order(self) -> None:
        dist = self._dist(
            provides_extra=["zeta", "alpha", "mu"],
            requires=[
                "pkg_a; extra == 'alpha'",
                "pkg_m; extra == 'mu'",
                "pkg_z; extra == 'zeta'",
            ],
        )
        with patch(
            "buvis.pybase.updater.detector.distribution",
            side_effect=lambda name: dist if name == "buvis-gems" else MagicMock(),
        ):
            assert _installed_extras("buvis-gems") == ("zeta", "alpha", "mu")
