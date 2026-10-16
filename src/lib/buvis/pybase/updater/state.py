"""State store for updater: caches, upgrade back-off and event log in a single JSON file."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from buvis.pybase.filesystem import atomic_write_text

__all__ = [
    "DEFAULT_STATE_DIR",
    "STATE_FILE_NAME",
    "UPGRADE_BACKOFF",
    "append_log",
    "clear_upgrade_failure",
    "read_cache",
    "read_installer_cache",
    "read_upgrade_failure",
    "write_cache",
    "write_installer_cache",
    "write_upgrade_failure",
]

DEFAULT_STATE_DIR = Path.home() / ".config" / "buvis"
STATE_FILE_NAME = "updater.json"
UPGRADE_BACKOFF = timedelta(hours=24)
_MAX_LOG_ENTRIES = 100
_INSTALLER_CACHE_KEY = "installer_cache"
_UPGRADE_FAILED_KEY = "upgrade_failed"


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
        atomic_write_text(_state_path(state_dir), json.dumps(state, indent=2))
    except Exception:
        return


def _parse_ts(value: Any) -> datetime | None:
    """Parse an ISO timestamp, treating a naive one as UTC. Returns None if invalid."""
    if not isinstance(value, str):
        return None
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def read_cache(state_dir: Path) -> tuple[datetime | None, str | None]:
    """Read cached check timestamp and version. Returns (None, None) on any error."""
    state = _read_state(state_dir)
    last_check = _parse_ts(state.get("last_check"))
    latest_version = state.get("latest_version")
    if last_check is None or not isinstance(latest_version, str):
        return None, None
    return last_check, latest_version


def write_cache(state_dir: Path, latest_version: str) -> None:
    """Update cache fields without touching the log."""
    state = _read_state(state_dir)
    state["last_check"] = _now_iso()
    state["latest_version"] = latest_version
    _write_state(state_dir, state)


def read_installer_cache(state_dir: Path, method: str) -> tuple[datetime | None, str | None]:
    """Read the installer-index cache recorded for ``method``.

    Args:
        state_dir: Directory holding the updater state file.
        method: Installer method the record must match (``InstallerInfo.method``).

    Returns:
        ``(last_check, latest_version)``, or ``(None, None)`` when the record is
        absent, malformed or was written for a different installer method.
    """
    record = _read_state(state_dir).get(_INSTALLER_CACHE_KEY)
    if not isinstance(record, dict) or record.get("method") != method:
        return None, None
    last_check = _parse_ts(record.get("last_check"))
    latest_version = record.get("latest_version")
    if last_check is None or not isinstance(latest_version, str):
        return None, None
    return last_check, latest_version


def write_installer_cache(state_dir: Path, method: str, latest_version: str) -> None:
    """Record the installer-index lookup result, leaving every other field intact."""
    state = _read_state(state_dir)
    state[_INSTALLER_CACHE_KEY] = {"method": method, "last_check": _now_iso(), "latest_version": latest_version}
    _write_state(state_dir, state)


def read_upgrade_failure(state_dir: Path) -> tuple[str, datetime] | None:
    """Return ``(version, ts)`` of the last no-op upgrade, or None if absent or malformed."""
    record = _read_state(state_dir).get(_UPGRADE_FAILED_KEY)
    if not isinstance(record, dict):
        return None
    version = record.get("version")
    ts = _parse_ts(record.get("ts"))
    if not isinstance(version, str) or ts is None:
        return None
    return version, ts


def write_upgrade_failure(state_dir: Path, version: str) -> None:
    """Record that upgrading to ``version`` was a no-op, stamped with the current time."""
    state = _read_state(state_dir)
    state[_UPGRADE_FAILED_KEY] = {"version": version, "ts": _now_iso()}
    _write_state(state_dir, state)


def clear_upgrade_failure(state_dir: Path) -> None:
    """Remove the no-op upgrade record, if any."""
    state = _read_state(state_dir)
    if state.pop(_UPGRADE_FAILED_KEY, None) is not None:
        _write_state(state_dir, state)


def append_log(state_dir: Path, level: str, message: str) -> None:
    """Append an event to the log, keeping only the most recent entries."""
    state = _read_state(state_dir)
    log_entries = state.get("log")
    if not isinstance(log_entries, list):
        log_entries = []
    log_entries.append(
        {
            "ts": _now_iso(),
            "level": level,
            "message": message,
        }
    )
    state["log"] = log_entries[-_MAX_LOG_ENTRIES:]
    _write_state(state_dir, state)
