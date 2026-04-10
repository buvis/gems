"""State store for updater: cache + event log in a single JSON file."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_STATE_DIR",
    "STATE_FILE_NAME",
    "append_log",
    "read_cache",
    "write_cache",
]

DEFAULT_STATE_DIR = Path.home() / ".config" / "buvis"
STATE_FILE_NAME = "updater.json"
_MAX_LOG_ENTRIES = 100


def _state_path(state_dir: Path) -> Path:
    return state_dir / STATE_FILE_NAME


def _read_state(state_dir: Path) -> dict[str, Any]:
    """Read the full state file. Returns an empty dict on any error."""
    try:
        data = json.loads(_state_path(state_dir).read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(state_dir: Path, state: dict[str, Any]) -> None:
    """Write state file, silently ignoring errors."""
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        _state_path(state_dir).write_text(json.dumps(state, indent=2))
    except Exception:
        return


def read_cache(state_dir: Path) -> tuple[datetime | None, str | None]:
    """Read cached check timestamp and version. Returns (None, None) on any error."""
    state = _read_state(state_dir)
    last_check_str = state.get("last_check")
    latest_version = state.get("latest_version")
    if not isinstance(last_check_str, str) or not isinstance(latest_version, str):
        return None, None
    try:
        last_check = datetime.fromisoformat(last_check_str)
    except ValueError:
        return None, None
    if last_check.tzinfo is None:
        last_check = last_check.replace(tzinfo=timezone.utc)
    return last_check, latest_version


def write_cache(state_dir: Path, latest_version: str) -> None:
    """Update cache fields without touching the log."""
    state = _read_state(state_dir)
    state["last_check"] = datetime.now(tz=timezone.utc).isoformat()
    state["latest_version"] = latest_version
    _write_state(state_dir, state)


def append_log(state_dir: Path, level: str, message: str) -> None:
    """Append an event to the log, keeping only the most recent entries."""
    state = _read_state(state_dir)
    log_entries = state.get("log")
    if not isinstance(log_entries, list):
        log_entries = []
    log_entries.append(
        {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "level": level,
            "message": message,
        }
    )
    state["log"] = log_entries[-_MAX_LOG_ENTRIES:]
    _write_state(state_dir, state)
