"""PostToolUse hook: clear ``needs_attention`` in autopilot state.

Invoked by Claude Code's default-matcher PostToolUse block via
``pidash hooks run clear-attention``. Skips writes when the flag is already
falsy to avoid tool-call storm churn on ``state.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from pidash.hooks.session import mirror_to_session_dir, read_hook_input


def main() -> None:
    """Read hook input, flip ``needs_attention`` off, mirror to session dir."""
    hook_input = read_hook_input()

    state_file = Path("dev/local/autopilot/state.json")
    if not state_file.is_file():
        return

    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if not state.get("needs_attention"):
            return  # already clear, skip write storm
        state["needs_attention"] = False
        state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    except (json.JSONDecodeError, OSError):
        return

    mirror_to_session_dir(hook_input, state)
