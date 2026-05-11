"""Uninstall pidash hook entries from ``~/.claude/settings.json``."""

from __future__ import annotations

import json
from pathlib import Path

from buvis.pybase.result import CommandResult

from pidash.commands.hooks.settings import is_pidash_entry, load_settings, save_settings


def _strip_pidash(blocks: list[dict[str, object]]) -> tuple[list[dict[str, object]], int]:
    """Drop pidash-owned entries; prune empty blocks. Returns (pruned_blocks, removed_count)."""
    pruned: list[dict[str, object]] = []
    removed = 0
    for block in blocks:
        raw_entries = block.get("hooks", [])
        if not isinstance(raw_entries, list):
            pruned.append(block)
            continue
        kept: list[object] = []
        for entry in raw_entries:
            if isinstance(entry, dict) and is_pidash_entry(entry):
                removed += 1
                continue
            kept.append(entry)
        if kept:
            new_block = dict(block)
            new_block["hooks"] = kept
            pruned.append(new_block)
    return pruned, removed


def _load_or_failure(path: Path) -> tuple[dict[str, object] | None, CommandResult | None]:
    """Read settings.json. Returns (data, None) on success, (None, failure_result) otherwise."""
    try:
        return load_settings(path), None
    except json.JSONDecodeError as exc:
        return None, CommandResult(success=False, error=f"malformed settings.json: {exc}")
    except OSError as exc:
        return None, CommandResult(success=False, error=f"cannot read settings.json: {exc}")
    except ValueError as exc:
        return None, CommandResult(success=False, error=str(exc))


class CommandUninstall:
    """Remove pidash-owned entries from settings.json, leaving everything else intact."""

    def __init__(self, settings_path: Path) -> None:
        self.settings_path = settings_path

    def execute(self) -> CommandResult:
        if not self.settings_path.is_file():
            return CommandResult(
                success=True,
                output="no settings.json, nothing to remove",
                metadata={"removed": 0},
            )

        data, failure = _load_or_failure(self.settings_path)
        if failure is not None or data is None:
            return failure or CommandResult(success=False, error="unknown load failure")

        raw_hooks = data.get("hooks", {})
        if not isinstance(raw_hooks, dict):
            return CommandResult(success=True, output="no pidash hooks present", metadata={"removed": 0})

        total_removed = 0
        for event, blocks in list(raw_hooks.items()):
            if not isinstance(blocks, list):
                continue
            block_dicts = [b for b in blocks if isinstance(b, dict)]
            non_dict = [b for b in blocks if not isinstance(b, dict)]
            pruned, removed = _strip_pidash(block_dicts)
            total_removed += removed
            new_blocks = [*pruned, *non_dict]
            if new_blocks:
                raw_hooks[event] = new_blocks
            else:
                del raw_hooks[event]

        try:
            save_settings(self.settings_path, data)
        except OSError as exc:
            return CommandResult(success=False, error=f"cannot write settings.json: {exc}")

        return CommandResult(
            success=True,
            output=f"removed {total_removed}",
            metadata={"removed": total_removed},
        )
