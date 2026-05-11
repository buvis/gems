from __future__ import annotations

import json
from pathlib import Path

from pidash.commands.hooks.install import CommandInstall
from pidash.commands.hooks.settings import HOOK_REGISTRY, PIDASH_COMMAND_PREFIX


def _all_pidash_commands(data: dict) -> list[str]:
    cmds: list[str] = []
    for blocks in data.get("hooks", {}).values():
        for block in blocks:
            for entry in block.get("hooks", []):
                cmd = entry.get("command", "")
                if cmd.startswith(PIDASH_COMMAND_PREFIX):
                    cmds.append(cmd)
    return cmds


class TestCommandInstall:
    def test_install_on_missing_settings(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        result = CommandInstall(target).execute()
        assert result.success
        assert result.metadata["installed"] == 6
        assert result.metadata["replaced"] == 0
        assert result.metadata["removed_legacy"] == 0
        data = json.loads(target.read_text())
        cmds = _all_pidash_commands(data)
        assert len(cmds) == 6
        run_events = {c.removeprefix(PIDASH_COMMAND_PREFIX) for c in cmds}
        assert run_events == {e.run_event for e in HOOK_REGISTRY}

    def test_install_idempotent(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        CommandInstall(target).execute()
        first = target.read_text()
        result = CommandInstall(target).execute()
        assert result.success
        assert result.metadata["replaced"] == 6
        assert result.metadata["removed_legacy"] == 0
        assert target.read_text() == first

    def test_install_strips_legacy_entries(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        legacy = {
            "hooks": {
                "Notification": [
                    {
                        "matcher": "permission_prompt",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 ~/.claude/hooks/set-pidash-attention.py",
                                "timeout": 5,
                            },
                            {
                                "type": "command",
                                "command": "python3 ~/.claude/hooks/notify.py",
                                "timeout": 15,
                            },
                        ],
                    }
                ],
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 ~/.claude/hooks/cleanup-pidash-session.py",
                                "timeout": 5,
                            }
                        ]
                    }
                ],
            }
        }
        target.write_text(json.dumps(legacy, indent=2), encoding="utf-8")
        result = CommandInstall(target).execute()
        assert result.success
        assert result.metadata["removed_legacy"] >= 2
        data = json.loads(target.read_text())
        all_cmds = json.dumps(data)
        assert "set-pidash-attention.py" not in all_cmds
        assert "cleanup-pidash-session.py" not in all_cmds
        assert "notify.py" in all_cmds

    def test_install_preserves_unrelated_entries(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        unrelated = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Edit|Write|MultiEdit",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 ~/.claude/hooks/design-quality-check.py",
                                "timeout": 5,
                            }
                        ],
                    }
                ]
            }
        }
        target.write_text(json.dumps(unrelated, indent=2), encoding="utf-8")
        CommandInstall(target).execute()
        data = json.loads(target.read_text())
        edit_blocks = [b for b in data["hooks"]["PostToolUse"] if b.get("matcher") == "Edit|Write|MultiEdit"]
        assert len(edit_blocks) == 1
        cmds = [h["command"] for h in edit_blocks[0]["hooks"]]
        assert "python3 ~/.claude/hooks/design-quality-check.py" in cmds

    def test_install_on_malformed_json_returns_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text("{ broken", encoding="utf-8")
        before = target.read_text()
        result = CommandInstall(target).execute()
        assert not result.success
        assert "malformed" in (result.error or "").lower()
        assert target.read_text() == before
