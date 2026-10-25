"""The custom hatch build hook: editable installs must not touch committed frontend output."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

if importlib.util.find_spec("hatchling") is None:
    # hatchling is a build requirement, not a test dependency: stand in for the
    # two attributes the hook reads from its base class.
    class _BuildHookInterface:
        def __init__(self, root, config, build_config, metadata, directory, target_name, app=None) -> None:
            self.root = root
            self.target_name = target_name

    for _name in ("hatchling", "hatchling.builders", "hatchling.builders.hooks", "hatchling.builders.hooks.plugin"):
        sys.modules.setdefault(_name, types.ModuleType(_name))
    _interface = types.ModuleType("hatchling.builders.hooks.plugin.interface")
    _interface.BuildHookInterface = _BuildHookInterface
    sys.modules["hatchling.builders.hooks.plugin.interface"] = _interface

_script = Path(__file__).resolve().parents[2] / "hatch_build.py"
_spec = importlib.util.spec_from_file_location("hatch_build", _script)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["hatch_build"] = _mod
_spec.loader.exec_module(_mod)

RustBuildHook = _mod.RustBuildHook

BIM_FRONTEND = Path("src/tools/bim/commands/serve/frontend")
POSTUP_FRONTEND = Path("src/tools/postup/adapters/web/frontend")


def _hook(root: Path, target_name: str = "wheel") -> object:
    return RustBuildHook(str(root), {}, None, None, str(root), target_name)


class TestEditableInstallsLeaveCommittedFrontendAlone:
    """Every ``uv sync`` builds an editable wheel; rebuilding postup's committed
    ``build/`` there dirties the tree whenever the npm toolchain drifts."""

    @pytest.mark.parametrize(
        ("version", "expected"),
        [("editable", [BIM_FRONTEND]), ("standard", [BIM_FRONTEND, POSTUP_FRONTEND])],
    )
    def test_editable_builds_skip_frontends_served_from_a_committed_build(
        self, mocker, monkeypatch, tmp_path: Path, version: str, expected: list[Path]
    ) -> None:
        monkeypatch.delenv("BUVIS_SKIP_FRONTEND", raising=False)
        mocker.patch.object(_mod.shutil, "which", return_value="/bin/npm")
        mocker.patch.object(RustBuildHook, "_build_rust")
        one = mocker.patch.object(RustBuildHook, "_build_one_frontend")
        build_data: dict = {}

        _hook(tmp_path).initialize(version, build_data)

        assert [call.args[1] for call in one.call_args_list] == [tmp_path / path for path in expected]
        assert build_data == {"infer_tag": True, "pure_python": False}

    def test_skip_env_still_silences_every_frontend_on_release_wheels(
        self, mocker, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("BUVIS_SKIP_FRONTEND", "1")
        mocker.patch.object(_mod.shutil, "which", return_value="/bin/npm")
        mocker.patch.object(RustBuildHook, "_build_rust")
        one = mocker.patch.object(RustBuildHook, "_build_one_frontend")

        _hook(tmp_path).initialize("standard", {})

        one.assert_not_called()

    def test_non_wheel_targets_build_nothing(self, mocker, tmp_path: Path) -> None:
        rust = mocker.patch.object(RustBuildHook, "_build_rust")
        one = mocker.patch.object(RustBuildHook, "_build_one_frontend")

        _hook(tmp_path, target_name="sdist").initialize("standard", {})

        rust.assert_not_called()
        one.assert_not_called()
