from __future__ import annotations

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-apply markers based on test file path."""
    for item in items:
        rel = item.path.as_posix()
        if "/tests/tools/" in rel:
            parts = rel.split("/tests/tools/")[1].split("/")
            if parts:
                tool_name = parts[0]
                item.add_marker(getattr(pytest.mark, tool_name))
        elif "/tests/lib/" in rel:
            item.add_marker(pytest.mark.lib)
