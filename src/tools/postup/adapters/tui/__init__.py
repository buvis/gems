"""Postup Textual TUI adapter.

Imports Textual — available only with the ``postup`` extra. The CLI catches the
``ImportError`` and renders install guidance, so this package is never imported
on the core-only text-brief path.
"""

from __future__ import annotations

from postup.adapters.tui.app import PostupApp

__all__ = ["PostupApp"]
