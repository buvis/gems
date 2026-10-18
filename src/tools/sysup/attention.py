"""Persist unresolved outcomes and fold ordinary runs into attention state."""

from __future__ import annotations

import json
import os
from datetime import timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from buvis.pybase.filesystem import atomic_write_text

from sysup.step_result import RED

if TYPE_CHECKING:
    from datetime import datetime

    from sysup.step_result import StepResult

__all__ = ["exit_code", "fold_results", "mark_notified", "read_state", "state_path", "to_notify", "write_state"]

_RANK = {"warned": -1, "expiring": 0, "unknown": 1, "expired": 2, "failed": 3}


def state_path() -> Path:
    """Return the attention file path, honouring ``$XDG_STATE_HOME``."""
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "sysup" / "attention.json"


def _valid_entry(entry: Any) -> bool:
    return (
        isinstance(entry, dict)
        and set(entry) == {"kind", "status", "details", "first_seen", "last_checked", "notified"}
        and entry["kind"] in ("command", "item")
        and isinstance(entry["status"], str)
        and entry["status"] in _RANK
        and isinstance(entry["details"], list)
        and bool(entry["details"])
        and all(isinstance(detail, str) for detail in entry["details"])
        and isinstance(entry["first_seen"], str)
        and isinstance(entry["last_checked"], str)
        and isinstance(entry["notified"], bool)
    )


def read_state() -> dict[str, Any]:
    """Return validated entries, or an empty dict for absent or malformed state."""
    try:
        loaded = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if (
        not isinstance(loaded, dict)
        or set(loaded) != {"version", "entries"}
        or not isinstance(loaded["version"], int)
        or isinstance(loaded["version"], bool)
        or loaded["version"] != 1
        or not isinstance(loaded["entries"], dict)
        or not all(_valid_entry(entry) for entry in loaded["entries"].values())
    ):
        return {}
    entries: dict[str, Any] = loaded["entries"]
    return entries


def write_state(entries: dict[str, Any]) -> None:
    """Write a version-one state envelope atomically, creating parents."""
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps({"version": 1, "entries": entries}, indent=2, sort_keys=True) + "\n")


def fold_results(
    entries: dict[str, Any], checked: set[str], results: list[StepResult], now: datetime
) -> dict[str, Any]:
    """Return a new entries mapping with every checked name updated.

    A checked name with no not-ok result loses its entry; one with any not-ok
    result gets one entry holding every not-ok message of this run, so a
    success after a failure inside the same run never clears the failure.
    Names not checked keep their entry untouched.
    """
    stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    names = checked | {r.command or r.label for r in results}
    folded = dict(entries)
    for name in names:
        bad = [r for r in results if (r.command or r.label) == name and r.status != "ok"]
        if not bad:
            folded.pop(name, None)
            continue
        previous = entries.get(name, {})
        worst = max(bad, key=lambda r: _RANK[r.status])
        folded[name] = {
            "kind": bad[0].kind,
            "status": worst.status,
            "details": [r.message or f"{r.label} {r.status}" for r in bad],
            "first_seen": previous.get("first_seen", stamp),
            "last_checked": stamp,
            "notified": bool(previous.get("notified", False)),
        }
    return folded


def to_notify(entries: dict[str, Any]) -> list[str]:
    """Names to push this run: every red entry, plus any entry never pushed."""
    return sorted(name for name, entry in entries.items() if entry["status"] in RED or not entry.get("notified"))


def mark_notified(entries: dict[str, Any], names: list[str]) -> dict[str, Any]:
    return {name: ({**entry, "notified": True} if name in names else entry) for name, entry in entries.items()}


def exit_code(results: list[StepResult]) -> int:
    """1 when a result of THIS run is red; retained entries never count."""
    return 1 if any(r.status in RED for r in results) else 0
