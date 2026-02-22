from __future__ import annotations

import importlib.resources
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock, patch

from buvis.pybase.manifest import discover_tools_installed


class TestDiscoverToolsInstalled:
    def test_discovers_installed_tool(self, tmp_path: Path) -> None:
        content = dedent("""\
            [tool]
            name = "hello"
            display_name = "Hello"
            module_name = "hello_world"
            description = "Hello world tool"
            category = "sample"
        """)
        toml_path = tmp_path / "manifest.toml"
        toml_path.write_text(content)

        mock_ref = MagicMock()
        with (
            patch.object(importlib.resources, "files") as mock_files,
            patch.object(importlib.resources, "as_file") as mock_as_file,
        ):
            mock_files.return_value.__truediv__ = MagicMock(return_value=mock_ref)
            mock_as_file.return_value.__enter__ = MagicMock(return_value=toml_path)
            mock_as_file.return_value.__exit__ = MagicMock(return_value=False)

            manifests = discover_tools_installed(["hello_world"])

        assert len(manifests) == 1
        assert manifests[0].name == "hello"

    def test_skips_missing_packages(self) -> None:
        manifests = discover_tools_installed(["nonexistent_package_xyz"])
        assert manifests == []
