from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from buvis.pybase.manifest import ToolManifest, discover_tools_dev


@pytest.fixture
def sample_toml(tmp_path: Path) -> Path:
    content = dedent("""\
        [tool]
        name = "test-tool"
        display_name = "Test Tool"
        module_name = "test_tool"
        description = "A test tool"
        category = "testing"

        [tool.interfaces]
        cli = true
        rest = false

        [tool.commands]
        hello = "Say hello"

        [tool.requirements]
        python = ">=3.11"
    """)
    toml_path = tmp_path / "manifest.toml"
    toml_path.write_text(content)
    return toml_path


@pytest.fixture
def tools_dir(tmp_path: Path) -> Path:
    for name in ("alpha", "beta"):
        tool_dir = tmp_path / name
        tool_dir.mkdir()
        content = dedent(f"""\
            [tool]
            name = "{name}"
            display_name = "{name.title()}"
            module_name = "{name}"
            description = "Tool {name}"
            category = "test"

            [tool.interfaces]
            cli = true

            [tool.commands]
            run = "Run {name}"

            [tool.requirements]
            python = ">=3.11"
        """)
        (tool_dir / "manifest.toml").write_text(content)
    return tmp_path


class TestToolManifest:
    def test_from_toml_parses_fields(self, sample_toml: Path) -> None:
        m = ToolManifest.from_toml(sample_toml)

        assert m.name == "test-tool"
        assert m.display_name == "Test Tool"
        assert m.module_name == "test_tool"
        assert m.description == "A test tool"
        assert m.category == "testing"
        assert m.interfaces == {"cli": True, "rest": False}
        assert m.commands == {"hello": "Say hello"}
        assert m.requirements == {"python": ">=3.11"}

    def test_to_dict(self, sample_toml: Path) -> None:
        m = ToolManifest.from_toml(sample_toml)
        d = m.to_dict()

        assert d["name"] == "test-tool"
        assert isinstance(d, dict)

    def test_from_toml_missing_optional(self, tmp_path: Path) -> None:
        content = dedent("""\
            [tool]
            name = "minimal"
            display_name = "Minimal"
            module_name = "minimal"
            description = "Minimal tool"
        """)
        p = tmp_path / "manifest.toml"
        p.write_text(content)
        m = ToolManifest.from_toml(p)

        assert m.category == ""
        assert m.interfaces == {}
        assert m.commands == {}


class TestDiscoverToolsDev:
    def test_finds_all_manifests(self, tools_dir: Path) -> None:
        manifests = discover_tools_dev(tools_dir)

        assert len(manifests) == 2
        names = [m.name for m in manifests]
        assert "alpha" in names
        assert "beta" in names

    def test_empty_dir(self, tmp_path: Path) -> None:
        manifests = discover_tools_dev(tmp_path)
        assert manifests == []
