from __future__ import annotations

from pathlib import Path

import pytest
from bim.tui.query import QueryTuiApp
from buvis.pybase.result import CommandResult
from textual.widgets import DataTable, Input


def _sample_rows():
    return [
        {"title": "Alpha note", "type": "note", "file_path": "/tmp/alpha.md"},
        {"title": "Beta project", "type": "project", "file_path": "/tmp/beta.md"},
        {"title": "Gamma note", "type": "note", "file_path": "/tmp/gamma.md"},
    ]


def _sample_columns():
    return ["title", "type", "file_path"]


class TestQueryTuiApp:
    @pytest.mark.anyio
    async def test_table_populated_on_mount(self):
        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            table = app.query_one(DataTable)
            assert table.row_count == 3

    @pytest.mark.anyio
    async def test_display_columns_exclude_file_path(self):
        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert "file_path" not in app._display_columns
            assert "title" in app._display_columns

    @pytest.mark.anyio
    async def test_search_filters_rows(self):
        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            inp = app.query_one(Input)
            inp.value = "alpha"
            await pilot.pause()
            table = app.query_one(DataTable)
            assert table.row_count == 1

    @pytest.mark.anyio
    async def test_clear_search_restores_all_rows(self):
        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            inp = app.query_one(Input)
            inp.value = "alpha"
            await pilot.pause()
            assert app.query_one(DataTable).row_count == 1

            inp.value = ""
            await pilot.pause()
            assert app.query_one(DataTable).row_count == 3

    @pytest.mark.anyio
    async def test_search_by_type(self):
        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            inp = app.query_one(Input)
            inp.value = "project"
            await pilot.pause()
            table = app.query_one(DataTable)
            assert table.row_count == 1

    @pytest.mark.anyio
    async def test_search_case_insensitive(self):
        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            inp = app.query_one(Input)
            inp.value = "BETA"
            await pilot.pause()
            table = app.query_one(DataTable)
            assert table.row_count == 1

    @pytest.mark.anyio
    async def test_no_archive_without_dir(self):
        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns(), archive_dir=None)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            # Archive action should be a no-op when archive_dir is None
            table = app.query_one(DataTable)
            table.focus()
            await pilot.press("a")
            await pilot.pause()
            # No ConfirmScreen should be pushed — still 1 screen
            assert len(app.screen_stack) == 1


class TestQueryTuiAppNotifications:
    @pytest.mark.anyio
    async def test_archive_failure_notifies_error_severity(self, mocker):
        mocker.patch("bim.tui.query.get_repo")
        mock_command = mocker.patch("bim.commands.archive_note.archive_note.CommandArchiveNote")
        mock_command.return_value.execute.return_value = CommandResult(success=False, error="Archive failed")

        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns(), archive_dir=Path("/tmp/archive"))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            notify_mock = mocker.patch.object(app, "notify")
            app._pending_archive_path = "/tmp/alpha.md"
            app._on_archive_confirmed(True)
            await pilot.pause()

        notify_mock.assert_any_call("Archive failed", severity="error")
        assert any(row["file_path"] == "/tmp/alpha.md" for row in app._rows)

    @pytest.mark.anyio
    async def test_archive_success_notifies_information_and_warning_severity_and_removes_row(self, mocker):
        mocker.patch("bim.tui.query.get_repo")
        mock_command = mocker.patch("bim.commands.archive_note.archive_note.CommandArchiveNote")
        mock_command.return_value.execute.return_value = CommandResult(
            success=True,
            output="Archived alpha.md",
            warnings=["ghost.md doesn't exist"],
        )

        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns(), archive_dir=Path("/tmp/archive"))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            notify_mock = mocker.patch.object(app, "notify")
            app._pending_archive_path = "/tmp/alpha.md"
            app._on_archive_confirmed(True)
            await pilot.pause()

        notify_mock.assert_any_call("Archived alpha.md", severity="information")
        notify_mock.assert_any_call("ghost.md doesn't exist", severity="warning")
        assert not any(row["file_path"] == "/tmp/alpha.md" for row in app._rows)

    @pytest.mark.anyio
    async def test_delete_failure_notifies_error_severity(self, mocker):
        mocker.patch("bim.tui.query.get_repo")
        mock_command = mocker.patch("bim.commands.delete_note.delete_note.CommandDeleteNote")
        mock_command.return_value.execute.return_value = CommandResult(success=False, error="Deletion failed")

        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            notify_mock = mocker.patch.object(app, "notify")
            app._pending_delete_path = "/tmp/alpha.md"
            app._on_delete_confirmed(True)
            await pilot.pause()

        notify_mock.assert_any_call("Deletion failed", severity="error")
        assert any(row["file_path"] == "/tmp/alpha.md" for row in app._rows)

    @pytest.mark.anyio
    async def test_delete_success_with_warning_notifies_warning_severity_and_deleted_toast(self, mocker):
        mocker.patch("bim.tui.query.get_repo")
        mock_command = mocker.patch("bim.commands.delete_note.delete_note.CommandDeleteNote")
        mock_command.return_value.execute.return_value = CommandResult(
            success=True,
            metadata={"deleted_count": 1},
            warnings=["ghost.md doesn't exist"],
        )

        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            notify_mock = mocker.patch.object(app, "notify")
            app._pending_delete_path = "/tmp/alpha.md"
            app._on_delete_confirmed(True)
            await pilot.pause()

        notify_mock.assert_any_call("ghost.md doesn't exist", severity="warning")
        notify_mock.assert_any_call("Deleted alpha.md")
        assert not any(row["file_path"] == "/tmp/alpha.md" for row in app._rows)

    @pytest.mark.anyio
    async def test_format_failure_notifies_error_severity(self, mocker):
        mocker.patch("bim.tui.query.get_repo")
        mocker.patch("bim.dependencies.get_formatter")
        mock_command = mocker.patch("bim.commands.format_note.format_note.CommandFormatNote")
        mock_command.return_value.execute.return_value = CommandResult(success=False, error="Formatting failed")

        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            table = app.query_one(DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            notify_mock = mocker.patch.object(app, "notify")
            app.action_format()
            await pilot.pause()

        notify_mock.assert_any_call("Formatting failed", severity="error")

    @pytest.mark.anyio
    async def test_format_success_with_warning_notifies_warning_severity_and_formatted_toast(self, mocker):
        mocker.patch("bim.tui.query.get_repo")
        mocker.patch("bim.dependencies.get_formatter")
        mock_command = mocker.patch("bim.commands.format_note.format_note.CommandFormatNote")
        mock_command.return_value.execute.return_value = CommandResult(
            success=True,
            metadata={"original": "content"},
            warnings=["stray.md doesn't exist"],
        )

        app = QueryTuiApp(rows=_sample_rows(), columns=_sample_columns())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            table = app.query_one(DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            notify_mock = mocker.patch.object(app, "notify")
            app.action_format()
            await pilot.pause()

        notify_mock.assert_any_call("stray.md doesn't exist", severity="warning")
        notify_mock.assert_any_call("Formatted alpha.md")
