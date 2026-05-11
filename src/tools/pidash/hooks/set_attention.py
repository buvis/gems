"""Notification hook: set ``needs_attention=True`` in autopilot state.

Invoked by Claude Code's permission_prompt and idle_prompt notifications via
``pidash hooks run set-attention``. Mirrors the updated state into
``~/.pidash/sessions/{session_id}.json`` so the dashboard sees the flag.
"""

from __future__ import annotations

import json
from pathlib import Path

from pidash.hooks.session import mirror_to_session_dir, read_hook_input


def main() -> None:
    """Read hook input, flip ``needs_attention``, mirror to session dir."""
    hook_input = read_hook_input()

    state_file = Path("dev/local/autopilot/state.json")
    if not state_file.is_file():
        return

    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["needs_attention"] = True
        state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    except (json.JSONDecodeError, OSError):
        return

    mirror_to_session_dir(hook_input, state)
