from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bim.commands.sync_note.sync_note import CommandSyncNote
from bim.params.sync_note import SyncNoteParams
from buvis.pybase.result import CommandResult


@pytest.fixture
def zettel_file(tmp_path: Path, minimal_zettel: str) -> Path:
    p = tmp_path / "202401151030 Test project.md"
    p.write_text(minimal_zettel, encoding="utf-8")
    return p


class TestCommandSyncNote:
    def test_unsupported_target_returns_failure(self, zettel_file: Path) -> None:
        params = SyncNoteParams(paths=[zettel_file], target_system="unsupported")
        cmd = CommandSyncNote(
            params=params,
            jira_adapter_config={},
            repo=MagicMock(),
            formatter=MagicMock(),
        )
        result = cmd.execute()

        assert isinstance(result, CommandResult)
        assert result.success is False
        assert "not supported" in result.error

    def test_missing_path_returns_warning(self, tmp_path: Path, mocker) -> None:
        missing = tmp_path / "nonexistent.md"
        params = SyncNoteParams(paths=[missing], target_system="jira")
        mocker.patch(
            "bim.commands.sync_note.sync_note.ZettelJiraAdapter",
            return_value=MagicMock(),
        )
        cmd = CommandSyncNote(
            params=params,
            jira_adapter_config={},
            repo=MagicMock(),
            formatter=MagicMock(),
        )
        result = cmd.execute()

        assert isinstance(result, CommandResult)
        assert result.success is True
        assert len(result.warnings) == 1
        assert "doesn't exist" in result.warnings[0]
