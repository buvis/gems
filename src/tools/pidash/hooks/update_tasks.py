"""PostToolUse hook for TaskUpdate: sync task status to autopilot state.

Invoked by Claude Code's ``PostToolUse(TaskUpdate)`` matcher via
``pidash hooks run update-tasks``. Tries four matching strategies in order
(by id, by title from tool_response, by substring in response, by title from
tool_input), then mirrors the updated state to the session file.

Drops the ``pidash-hook.log`` diagnostic writer that the legacy script used:
silent no-op when no task matches.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pidash.hooks.session import mirror_to_session_dir, read_hook_input, write_json_atomic

_PREFIX_RE = re.compile(r"^\[(?:C\d+|DOUBT)\]\s*")
# Unicode dashes normalized to ASCII '-' so titles round-trip through tools
# that silently rewrite '-' to en- or em-dash.
_EN_DASH = "\u2013"
_EM_DASH = "\u2014"


def _strip_task_prefix(name: str) -> str:
    """Strip ``[C1]``, ``[C2]``, ``[DOUBT]`` etc. prefixes from task names."""
    return _PREFIX_RE.sub("", name)


def _find_task_title(hook_input: dict[str, object]) -> str:
    """Extract task title from ``tool_response`` (JSON dict or text)."""
    resp = hook_input.get("tool_response", "")
    if isinstance(resp, dict):
        title = resp.get("title") or resp.get("name") or ""
        return title if isinstance(title, str) else ""
    if isinstance(resp, str):
        try:
            parsed = json.loads(resp)
        except (json.JSONDecodeError, ValueError):
            return ""
        if isinstance(parsed, dict):
            title = parsed.get("title") or parsed.get("name") or ""
            return title if isinstance(title, str) else ""
    return ""


def _normalize_tasks(tasks: list[object]) -> list[dict[str, object]]:
    """Convert string tasks to dicts so matching works."""
    result: list[dict[str, object]] = []
    for t in tasks:
        if isinstance(t, str):
            result.append({"name": t, "status": "pending"})
        elif isinstance(t, dict):
            result.append(t)
    return result


def _norm(s: str) -> str:
    return s.replace(_EN_DASH, "-").replace(_EM_DASH, "-").strip().lower()


def _name_matches(task_name: str, candidate: str) -> bool:
    """Match task names, ignoring ``[C{n}]``/``[DOUBT]`` prefixes and unicode dashes."""
    tn = _norm(task_name)
    cn = _norm(candidate)
    if tn == cn:
        return True
    tn_base = _norm(_strip_task_prefix(task_name))
    cn_base = _norm(_strip_task_prefix(candidate))
    return tn_base == cn_base


def _parse_request(hook_input: dict[str, object]) -> tuple[str, str] | None:
    """Extract (task_id, new_status) from hook input, or None when invalid."""
    tool_input = hook_input.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return None
    task_id = tool_input.get("id", "")
    new_status = tool_input.get("status", "")
    if not isinstance(task_id, str) or not isinstance(new_status, str):
        return None
    if not task_id or not new_status:
        return None
    return task_id, new_status


def _load_state(state_file: Path) -> dict[str, object] | None:
    """Load autopilot state.json, or None on any read/parse failure."""
    if not state_file.is_file():
        return None
    try:
        loaded = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _normalize_task_list(state: dict[str, object]) -> list[dict[str, object]] | None:
    """Normalize ``state['tasks']`` in place to a list of dicts, or None when missing/empty."""
    raw_tasks = state.get("tasks", [])
    if not isinstance(raw_tasks, list) or not raw_tasks:
        return None
    tasks = _normalize_tasks(raw_tasks)
    state["tasks"] = tasks
    return tasks


def _match_by_id(task: dict[str, object], task_id: str, hook_input: dict[str, object]) -> bool:
    del hook_input
    return task.get("id") == task_id


def _match_by_response_title(task: dict[str, object], task_id: str, hook_input: dict[str, object]) -> bool:
    del task_id
    title = _find_task_title(hook_input)
    if not title:
        return False
    name = task.get("name")
    return isinstance(name, str) and _name_matches(name, title)


def _match_by_response_substring(task: dict[str, object], task_id: str, hook_input: dict[str, object]) -> bool:
    del task_id
    name = task.get("name", "")
    if not isinstance(name, str) or not name:
        return False
    resp_text = str(hook_input.get("tool_response", ""))
    return name in resp_text or _strip_task_prefix(name) in resp_text


def _match_by_input_title(task: dict[str, object], task_id: str, hook_input: dict[str, object]) -> bool:
    del task_id
    tool_input = hook_input.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return False
    input_title = tool_input.get("title") or tool_input.get("name") or ""
    if not isinstance(input_title, str) or not input_title:
        return False
    name = task.get("name")
    return isinstance(name, str) and _name_matches(name, input_title)


_MATCHERS = (
    _match_by_id,
    _match_by_response_title,
    _match_by_response_substring,
    _match_by_input_title,
)


def _apply_match(
    tasks: list[dict[str, object]],
    task_id: str,
    new_status: str,
    hook_input: dict[str, object],
) -> bool:
    """Update one task's status using the four-strategy match chain."""
    for matcher in _MATCHERS:
        for task in tasks:
            if matcher(task, task_id, hook_input):
                task["status"] = new_status
                if matcher is not _match_by_id:
                    task["id"] = task_id
                return True
    return False


def main() -> None:
    """Apply the TaskUpdate to state.json and mirror to session dir."""
    hook_input = read_hook_input()
    if not hook_input:
        return

    request = _parse_request(hook_input)
    if request is None:
        return
    task_id, new_status = request

    state_file = Path("dev/local/autopilot/state.json")
    state = _load_state(state_file)
    if state is None:
        return

    tasks = _normalize_task_list(state)
    if tasks is None or not _apply_match(tasks, task_id, new_status, hook_input):
        return

    state["tasks_completed"] = sum(1 for t in tasks if t.get("status") == "completed")
    state["tasks_total"] = len(tasks)

    write_json_atomic(state_file, state)

    mirror_to_session_dir(hook_input, state)
