"""Helpers for reading and writing ``~/.claude/settings.json``.

Exposes the canonical ``HOOK_REGISTRY`` (the six pidash hook entries Claude
Code must run), helpers for recognizing pidash-owned and legacy entries, and
atomic ``load_settings``/``save_settings`` round-trip primitives.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

PIDASH_COMMAND_PREFIX = "pidash hooks run "

LEGACY_HOOK_FILENAMES = (
    "set-pidash-attention.py",
    "clear-pidash-attention.py",
    "cleanup-pidash-session.py",
    "update-pidash-tasks.py",
    "sync-pidash-on-agent-return.py",
)


@dataclass(frozen=True)
class HookEntry:
    """One Claude Code hook registration."""

    event: str
    matcher: str | None  # None means default-matcher block (no "matcher" key)
    run_event: str  # argument to ``pidash hooks run``
    timeout: int


HOOK_REGISTRY: tuple[HookEntry, ...] = (
    HookEntry("Notification", "permission_prompt", "set-attention", 5),
    HookEntry("Notification", "idle_prompt", "set-attention", 5),
    HookEntry("PostToolUse", "TaskUpdate", "update-tasks", 5),
    HookEntry("PostToolUse", "Agent", "sync-agent-return", 5),
    HookEntry("PostToolUse", None, "clear-attention", 3),
    HookEntry("Stop", None, "cleanup-session", 5),
)


def build_hook_command(run_event: str) -> str:
    """Return the canonical ``pidash hooks run <event>`` command string."""
    return f"{PIDASH_COMMAND_PREFIX}{run_event}"


def is_pidash_entry(entry: dict[str, object]) -> bool:
    """True when ``entry`` is a pidash-owned hook command."""
    cmd = entry.get("command", "")
    return isinstance(cmd, str) and cmd.startswith(PIDASH_COMMAND_PREFIX)


def is_legacy_entry(entry: dict[str, object]) -> bool:
    """True when ``entry`` points at one of the legacy ``~/.claude/hooks/*.py`` scripts."""
    cmd = entry.get("command", "")
    if not isinstance(cmd, str):
        return False
    return any(name in cmd for name in LEGACY_HOOK_FILENAMES)


def load_settings(path: Path) -> dict[str, object]:
    """Load JSON from ``path``. Raises ``FileNotFoundError`` if missing, ``json.JSONDecodeError`` if malformed."""
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON is not an object")
    return data


def save_settings(path: Path, data: dict[str, object]) -> None:
    """Atomically write ``data`` to ``path`` as pretty-printed JSON with trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f"{path.stem}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
