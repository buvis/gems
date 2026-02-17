from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# dev/scaffold.py is not a package — load directly
_spec = importlib.util.spec_from_file_location(
    "scaffold", Path(__file__).resolve().parents[2] / "dev" / "scaffold.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["scaffold"] = _mod
_spec.loader.exec_module(_mod)

_to_snake = _mod._to_snake
_to_pascal = _mod._to_pascal
_to_kebab = _mod._to_kebab
scaffold = _mod.scaffold


class TestNameConversions:
    @pytest.mark.parametrize(
        ("input_name", "expected"),
        [
            ("my-tool", "my_tool"),
            ("MyTool", "mytool"),
            ("my_tool", "my_tool"),
            ("hello-world", "hello_world"),
            ("FOO", "foo"),
        ],
    )
    def test_to_snake(self, input_name: str, expected: str) -> None:
        assert _to_snake(input_name) == expected

    @pytest.mark.parametrize(
        ("input_name", "expected"),
        [
            ("my-tool", "MyTool"),
            ("my_tool", "MyTool"),
            ("hello-world", "HelloWorld"),
            ("foo", "Foo"),
        ],
    )
    def test_to_pascal(self, input_name: str, expected: str) -> None:
        assert _to_pascal(input_name) == expected

    @pytest.mark.parametrize(
        ("input_name", "expected"),
        [
            ("my_tool", "my-tool"),
            ("hello_world", "hello-world"),
            ("foo", "foo"),
        ],
    )
    def test_to_kebab(self, input_name: str, expected: str) -> None:
        assert _to_kebab(input_name) == expected


class TestScaffold:
    def test_creates_simple_tool(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        scaffold("my-app", "Test tool")

        tool_dir = tmp_path / "src" / "tools" / "my_app"
        assert (tool_dir / "__init__.py").is_file()
        assert (tool_dir / "__main__.py").is_file()
        assert (tool_dir / "cli.py").is_file()
        assert (tool_dir / "settings.py").is_file()
        assert (tool_dir / "manifest.toml").is_file()
        assert (tool_dir / "commands" / "example.py").is_file()
        assert (tool_dir / "params" / "example.py").is_file()
        assert not (tool_dir / "adapters").exists()

        test_dir = tmp_path / "tests" / "tools" / "my_app"
        assert (test_dir / "test_cli.py").is_file()

    def test_creates_multi_interface_tool(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        scaffold("my-app", "Test tool", multi_interface=True)

        tool_dir = tmp_path / "src" / "tools" / "my_app"
        assert (tool_dir / "adapters" / "cli.py").is_file()
        assert not (tool_dir / "cli.py").exists()

    def test_raises_if_dir_exists(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src" / "tools" / "my_app").mkdir(parents=True)

        with pytest.raises(FileExistsError):
            scaffold("my-app", "Test tool")

    def test_generated_manifest_has_correct_name(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        scaffold("my-app", "Test tool")

        manifest = (tmp_path / "src" / "tools" / "my_app" / "manifest.toml").read_text()
        assert 'name = "my-app"' in manifest
        assert 'module_name = "my_app"' in manifest
        assert 'display_name = "MyApp"' in manifest

    def test_generated_settings_has_env_prefix(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        scaffold("my-app", "Test tool")

        settings = (tmp_path / "src" / "tools" / "my_app" / "settings.py").read_text()
        assert 'env_prefix="BUVIS_MY_APP_"' in settings
        assert "class MyAppSettings" in settings
