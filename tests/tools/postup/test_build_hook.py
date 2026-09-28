"""Tests for the ``hatch_build.py`` custom build hook's frontend step.

Covers the PRD 00067 Phase 2 generalization: ``_build_frontend`` must build
BOTH tool frontends (bim and postup), honor ``BUVIS_SKIP_FRONTEND``, copy bim's
``build/`` into its packaged ``static/``, and leave postup's committed
``build/`` in place (no static copy).

``hatch_build.py`` lives at the repo root (off the import path) and imports
``hatchling`` at module top — a build-backend package that is not installed in
the test environment. A minimal ``BuildHookInterface`` stub is injected into
``sys.modules`` before the module is loaded by file path, so the real
``_build_frontend`` / ``_build_one_frontend`` logic runs unchanged.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.lib

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _install_hatchling_stub() -> None:
    """Register a minimal ``hatchling`` package exposing ``BuildHookInterface``."""
    if "hatchling.builders.hooks.plugin.interface" in sys.modules:
        return

    class _StubBuildHookInterface:
        PLUGIN_NAME = ""

        def __init__(self) -> None:  # pragma: no cover - never called in tests
            self.root = ""

    for name in (
        "hatchling",
        "hatchling.builders",
        "hatchling.builders.hooks",
        "hatchling.builders.hooks.plugin",
        "hatchling.builders.hooks.plugin.interface",
    ):
        sys.modules.setdefault(name, ModuleType(name))
    sys.modules["hatchling.builders.hooks.plugin.interface"].BuildHookInterface = _StubBuildHookInterface


def _load_hatch_build() -> ModuleType:
    _install_hatchling_stub()
    spec = importlib.util.spec_from_file_location("hatch_build_under_test", _REPO_ROOT / "hatch_build.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_hook(module: ModuleType, root: Path) -> object:
    hook = module.RustBuildHook.__new__(module.RustBuildHook)
    hook.root = str(root)
    return hook


def _scaffold_two_frontends(root: Path) -> tuple[Path, Path]:
    bim_fe = root / "src/tools/bim/commands/serve/frontend"
    postup_fe = root / "src/tools/postup/adapters/web/frontend"
    for fe in (bim_fe, postup_fe):
        fe.mkdir(parents=True)
        (fe / "package.json").write_text("{}", encoding="utf-8")
        (fe / "build").mkdir()
        (fe / "build" / "index.html").write_text("<html></html>", encoding="utf-8")
    return bim_fe, postup_fe


class TestBuildFrontend:
    def test_builds_both_tool_frontends(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        module = _load_hatch_build()
        monkeypatch.delenv("BUVIS_SKIP_FRONTEND", raising=False)
        bim_fe, postup_fe = _scaffold_two_frontends(tmp_path)
        hook = _make_hook(module, tmp_path)

        with (
            patch.object(module.shutil, "which", return_value="/usr/bin/npm"),
            patch.object(module.subprocess, "run") as mock_run,
            patch.object(module.shutil, "copytree") as mock_copytree,
            patch.object(module.shutil, "rmtree"),
        ):
            hook._build_frontend()

        built_dirs = {str(call.kwargs["cwd"]) for call in mock_run.call_args_list}
        assert str(bim_fe) in built_dirs
        assert str(postup_fe) in built_dirs
        # npm ci + npm run build for each of the two frontends.
        assert mock_run.call_count == 4

        # bim copies build/ -> static/; postup does NOT (served in place).
        copied_sources = {str(call.args[0]) for call in mock_copytree.call_args_list}
        assert str(bim_fe / "build") in copied_sources
        assert str(postup_fe / "build") not in copied_sources

    def test_skip_env_var_builds_nothing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        module = _load_hatch_build()
        monkeypatch.setenv("BUVIS_SKIP_FRONTEND", "1")
        _scaffold_two_frontends(tmp_path)
        hook = _make_hook(module, tmp_path)

        with (
            patch.object(module.shutil, "which", return_value="/usr/bin/npm"),
            patch.object(module.subprocess, "run") as mock_run,
        ):
            hook._build_frontend()

        mock_run.assert_not_called()

    def test_missing_npm_builds_nothing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        module = _load_hatch_build()
        monkeypatch.delenv("BUVIS_SKIP_FRONTEND", raising=False)
        _scaffold_two_frontends(tmp_path)
        hook = _make_hook(module, tmp_path)

        with (
            patch.object(module.shutil, "which", return_value=None),
            patch.object(module.subprocess, "run") as mock_run,
        ):
            hook._build_frontend()

        mock_run.assert_not_called()

    def test_frontend_without_package_json_is_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        module = _load_hatch_build()
        monkeypatch.delenv("BUVIS_SKIP_FRONTEND", raising=False)
        # Only postup gets a package.json; bim's frontend dir is absent entirely.
        postup_fe = tmp_path / "src/tools/postup/adapters/web/frontend"
        postup_fe.mkdir(parents=True)
        (postup_fe / "package.json").write_text("{}", encoding="utf-8")
        (postup_fe / "build").mkdir()
        hook = _make_hook(module, tmp_path)

        with (
            patch.object(module.shutil, "which", return_value="/usr/bin/npm"),
            patch.object(module.subprocess, "run") as mock_run,
        ):
            hook._build_frontend()

        built_dirs = {str(call.kwargs["cwd"]) for call in mock_run.call_args_list}
        assert built_dirs == {str(postup_fe)}
