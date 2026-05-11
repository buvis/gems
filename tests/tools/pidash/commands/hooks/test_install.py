from __future__ import annotations

import json
from pathlib import Path

from pidash.commands.hooks.install import CommandInstall
from pidash.commands.hooks.settings import HOOK_REGISTRY, PIDASH_COMMAND_PREFIX
from pidash.commands.hooks.uninstall import CommandUninstall


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

    def test_install_on_non_dict_hooks_value_returns_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text(json.dumps({"hooks": []}), encoding="utf-8")
        before = target.read_text()
        result = CommandInstall(target).execute()
        assert not result.success
        assert "hooks" in (result.error or "").lower()
        assert target.read_text() == before

    def test_install_on_string_hooks_value_returns_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text(json.dumps({"hooks": "oops"}), encoding="utf-8")
        before = target.read_text()
        result = CommandInstall(target).execute()
        assert not result.success
        assert "hooks" in (result.error or "").lower()
        assert target.read_text() == before

    def test_install_on_null_hooks_value_returns_failure(self, tmp_path: Path) -> None:
        """A JSON ``null`` value for ``hooks`` is malformed-for-our-purposes,
        like an array or string. The original file must be left untouched."""
        target = tmp_path / "settings.json"
        target.write_text(json.dumps({"hooks": None}), encoding="utf-8")
        before = target.read_text()
        result = CommandInstall(target).execute()
        assert not result.success
        assert "hooks" in (result.error or "").lower()
        assert target.read_text() == before

    def test_install_preserves_unrelated_top_level_keys(self, tmp_path: Path) -> None:
        """Top-level keys other than ``hooks`` (permissions, env, mcpServers, …)
        must round-trip unchanged through both install and uninstall."""
        target = tmp_path / "settings.json"
        seed = {
            "permissions": {"allow": ["Bash(git:*)"], "deny": ["Bash(rm -rf /:*)"]},
            "env": {"FOO": "bar", "DEBUG": "1"},
            "mcpServers": {
                "exa": {"command": "npx", "args": ["-y", "exa-mcp"]},
            },
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
                ],
            },
        }
        target.write_text(json.dumps(seed, indent=2), encoding="utf-8")

        assert CommandInstall(target).execute().success
        after_install = json.loads(target.read_text())
        for key in ("permissions", "env", "mcpServers"):
            assert after_install[key] == seed[key], f"{key} mutated by install"

        assert CommandUninstall(target).execute().success
        after_uninstall = json.loads(target.read_text())
        for key in ("permissions", "env", "mcpServers"):
            assert after_uninstall[key] == seed[key], f"{key} mutated by uninstall"
        # The unrelated hook entry must also still be there.
        post_blocks = after_uninstall["hooks"]["PostToolUse"]
        assert any(
            any(h.get("command") == "python3 ~/.claude/hooks/design-quality-check.py" for h in block.get("hooks", []))
            for block in post_blocks
        )
