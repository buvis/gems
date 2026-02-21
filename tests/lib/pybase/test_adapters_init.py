from __future__ import annotations

import pytest


class TestAdaptersLazyImports:
    def test_import_jira_adapter(self) -> None:
        from buvis.pybase.adapters import JiraAdapter

        assert JiraAdapter is not None

    def test_import_shell_adapter(self) -> None:
        from buvis.pybase.adapters import ShellAdapter

        assert ShellAdapter is not None

    def test_import_uv_adapter(self) -> None:
        from buvis.pybase.adapters import UvAdapter

        assert UvAdapter is not None

    def test_import_uv_tool_manager(self) -> None:
        from buvis.pybase.adapters import UvToolManager

        assert UvToolManager is not None

    def test_import_unknown_raises(self) -> None:
        with pytest.raises(AttributeError, match="has no attribute"):
            from buvis.pybase import adapters

            adapters.__getattr__("NonExistentAdapter")

    def test_import_console(self) -> None:
        from buvis.pybase.adapters import console

        assert console is not None
