from __future__ import annotations

import json
from pathlib import Path

from pidash.commands.hooks.install import CommandInstall
from pidash.commands.hooks.uninstall import CommandUninstall


class TestCommandUninstall:
    def test_uninstall_missing_file_is_success(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        result = CommandUninstall(target).execute()
        assert result.success
        assert result.metadata["removed"] == 0

    def test_uninstall_after_install_removes_all_pidash_entries(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        CommandInstall(target).execute()
        result = CommandUninstall(target).execute()
        assert result.success
        assert result.metadata["removed"] == 6
        data = json.loads(target.read_text())
        assert "pidash hooks run" not in json.dumps(data)

    def test_uninstall_preserves_unrelated_entries(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PostToolUse": [
                            {
                                "matcher": "Edit",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "pidash hooks run clear-attention",
                                        "timeout": 3,
                                    },
                                    {
                                        "type": "command",
                                        "command": "python3 ~/.claude/hooks/notify.py",
                                        "timeout": 15,
                                    },
                                ],
                            }
                        ]
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        result = CommandUninstall(target).execute()
        assert result.success
        assert result.metadata["removed"] == 1
        data = json.loads(target.read_text())
        assert "pidash hooks run" not in json.dumps(data)
        assert "notify.py" in json.dumps(data)

    def test_uninstall_drops_empty_event_after_pruning(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "pidash hooks run cleanup-session",
                                        "timeout": 5,
                                    }
                                ]
                            }
                        ]
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        CommandUninstall(target).execute()
        data = json.loads(target.read_text())
        assert "Stop" not in data["hooks"]

    def test_uninstall_idempotent(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text(json.dumps({"hooks": {}}, indent=2) + "\n", encoding="utf-8")
        first = CommandUninstall(target).execute()
        second = CommandUninstall(target).execute()
        assert first.metadata["removed"] == 0
        assert second.metadata["removed"] == 0
