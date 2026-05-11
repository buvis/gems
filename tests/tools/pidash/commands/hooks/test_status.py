from __future__ import annotations

import json
from pathlib import Path

from pidash.commands.hooks.install import CommandInstall
from pidash.commands.hooks.status import CommandStatus


class TestCommandStatus:
    def test_status_missing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        result = CommandStatus(target).execute()
        assert not result.success
        assert result.error == "settings.json not found"
        assert result.metadata["installed_count"] == 0
        assert result.metadata["missing_count"] == 6
        for row in result.metadata["hooks"]:
            assert row["installed"] is False

    def test_status_after_full_install(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        CommandInstall(target).execute()
        result = CommandStatus(target).execute()
        assert result.success
        assert result.metadata["installed_count"] == 6
        assert result.metadata["missing_count"] == 0
        for row in result.metadata["hooks"]:
            assert row["installed"] is True

    def test_status_partial_install(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        CommandInstall(target).execute()
        data = json.loads(target.read_text())
        data["hooks"]["Stop"] = []
        target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        result = CommandStatus(target).execute()
        assert not result.success
        assert result.metadata["installed_count"] == 5
        missing = [r for r in result.metadata["hooks"] if not r["installed"]]
        assert len(missing) == 1
        assert missing[0]["run_event"] == "cleanup-session"

    def test_status_ignores_legacy_entries(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Notification": [
                            {
                                "matcher": "permission_prompt",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 ~/.claude/hooks/set-pidash-attention.py",
                                        "timeout": 5,
                                    }
                                ],
                            }
                        ]
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        result = CommandStatus(target).execute()
        assert not result.success
        assert result.metadata["installed_count"] == 0

    def test_status_does_not_write(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        CommandInstall(target).execute()
        before = target.read_text()
        CommandStatus(target).execute()
        assert target.read_text() == before
