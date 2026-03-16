from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# dev/bin/scaffold.py is not a package — load directly
_script = Path(__file__).resolve().parents[2] / "dev" / "bin" / "scaffold.py"
_spec = importlib.util.spec_from_file_location("scaffold", _script)
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


MINIMAL_PYPROJECT = """\
[project.scripts]
alpha = "alpha.cli:cli"
zulu = "zulu.cli:cli"

[project.optional-dependencies]
alpha = ["some-dep>=1,<2"]
all = ["buvis-gems[alpha]"]

[tool.hatch.build.targets.wheel]
packages = [
  "src/lib/buvis",
  "src/tools/alpha",
  "src/tools/zulu",
]
"""


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


class TestScaffoldWiring:
    @pytest.fixture
    def repo(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text(MINIMAL_PYPROJECT)
        return tmp_path

    def test_adds_scripts_entry(self, repo) -> None:
        scaffold("my-app", "Test tool")
        text = (repo / "pyproject.toml").read_text()
        assert 'my-app = "my_app.cli:cli"' in text

    def test_adds_packages_entry(self, repo) -> None:
        scaffold("my-app", "Test tool")
        text = (repo / "pyproject.toml").read_text()
        assert '"src/tools/my_app",' in text

    def test_multi_interface_scripts_entry(self, repo) -> None:
        scaffold("my-app", "Test tool", multi_interface=True)
        text = (repo / "pyproject.toml").read_text()
        assert 'my-app = "my_app.adapters.cli:cli"' in text

    def test_entries_sorted_alphabetically(self, repo) -> None:
        scaffold("bravo", "B tool")
        text = (repo / "pyproject.toml").read_text()
        lines = text.splitlines()
        scripts_lines = []
        in_scripts = False
        for line in lines:
            if line.strip() == "[project.scripts]":
                in_scripts = True
                continue
            if in_scripts:
                if line.strip().startswith("["):
                    break
                if "=" in line:
                    scripts_lines.append(line.strip())
        keys = [entry.split("=")[0].strip() for entry in scripts_lines]
        assert keys == sorted(keys), f"scripts not sorted: {keys}"

    def test_extras_adds_optional_deps(self, repo) -> None:
        scaffold("my-app", "Test tool", extras=["requests>=2,<3"])
        text = (repo / "pyproject.toml").read_text()
        assert 'my-app = ["requests>=2,<3"]' in text

    def test_extras_updates_all(self, repo) -> None:
        scaffold("my-app", "Test tool", extras=["requests>=2,<3"])
        text = (repo / "pyproject.toml").read_text()
        all_line = next(line for line in text.splitlines() if line.strip().startswith("all = "))
        assert "my-app" in all_line

    def test_no_extras_skips_optional_deps(self, repo) -> None:
        scaffold("my-app", "Test tool")
        text = (repo / "pyproject.toml").read_text()
        assert "my-app = [" not in text
        # all extra unchanged
        all_line = next(line for line in text.splitlines() if line.strip().startswith("all = "))
        assert "my-app" not in all_line

    def test_no_pyproject_skips_wiring(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        scaffold("my-app", "Test tool")
        # Tool files still created
        assert (tmp_path / "src" / "tools" / "my_app" / "cli.py").is_file()
        # No pyproject.toml created
        assert not (tmp_path / "pyproject.toml").exists()
