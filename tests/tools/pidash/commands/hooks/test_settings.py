from __future__ import annotations

import json
from pathlib import Path

import pytest
from pidash.commands.hooks.settings import (
    HOOK_REGISTRY,
    PIDASH_COMMAND_PREFIX,
    HookEntry,
    build_hook_command,
    is_legacy_entry,
    is_pidash_entry,
    load_settings,
    save_settings,
)


class TestHookRegistry:
    def test_registry_covers_all_six_canonical_entries(self) -> None:
        assert len(HOOK_REGISTRY) == 6
        run_events = {e.run_event for e in HOOK_REGISTRY}
        assert run_events == {
            "set-attention",
            "clear-attention",
            "cleanup-session",
            "update-tasks",
            "sync-agent-return",
        }

    def test_default_matcher_blocks_have_matcher_none(self) -> None:
        defaults = [e for e in HOOK_REGISTRY if e.matcher is None]
        events = {e.event for e in defaults}
        assert events == {"PostToolUse", "Stop"}

    def test_each_entry_has_positive_timeout(self) -> None:
        for entry in HOOK_REGISTRY:
            assert isinstance(entry, HookEntry)
            assert entry.timeout > 0


class TestBuildHookCommand:
    def test_prepends_prefix(self) -> None:
        assert build_hook_command("set-attention") == "pidash hooks run set-attention"

    def test_uses_documented_prefix(self) -> None:
        assert PIDASH_COMMAND_PREFIX == "pidash hooks run "


class TestIsPidashEntry:
    def test_pidash_command_detected(self) -> None:
        assert is_pidash_entry({"command": "pidash hooks run set-attention"})

    def test_legacy_command_not_pidash(self) -> None:
        assert not is_pidash_entry({"command": "python3 ~/.claude/hooks/set-pidash-attention.py"})

    def test_missing_command_not_pidash(self) -> None:
        assert not is_pidash_entry({})

    def test_non_string_command_not_pidash(self) -> None:
        assert not is_pidash_entry({"command": 123})


class TestIsLegacyEntry:
    @pytest.mark.parametrize(
        "command",
        [
            "python3 ~/.claude/hooks/set-pidash-attention.py",
            "python3 /Users/bob/.claude/hooks/clear-pidash-attention.py",
            "~/.claude/hooks/cleanup-pidash-session.py",
            "python3 ~/.claude/hooks/update-pidash-tasks.py",
            "python3 ~/.claude/hooks/sync-pidash-on-agent-return.py",
        ],
    )
    def test_legacy_paths_detected(self, command: str) -> None:
        assert is_legacy_entry({"command": command})

    def test_pidash_command_not_legacy(self) -> None:
        assert not is_legacy_entry({"command": "pidash hooks run set-attention"})

    def test_unrelated_command_not_legacy(self) -> None:
        assert not is_legacy_entry({"command": "python3 ~/.claude/hooks/notify.py"})


class TestLoadSettings:
    def test_loads_valid_json(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text('{"a": 1}', encoding="utf-8")
        assert load_settings(target) == {"a": 1}

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_settings(tmp_path / "missing.json")

    def test_malformed_json_raises(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text("not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_settings(target)

    def test_top_level_array_rejected(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text("[1, 2]", encoding="utf-8")
        with pytest.raises(ValueError, match="not an object"):
            load_settings(target)


class TestSaveSettings:
    def test_writes_pretty_json_with_newline(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        save_settings(target, {"a": 1, "nested": {"b": 2}})
        raw = target.read_text(encoding="utf-8")
        assert raw.endswith("\n")
        assert json.loads(raw) == {"a": 1, "nested": {"b": 2}}
        assert '  "a": 1' in raw

    def test_round_trip_preserves_content(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        data = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x", "timeout": 5}]}]}}
        save_settings(target, data)
        assert load_settings(target) == data

    def test_double_save_is_byte_identical(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        data = {"hooks": {"PostToolUse": [{"matcher": "TaskUpdate", "hooks": []}]}}
        save_settings(target, data)
        first = target.read_text(encoding="utf-8")
        save_settings(target, data)
        assert target.read_text(encoding="utf-8") == first

    def test_creates_parent_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "settings.json"
        save_settings(target, {})
        assert target.is_file()
