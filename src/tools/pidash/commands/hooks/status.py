"""Report which pidash hook entries are installed in ``~/.claude/settings.json``."""

from __future__ import annotations

import json
from pathlib import Path

from buvis.pybase.result import CommandResult

from pidash.commands.hooks.settings import (
    HOOK_REGISTRY,
    HookEntry,
    build_hook_command,
    load_settings,
)


def _entry_installed(data: dict[str, object], entry: HookEntry) -> bool:
    """True if ``data`` contains a registered hook matching ``entry``."""
    raw_hooks = data.get("hooks", {})
    if not isinstance(raw_hooks, dict):
        return False
    blocks = raw_hooks.get(entry.event, [])
    if not isinstance(blocks, list):
        return False
    target_command = build_hook_command(entry.run_event)
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if entry.matcher is None:
            if "matcher" in block:
                continue
        elif block.get("matcher") != entry.matcher:
            continue
        block_hooks = block.get("hooks", [])
        if not isinstance(block_hooks, list):
            continue
        for hook in block_hooks:
            if isinstance(hook, dict) and hook.get("command") == target_command:
                return True
    return False


def _missing_status_rows() -> list[dict[str, object]]:
    return [
        {
            "event": e.event,
            "matcher": e.matcher,
            "run_event": e.run_event,
            "installed": False,
        }
        for e in HOOK_REGISTRY
    ]


class CommandStatus:
    """Report install status for the six pidash hook entries."""

    def __init__(self, settings_path: Path) -> None:
        self.settings_path = settings_path

    def execute(self) -> CommandResult:
        if not self.settings_path.is_file():
            return CommandResult(
                success=False,
                error="settings.json not found",
                metadata={
                    "hooks": _missing_status_rows(),
                    "installed_count": 0,
                    "missing_count": len(HOOK_REGISTRY),
                },
            )

        try:
            data = load_settings(self.settings_path)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            return CommandResult(success=False, error=f"cannot read settings.json: {exc}")

        rows: list[dict[str, object]] = []
        installed_count = 0
        for entry in HOOK_REGISTRY:
            installed = _entry_installed(data, entry)
            installed_count += int(installed)
            rows.append(
                {
                    "event": entry.event,
                    "matcher": entry.matcher,
                    "run_event": entry.run_event,
                    "installed": installed,
                }
            )

        return CommandResult(
            success=installed_count == len(HOOK_REGISTRY),
            output=f"{installed_count}/{len(HOOK_REGISTRY)} pidash hooks installed",
            metadata={
                "hooks": rows,
                "installed_count": installed_count,
                "missing_count": len(HOOK_REGISTRY) - installed_count,
            },
        )
