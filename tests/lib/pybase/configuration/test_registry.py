from __future__ import annotations

from importlib.metadata import EntryPoint
from pathlib import Path

import pytest
import tomllib
from buvis.pybase.configuration.registry import CONFIG_SETTINGS_ENTRY_POINT_GROUP, known_tool_names

_PYPROJECT = Path(__file__).resolve().parents[4] / "pyproject.toml"


def _fake_entry_point(name: str) -> EntryPoint:
    return EntryPoint(name=name, value="unused.module:Unused", group="buvis.config_settings")


@pytest.fixture(autouse=True)
def _clear_known_tool_names_cache():
    known_tool_names.cache_clear()
    yield
    known_tool_names.cache_clear()


class TestKnownToolNames:
    def test_returns_exactly_the_registered_names(self, monkeypatch):
        known_tool_names.cache_clear()
        fixture = (_fake_entry_point("alpha"), _fake_entry_point("beta"))
        monkeypatch.setattr(
            "buvis.pybase.configuration.registry.entry_points",
            lambda group: fixture,
        )
        assert known_tool_names() == frozenset({"alpha", "beta"})

    def test_never_loads_an_entry_point(self, monkeypatch):
        known_tool_names.cache_clear()

        class ExplodingEntryPoint:
            name = "exploding"

            def load(self):
                raise AssertionError("known_tool_names must never call .load()")

        monkeypatch.setattr(
            "buvis.pybase.configuration.registry.entry_points",
            lambda group: (ExplodingEntryPoint(),),
        )
        assert known_tool_names() == frozenset({"exploding"})

    def test_result_is_cached_until_cleared(self, monkeypatch):
        known_tool_names.cache_clear()
        monkeypatch.setattr(
            "buvis.pybase.configuration.registry.entry_points",
            lambda group: (_fake_entry_point("gamma"),),
        )
        first = known_tool_names()

        monkeypatch.setattr(
            "buvis.pybase.configuration.registry.entry_points",
            lambda group: (_fake_entry_point("delta"),),
        )
        assert known_tool_names() == first  # still cached, not re-queried

        known_tool_names.cache_clear()
        assert known_tool_names() == frozenset({"delta"})


class TestRealEntryPointWiring:
    """No monkeypatching: every declared tool must actually be discoverable."""

    def test_matches_declared_config_settings_entry_points(self):
        declared = set(
            tomllib.loads(_PYPROJECT.read_text())["project"]["entry-points"][CONFIG_SETTINGS_ENTRY_POINT_GROUP]
        )
        assert known_tool_names() == frozenset(declared)
