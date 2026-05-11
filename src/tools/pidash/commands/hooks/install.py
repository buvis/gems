"""Install pidash hook entries into ``~/.claude/settings.json``."""

from __future__ import annotations

import json
from pathlib import Path

from buvis.pybase.result import CommandResult

from pidash.commands.hooks.settings import (
    HOOK_REGISTRY,
    HookEntry,
    build_hook_command,
    is_legacy_entry,
    is_pidash_entry,
    load_settings,
    save_settings,
)


def _strip_managed_entries(
    blocks: list[dict[str, object]],
) -> tuple[list[dict[str, object]], int, int]:
    """Remove pidash-owned and legacy entries from ``blocks``.

    Returns the pruned list, count of pidash entries removed, count of legacy entries removed.
    Blocks with empty ``hooks`` lists after filtering are dropped.
    """
    pruned: list[dict[str, object]] = []
    replaced = 0
    removed_legacy = 0
    for block in blocks:
        raw_entries = block.get("hooks", [])
        if not isinstance(raw_entries, list):
            pruned.append(block)
            continue
        kept: list[object] = []
        for entry in raw_entries:
            if not isinstance(entry, dict):
                kept.append(entry)
                continue
            if is_pidash_entry(entry):
                replaced += 1
                continue
            if is_legacy_entry(entry):
                removed_legacy += 1
                continue
            kept.append(entry)
        if kept:
            new_block = dict(block)
            new_block["hooks"] = kept
            pruned.append(new_block)
    return pruned, replaced, removed_legacy


def _find_or_create_block(blocks: list[dict[str, object]], matcher: str | None) -> dict[str, object]:
    """Return the block matching ``matcher`` (creating an empty one if absent).

    ``matcher=None`` selects/creates a default-matcher block (no ``matcher`` key).
    """
    for block in blocks:
        if matcher is None:
            if "matcher" not in block:
                return block
        elif block.get("matcher") == matcher:
            return block
    new_block: dict[str, object] = {} if matcher is None else {"matcher": matcher}
    new_block["hooks"] = []
    blocks.append(new_block)
    return new_block


def _insert_hook_entry(hooks_map: dict[str, object], entry: HookEntry) -> None:
    """Append the canonical command entry for ``entry`` into ``hooks_map``."""
    event_blocks = hooks_map.setdefault(entry.event, [])
    if not isinstance(event_blocks, list):
        event_blocks = []
        hooks_map[entry.event] = event_blocks
    block = _find_or_create_block(event_blocks, entry.matcher)
    block_hooks = block.setdefault("hooks", [])
    if not isinstance(block_hooks, list):
        block_hooks = []
        block["hooks"] = block_hooks
    block_hooks.append(
        {
            "type": "command",
            "command": build_hook_command(entry.run_event),
            "timeout": entry.timeout,
        }
    )


class CommandInstall:
    """Idempotently install the six pidash hook entries into settings.json."""

    def __init__(self, settings_path: Path) -> None:
        self.settings_path = settings_path

    def execute(self) -> CommandResult:
        if self.settings_path.is_file():
            try:
                data = load_settings(self.settings_path)
            except json.JSONDecodeError as exc:
                return CommandResult(success=False, error=f"malformed settings.json: {exc}")
            except OSError as exc:
                return CommandResult(success=False, error=f"cannot read settings.json: {exc}")
            except ValueError as exc:
                return CommandResult(success=False, error=str(exc))
        else:
            data = {}

        if "hooks" in data and not isinstance(data["hooks"], dict):
            return CommandResult(
                success=False,
                error=(f"malformed settings.json: `hooks` must be a JSON object, got {type(data['hooks']).__name__}"),
            )
        existing = data.get("hooks")
        raw_hooks: dict[str, object] = existing if isinstance(existing, dict) else {}
        data["hooks"] = raw_hooks

        replaced_total = 0
        removed_legacy_total = 0
        for event, blocks in list(raw_hooks.items()):
            if not isinstance(blocks, list):
                continue
            block_dicts = [b for b in blocks if isinstance(b, dict)]
            non_dict = [b for b in blocks if not isinstance(b, dict)]
            pruned, replaced, removed_legacy = _strip_managed_entries(block_dicts)
            replaced_total += replaced
            removed_legacy_total += removed_legacy
            raw_hooks[event] = [*pruned, *non_dict]

        for entry in HOOK_REGISTRY:
            _insert_hook_entry(raw_hooks, entry)

        try:
            save_settings(self.settings_path, data)
        except OSError as exc:
            return CommandResult(success=False, error=f"cannot write settings.json: {exc}")

        return CommandResult(
            success=True,
            output=(
                f"installed {len(HOOK_REGISTRY)}, replaced {replaced_total}, removed_legacy {removed_legacy_total}"
            ),
            metadata={
                "installed": len(HOOK_REGISTRY),
                "replaced": replaced_total,
                "removed_legacy": removed_legacy_total,
            },
        )
