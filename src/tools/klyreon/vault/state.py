"""Vault state in ``$XDG_STATE_HOME/klyreon/state.json`` (staleness tracking).

v1 reads ``last_maintain`` for the staleness warning. The write path is here
too (atomic) so PRD D can stamp ``last_maintain`` without adding a module;
nothing in v1 writes it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from buvis.pybase.filesystem import atomic_write_text

__all__ = ["read_state", "state_path", "write_state"]


def state_path() -> Path:
    """Return the state file path, honouring ``$XDG_STATE_HOME``."""
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "klyreon" / "state.json"


def read_state() -> dict[str, Any]:
    """Return the parsed state mapping, or an empty dict when absent/unreadable."""
    path = state_path()
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def write_state(state: dict[str, Any]) -> None:
    """Write ``state`` to the state file atomically, creating parents."""
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(state, indent=2, sort_keys=True) + "\n")
