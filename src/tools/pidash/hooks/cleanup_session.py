"""Stop hook: mark a session as stopped in ``~/.pidash/sessions/``.

Invoked by Claude Code's Stop event via ``pidash hooks run cleanup-session``.
Writes ``phase: "stopped"`` plus ``stopped_at`` and ``updated_at`` timestamps
to the session file (creating a minimal record if none exists yet).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pidash.hooks.session import SESSIONS_DIR, read_hook_input, write_session_file


def main() -> None:
    """Mark the current session as stopped in its session file."""
    hook_input = read_hook_input()
    raw_id = hook_input.get("session_id")
    if not isinstance(raw_id, str) or not raw_id:
        return
    if "\x00" in raw_id:
        return
    session_id = Path(raw_id).name
    if not session_id:
        return

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    target = SESSIONS_DIR / f"{session_id}.json"
    now = datetime.now(timezone.utc).isoformat()
    cwd = hook_input.get("cwd", "")
    cwd_str = cwd if isinstance(cwd, str) else ""

    state: dict[str, object]
    if target.is_file():
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
            state = loaded if isinstance(loaded, dict) else {}
        except (json.JSONDecodeError, OSError):
            state = {}
    else:
        state = {"session_id": session_id, "cwd": cwd_str}

    state.setdefault("session_id", session_id)
    state.setdefault("cwd", cwd_str)
    state["phase"] = "stopped"
    state["stopped_at"] = now
    state["updated_at"] = now

    write_session_file(target, state)
