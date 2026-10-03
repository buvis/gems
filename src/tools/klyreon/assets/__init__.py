"""Operator asset install, refresh, and manifest (PRD 00076).

The record (:mod:`klyreon.assets.manifest`), the operator table
(:mod:`klyreon.assets.registry`), and the hash-compare install/refresh/uninstall
engine (:mod:`klyreon.assets.installer`). Nothing here reads the vault: an
operator asset pack is installed into a home directory, and klyreon's own
autonomous loop never reads what it installed there.
"""

from __future__ import annotations

__all__: list[str] = []
