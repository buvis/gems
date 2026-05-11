"""Shared helpers for mirroring autopilot state to ``~/.pidash/sessions/``.

This module is the single source of truth for ``SESSIONS_DIR`` and is
imported by both the bundled hook entrypoints (set-attention, update-tasks,
etc.) and by ``pidash.tui.watcher``.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path.home() / ".pidash" / "sessions"


def read_hook_input() -> dict[str, object]:
    """Read and parse JSON from stdin.

    Returns an empty dict on any failure (TTY stdin, empty input, malformed JSON, OSError).
    """
    try:
        if sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError, OSError):
        return {}


def mirror_to_session_dir(hook_input: dict[str, object], state: dict[str, object]) -> None:
    """Write session state to ``~/.pidash/sessions/{session_id}.json``.

    Skips silently if ``session_id`` is missing from ``hook_input``.
    """
    raw_id = hook_input.get("session_id")
    if not isinstance(raw_id, str) or not raw_id:
        return
    if "\x00" in raw_id:
        return
    session_id = Path(raw_id).name  # strip directory components
    if not session_id:
        return

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    merged: dict[str, object] = dict(state)
    merged["session_id"] = session_id
    cwd = hook_input.get("cwd", "")
    merged["cwd"] = cwd if isinstance(cwd, str) else ""
    merged["updated_at"] = datetime.now(timezone.utc).isoformat()

    write_session_file(SESSIONS_DIR / f"{session_id}.json", merged)


def write_session_file(target: Path, data: dict[str, object]) -> None:
    """Atomically write JSON ``data`` to ``target`` via tempfile + os.replace."""
    write_json_atomic(target, data)


def write_json_atomic(target: Path, data: dict[str, object]) -> None:
    """Atomically write JSON ``data`` to ``target`` via tempfile + os.replace.

    On any ``OSError`` (full disk, permission denied, etc.) the tempfile is
    cleaned up and the original ``target`` is left untouched -- no truncated
    or half-written file. ``target.parent`` is auto-created.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = ""
    try:
        fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp", prefix=f"{target.stem}.")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, target)
    except OSError:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
