"""Cross-tool name discovery for the shared config-file typo check.

Discovers every installed tool's *name* through the
``buvis.config_settings`` entry-point group, never by importing a tool
package - see AGENTS.md "the library stays interface-agnostic". A tool's
name is the ``<tool>:`` namespace key a shared config file may legitimately
carry for it (``docs/source/configuration.rst`` "Tool-Specific Configuration
Files"); this module answers only "is this a registered tool name", nothing
about any tool's own fields.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import entry_points

__all__ = ["CONFIG_SETTINGS_ENTRY_POINT_GROUP", "known_tool_names"]

CONFIG_SETTINGS_ENTRY_POINT_GROUP = "buvis.config_settings"


@lru_cache(maxsize=1)
def known_tool_names() -> frozenset[str]:
    """Every registered tool's entry-point name.

    Reads only ``EntryPoint.name`` - never calls ``.load()`` - so this
    function imports no tool code at all, not even optionally; it is pure
    distribution metadata lookup. A shared config file's ``<tool>:``
    section for a tool missing from this set (uninstalled extra, not yet
    registered) is indistinguishable from a genuine typo and surfaces as a
    noisy warning rather than silence - accepted, not solved, by this
    design.

    Cached for the lifetime of the process: ``entry_points(group=...)``
    re-parses every installed distribution's metadata on each call, and
    ``_load_yaml`` calls this once per ``resolve()`` call, which runs on
    every CLI invocation of every tool. Uncached, this adds a
    cross-distribution metadata scan to the hot path of every tool command
    that touches ``config.yaml``/``buvis.yaml``. Tests that need a fresh
    set after monkeypatching ``entry_points`` call
    ``known_tool_names.cache_clear()`` first.
    """
    return frozenset(ep.name for ep in entry_points(group=CONFIG_SETTINGS_ENTRY_POINT_GROUP))
