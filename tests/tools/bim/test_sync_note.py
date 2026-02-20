from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bim.commands.sync_note.sync_note import CommandSyncNote, _extract_issue_key
from bim.params.sync_note import SyncNoteParams
from buvis.pybase.result import CommandResult
from buvis.pybase.zettel.domain.entities import ProjectZettel


@pytest.fixture
def zettel_file(tmp_path: Path, minimal_zettel: str) -> Path:
    p = tmp_path / "202401151030 Test project.md"
    p.write_text(minimal_zettel, encoding="utf-8")
    return p


class TestExtractIssueKey:
    def test_extracts_key_from_markdown_link(self) -> None:
        assert _extract_issue_key("[PROJ-123](https://jira.example.com/browse/PROJ-123)") == "PROJ-123"

    def test_returns_none_for_plain_text(self) -> None:
        assert _extract_issue_key("do-not-track") is None

    def test_returns_none_for_empty_brackets(self) -> None:
        assert _extract_issue_key("[]()") is None

    def test_returns_none_for_empty_string(self) -> None:
        assert _extract_issue_key("") is None


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

    def test_linked_project_updates_description(self, zettel_file: Path, mocker) -> None:
        project = MagicMock(spec=ProjectZettel)
        project.us = "[PROJ-42](https://jira.example.com/browse/PROJ-42)"

        mock_adapter = MagicMock()
        mock_adapter.update_description_from_project.return_value = True
        mocker.patch(
            "bim.commands.sync_note.sync_note.ZettelJiraAdapter",
            return_value=mock_adapter,
        )
        mock_reader = MagicMock()
        mock_reader.execute.return_value = project
        mocker.patch(
            "bim.commands.sync_note.sync_note.ReadZettelUseCase",
            return_value=mock_reader,
        )

        params = SyncNoteParams(paths=[zettel_file], target_system="jira")
        cmd = CommandSyncNote(
            params=params,
            jira_adapter_config={},
            repo=MagicMock(),
            formatter=MagicMock(),
        )
        result = cmd.execute()

        assert result.success is True
        assert "Description updated for PROJ-42" in result.output
        assert result.metadata["synced_count"] == 1
        mock_adapter.update_description_from_project.assert_called_once_with("PROJ-42", project)

    def test_linked_project_already_in_sync(self, zettel_file: Path, mocker) -> None:
        project = MagicMock(spec=ProjectZettel)
        project.us = "[PROJ-42](https://jira.example.com/browse/PROJ-42)"

        mock_adapter = MagicMock()
        mock_adapter.update_description_from_project.return_value = False
        mocker.patch(
            "bim.commands.sync_note.sync_note.ZettelJiraAdapter",
            return_value=mock_adapter,
        )
        mock_reader = MagicMock()
        mock_reader.execute.return_value = project
        mocker.patch(
            "bim.commands.sync_note.sync_note.ReadZettelUseCase",
            return_value=mock_reader,
        )

        params = SyncNoteParams(paths=[zettel_file], target_system="jira")
        cmd = CommandSyncNote(
            params=params,
            jira_adapter_config={},
            repo=MagicMock(),
            formatter=MagicMock(),
        )
        result = cmd.execute()

        assert result.success is True
        assert "Already in sync with PROJ-42" in result.output
        assert result.metadata["synced_count"] == 0
