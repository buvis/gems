from __future__ import annotations

import os
import sys

import pytest

# Snapshot tests render SVG via Rich/Textual and are sensitive to OS-specific
# glyph metrics and font handling. Baselines are generated in one canonical
# environment (Linux + Python 3.12) via the `update-snapshots` GitHub workflow.
# Everywhere else, snapshot tests are skipped to keep the matrix green.
SNAPSHOT_CANONICAL_PYTHON = (3, 12)
SNAPSHOT_CANONICAL_PLATFORM = "linux"


def _snapshot_env_is_canonical() -> bool:
    if os.environ.get("BUVIS_SNAPSHOT_CANONICAL") == "1":
        return True
    return sys.platform.startswith(SNAPSHOT_CANONICAL_PLATFORM) and sys.version_info[:2] == SNAPSHOT_CANONICAL_PYTHON


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-apply tool/lib markers by path and gate snapshot tests to canonical env."""
    canonical = _snapshot_env_is_canonical()
    skip_snapshot = pytest.mark.skip(
        reason=(
            f"snapshot baselines are canonical on {SNAPSHOT_CANONICAL_PLATFORM} + "
            f"Python {SNAPSHOT_CANONICAL_PYTHON[0]}.{SNAPSHOT_CANONICAL_PYTHON[1]}; "
            "run the update-snapshots workflow to regenerate"
        ),
    )
    for item in items:
        rel = item.path.as_posix()
        if "/tests/tools/" in rel:
            parts = rel.split("/tests/tools/")[1].split("/")
            if parts:
                tool_name = parts[0]
                item.add_marker(getattr(pytest.mark, tool_name))
        elif "/tests/lib/" in rel:
            item.add_marker(pytest.mark.lib)

        if not canonical and "snapshot" in item.keywords:
            item.add_marker(skip_snapshot)
