"""End-to-end install/uninstall/status flow via the pidash CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from pidash.cli import cli


def _legacy_settings() -> dict[str, object]:
    return {
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
                },
                {
                    "matcher": "idle_prompt",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/set-pidash-attention.py",
                            "timeout": 5,
                        }
                    ],
                },
            ],
            "PostToolUse": [
                {
                    "matcher": "TaskUpdate",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/update-pidash-tasks.py",
                            "timeout": 5,
                        }
                    ],
                },
                {
                    "matcher": "Agent",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/sync-pidash-on-agent-return.py",
                            "timeout": 5,
                        }
                    ],
                },
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/clear-pidash-attention.py",
                            "timeout": 3,
                        },
                        {
                            "type": "command",
                            "command": "python3 ~/.claude/hooks/notify.py",
                            "timeout": 15,
                        },
                    ],
                },
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


@pytest.mark.integration
class TestInstallIntegration:
    def test_install_on_empty(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        runner = CliRunner()
        result = runner.invoke(cli, ["hooks", "install", "--settings-path", str(target)])
        assert result.exit_code == 0, result.output
        data = json.loads(target.read_text())
        assert json.dumps(data).count("pidash hooks run ") == 6

    def test_install_over_legacy_replaces_entries(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text(json.dumps(_legacy_settings(), indent=2), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["hooks", "install", "--settings-path", str(target)])
        assert result.exit_code == 0, result.output
        text = json.dumps(json.loads(target.read_text()))
        assert "set-pidash-attention.py" not in text
        assert "clear-pidash-attention.py" not in text
        assert "cleanup-pidash-session.py" not in text
        assert "update-pidash-tasks.py" not in text
        assert "sync-pidash-on-agent-return.py" not in text
        assert "notify.py" in text
        assert text.count("pidash hooks run ") == 6

    def test_install_idempotent(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        runner = CliRunner()
        runner.invoke(cli, ["hooks", "install", "--settings-path", str(target)])
        first = target.read_text()
        runner.invoke(cli, ["hooks", "install", "--settings-path", str(target)])
        assert target.read_text() == first

    def test_status_all_installed(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        runner = CliRunner()
        runner.invoke(cli, ["hooks", "install", "--settings-path", str(target)])
        result = runner.invoke(cli, ["hooks", "status", "--settings-path", str(target)])
        assert result.exit_code == 0, result.output

    def test_status_missing_settings_is_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "nothing.json"
        runner = CliRunner()
        result = runner.invoke(cli, ["hooks", "status", "--settings-path", str(target)])
        assert result.exit_code != 0

    def test_uninstall_round_trip(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text(json.dumps(_legacy_settings(), indent=2), encoding="utf-8")
        runner = CliRunner()
        runner.invoke(cli, ["hooks", "install", "--settings-path", str(target)])
        result = runner.invoke(cli, ["hooks", "uninstall", "--settings-path", str(target)])
        assert result.exit_code == 0
        text = json.dumps(json.loads(target.read_text()))
        assert "pidash hooks run" not in text
        assert "notify.py" in text
