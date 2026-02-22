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

    def test_non_project_zettel_warns(self, zettel_file: Path, mocker) -> None:
        """A zettel that is not a ProjectZettel produces a warning."""
        note = MagicMock()  # not spec=ProjectZettel
        note.__class__ = type("NoteZettel", (), {})

        mock_reader = MagicMock()
        mock_reader.execute.return_value = note
        mocker.patch(
            "bim.commands.sync_note.sync_note.ReadZettelUseCase",
            return_value=mock_reader,
        )
        mocker.patch(
            "bim.commands.sync_note.sync_note.ZettelJiraAdapter",
            return_value=MagicMock(),
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
        assert any("not a project" in w for w in result.warnings)

    def test_ignore_flag_default(self, zettel_file: Path, mocker) -> None:
        """Project with us == default ignore label is skipped."""
        project = MagicMock(spec=ProjectZettel)
        project.us = "do-not-track"

        mock_reader = MagicMock()
        mock_reader.execute.return_value = project
        mocker.patch(
            "bim.commands.sync_note.sync_note.ReadZettelUseCase",
            return_value=mock_reader,
        )
        mocker.patch(
            "bim.commands.sync_note.sync_note.ZettelJiraAdapter",
            return_value=MagicMock(),
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
        assert any("ignore Jira" in w for w in result.warnings)

    def test_ignore_flag_custom(self, zettel_file: Path, mocker) -> None:
        """Custom ignore label from config is respected."""
        project = MagicMock(spec=ProjectZettel)
        project.us = "skip-jira"

        mock_reader = MagicMock()
        mock_reader.execute.return_value = project
        mocker.patch(
            "bim.commands.sync_note.sync_note.ReadZettelUseCase",
            return_value=mock_reader,
        )
        mocker.patch(
            "bim.commands.sync_note.sync_note.ZettelJiraAdapter",
            return_value=MagicMock(),
        )

        params = SyncNoteParams(paths=[zettel_file], target_system="jira")
        cmd = CommandSyncNote(
            params=params,
            jira_adapter_config={"ignore": "skip-jira"},
            repo=MagicMock(),
            formatter=MagicMock(),
        )
        result = cmd.execute()

        assert result.success is True
        assert any("ignore Jira" in w for w in result.warnings)

    def test_unparseable_issue_key_warns(self, zettel_file: Path, mocker) -> None:
        """us field that has content but can't be parsed as [KEY](url) warns."""
        project = MagicMock(spec=ProjectZettel)
        project.us = "not-a-link"

        mock_reader = MagicMock()
        mock_reader.execute.return_value = project
        mocker.patch(
            "bim.commands.sync_note.sync_note.ReadZettelUseCase",
            return_value=mock_reader,
        )
        mocker.patch(
            "bim.commands.sync_note.sync_note.ZettelJiraAdapter",
            return_value=MagicMock(),
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
        assert any("Can't parse issue key" in w for w in result.warnings)

    def test_create_new_jira_issue(self, zettel_file: Path, mocker) -> None:
        """Project without us field creates a new Jira issue."""
        project = MagicMock(spec=ProjectZettel)
        project.us = None

        mock_reader = MagicMock()
        mock_reader.execute.return_value = project
        mocker.patch(
            "bim.commands.sync_note.sync_note.ReadZettelUseCase",
            return_value=mock_reader,
        )

        new_issue = MagicMock()
        new_issue.id = "PROJ-99"
        new_issue.link = "https://jira.example.com/browse/PROJ-99"

        mock_adapter = MagicMock()
        mock_adapter.create_from_project.return_value = new_issue
        mocker.patch(
            "bim.commands.sync_note.sync_note.ZettelJiraAdapter",
            return_value=mock_adapter,
        )

        mock_printer = MagicMock()
        mock_printer.execute.return_value = "formatted note"
        mocker.patch(
            "bim.commands.sync_note.sync_note.PrintZettelUseCase",
            return_value=mock_printer,
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
        assert "PROJ-99" in result.output
        assert result.metadata["synced_count"] == 1
        project.add_log_entry.assert_called_once()
        assert project.us == "[PROJ-99](https://jira.example.com/browse/PROJ-99)"
        assert zettel_file.read_text(encoding="utf-8") == "formatted note"

    def test_create_new_issue_empty_us(self, zettel_file: Path, mocker) -> None:
        """Project with empty string us also creates a new issue (falsy)."""
        project = MagicMock(spec=ProjectZettel)
        project.us = ""

        mock_reader = MagicMock()
        mock_reader.execute.return_value = project
        mocker.patch(
            "bim.commands.sync_note.sync_note.ReadZettelUseCase",
            return_value=mock_reader,
        )

        new_issue = MagicMock()
        new_issue.id = "PROJ-100"
        new_issue.link = "https://jira.example.com/browse/PROJ-100"

        mock_adapter = MagicMock()
        mock_adapter.create_from_project.return_value = new_issue
        mocker.patch(
            "bim.commands.sync_note.sync_note.ZettelJiraAdapter",
            return_value=mock_adapter,
        )

        mock_printer = MagicMock()
        mock_printer.execute.return_value = "formatted"
        mocker.patch(
            "bim.commands.sync_note.sync_note.PrintZettelUseCase",
            return_value=mock_printer,
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
        assert "PROJ-100" in result.output
        assert result.metadata["synced_count"] == 1

    def test_multiple_paths_mixed(self, tmp_path: Path, mocker) -> None:
        """Multiple paths: one missing, one non-project, one synced."""
        missing = tmp_path / "missing.md"
        existing = tmp_path / "project.md"
        existing.write_text("---\ntitle: P\n---\n", encoding="utf-8")

        non_project = MagicMock()
        non_project.__class__ = type("NoteZettel", (), {})

        mock_reader = MagicMock()
        mock_reader.execute.return_value = non_project
        mocker.patch(
            "bim.commands.sync_note.sync_note.ReadZettelUseCase",
            return_value=mock_reader,
        )
        mocker.patch(
            "bim.commands.sync_note.sync_note.ZettelJiraAdapter",
            return_value=MagicMock(),
        )

        params = SyncNoteParams(paths=[missing, existing], target_system="jira")
        cmd = CommandSyncNote(
            params=params,
            jira_adapter_config={},
            repo=MagicMock(),
            formatter=MagicMock(),
        )
        result = cmd.execute()

        assert result.success is True
        assert len(result.warnings) == 2
        assert result.metadata["synced_count"] == 0
