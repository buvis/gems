"""PostToolUse hook for Agent: sync task status to autopilot state.

Safety net for subagent dispatches: PostToolUse hooks don't fire inside a
subagent, so any ``TaskUpdate`` calls it makes are invisible to the host
session's ``update-tasks`` hook. This hook parses the Agent tool's response
text for ``✓ Task``, ``- [x] Task``, ``■ Task`` (etc.) markers and applies
the implied status changes to ``state.json``.

Invoked by ``pidash hooks run sync-agent-return``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pidash.hooks.session import mirror_to_session_dir, read_hook_input

_PREFIX_RE = re.compile(r"^\[(?:C\d+|DOUBT)\]\s*")
_EN_DASH = "\u2013"
_EM_DASH = "\u2014"
_COMPLETED_GLYPH_RE = re.compile(r"^[✓✅]\s+")
_COMPLETED_CHECKBOX_RE = re.compile(r"^-\s+\[x\]\s+", re.IGNORECASE)
_IN_PROGRESS_GLYPH_RE = re.compile(r"^[■▸\U0001f504⏳]\s+")


def _normalize(s: str) -> str:
    """Normalize unicode dashes and whitespace for comparison."""
    return s.replace(_EN_DASH, "-").replace(_EM_DASH, "-").strip().lower()


def _strip_prefix(name: str) -> str:
    """Strip ``[C1]``, ``[DOUBT]`` etc. prefixes."""
    return _PREFIX_RE.sub("", name)


def _names_match(task_name: str, candidate: str) -> bool:
    """Match names, ignoring ``[C{n}]``/``[DOUBT]`` prefixes; substring-tolerant."""
    tn = _normalize(task_name)
    cn = _normalize(candidate)
    if tn == cn or tn in cn or cn in tn:
        return True
    tn_base = _normalize(_strip_prefix(task_name))
    cn_base = _normalize(_strip_prefix(candidate))
    if tn_base and cn_base and (tn_base in cn_base or cn_base in tn_base):
        return True
    return tn_base == cn_base


def _extract_task_markers(text: str) -> tuple[list[str], list[str]]:
    """Extract (completed_names, in_progress_names) from agent response text."""
    completed: list[str] = []
    in_progress: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if _COMPLETED_GLYPH_RE.match(stripped):
            completed.append(_COMPLETED_GLYPH_RE.sub("", stripped))
        elif _COMPLETED_CHECKBOX_RE.match(stripped):
            completed.append(_COMPLETED_CHECKBOX_RE.sub("", stripped))
        elif _IN_PROGRESS_GLYPH_RE.match(stripped):
            in_progress.append(_IN_PROGRESS_GLYPH_RE.sub("", stripped))
    return completed, in_progress


def _normalize_tasks_in_place(tasks: list[object]) -> list[dict[str, object]]:
    """Convert any string tasks to dicts; return the resulting dict list."""
    for i, t in enumerate(tasks):
        if isinstance(t, str):
            tasks[i] = {"name": t, "status": "pending"}
    return [t for t in tasks if isinstance(t, dict)]


def _load_state(state_file: Path) -> dict[str, object] | None:
    if not state_file.is_file():
        return None
    try:
        loaded = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _apply_markers(
    tasks: list[dict[str, object]],
    completed_names: list[str],
    in_progress_names: list[str],
) -> bool:
    """Apply marker updates; return True if any task changed."""
    updated = False
    for task in tasks:
        task_name = task.get("name", "")
        if not isinstance(task_name, str) or not task_name:
            continue

        if task.get("status") != "completed":
            for comp_name in completed_names:
                if _names_match(task_name, comp_name):
                    task["status"] = "completed"
                    updated = True
                    break

        if task.get("status") == "pending":
            for ip_name in in_progress_names:
                if _names_match(task_name, ip_name):
                    task["status"] = "in_progress"
                    updated = True
                    break

    return updated


def main() -> None:
    """Parse agent response markers and reflect them into state.json."""
    hook_input = read_hook_input()
    if not hook_input:
        return

    response_text = str(hook_input.get("tool_response", ""))
    if not response_text:
        return

    state_file = Path("dev/local/autopilot/state.json")
    state = _load_state(state_file)
    if state is None:
        return

    raw_tasks = state.get("tasks", [])
    if not isinstance(raw_tasks, list) or not raw_tasks:
        return
    tasks = _normalize_tasks_in_place(raw_tasks)
    state["tasks"] = tasks

    completed_names, in_progress_names = _extract_task_markers(response_text)
    if (not completed_names and not in_progress_names) or not _apply_markers(tasks, completed_names, in_progress_names):
        return

    state["tasks_completed"] = sum(1 for t in tasks if t.get("status") == "completed")
    state["tasks_total"] = len(tasks)

    try:
        state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass  # mirror anyway: legacy behavior

    mirror_to_session_dir(hook_input, state)
