from __future__ import annotations

from pathlib import Path

import pytest
from bim.tui.query import KanbanCard, KanbanLane, KanbanTuiApp
from buvis.pybase.result import CommandResult
from textual.widgets import Input


def _sample_rows():
    return [
        {"title": "Task A", "status": "todo", "file_path": "/tmp/a.md"},
        {"title": "Task B", "status": "todo", "file_path": "/tmp/b.md"},
        {"title": "Task C", "status": "done", "file_path": "/tmp/c.md"},
    ]


def _sample_columns():
    return ["title", "status", "file_path"]


class TestKanbanTuiApp:
    @pytest.mark.anyio
    async def test_lanes_grouped_on_mount(self):
        app = KanbanTuiApp(
            rows=_sample_rows(),
            columns=_sample_columns(),
            group_by="status",
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            lanes = app.query(KanbanLane)
            lane_titles = {lane._title for lane in lanes}
            assert "todo" in lane_titles
            assert "done" in lane_titles

    @pytest.mark.anyio
    async def test_lane_card_counts(self):
        app = KanbanTuiApp(
            rows=_sample_rows(),
            columns=_sample_columns(),
            group_by="status",
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            for lane in app.query(KanbanLane):
                if lane._title == "todo":
                    assert len(lane._lane_rows) == 2
                elif lane._title == "done":
                    assert len(lane._lane_rows) == 1

    @pytest.mark.anyio
    async def test_filter_rebuilds_lanes(self):
        app = KanbanTuiApp(
            rows=_sample_rows(),
            columns=_sample_columns(),
            group_by="status",
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            inp = app.query_one(Input)
            inp.value = "Task C"
            await pilot.pause()
            lanes = list(app.query(KanbanLane))
            # Only "done" lane should remain
            assert len(lanes) == 1
            assert lanes[0]._title == "done"

    @pytest.mark.anyio
    async def test_clear_filter_restores_lanes(self):
        app = KanbanTuiApp(
            rows=_sample_rows(),
            columns=_sample_columns(),
            group_by="status",
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            inp = app.query_one(Input)
            inp.value = "Task C"
            await pilot.pause()
            assert len(list(app.query(KanbanLane))) == 1

            inp.value = ""
            await pilot.pause()
            assert len(list(app.query(KanbanLane))) == 2

    @pytest.mark.anyio
    async def test_card_stores_row_data(self):
        app = KanbanTuiApp(
            rows=_sample_rows(),
            columns=_sample_columns(),
            group_by="status",
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            cards = list(app.query(KanbanCard))
            assert len(cards) == 3
            file_paths = {card.row["file_path"] for card in cards}
            assert "/tmp/a.md" in file_paths
            assert "/tmp/b.md" in file_paths
            assert "/tmp/c.md" in file_paths


class TestKanbanTuiAppNotifications:
    @pytest.mark.anyio
    async def test_archive_failure_notifies_error_severity(self, mocker):
        mocker.patch("bim.tui.query.get_repo")
        mock_command = mocker.patch("bim.commands.archive_note.archive_note.CommandArchiveNote")
        mock_command.return_value.execute.return_value = CommandResult(success=False, error="Archive failed")

        app = KanbanTuiApp(
            rows=_sample_rows(),
            columns=_sample_columns(),
            group_by="status",
            archive_dir=Path("/tmp/archive"),
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            notify_mock = mocker.patch.object(app, "notify")
            app._pending_archive_path = "/tmp/a.md"
            app._on_archive_confirmed(True)
            await pilot.pause()

        notify_mock.assert_any_call("Archive failed", severity="error")
        assert any(row["file_path"] == "/tmp/a.md" for row in app._rows)

    @pytest.mark.anyio
    async def test_archive_success_notifies_information_and_warning_severity_and_removes_row(self, mocker):
        mocker.patch("bim.tui.query.get_repo")
        mock_command = mocker.patch("bim.commands.archive_note.archive_note.CommandArchiveNote")
        mock_command.return_value.execute.return_value = CommandResult(
            success=True,
            output="Archived a.md",
            warnings=["ghost.md doesn't exist"],
        )

        app = KanbanTuiApp(
            rows=_sample_rows(),
            columns=_sample_columns(),
            group_by="status",
            archive_dir=Path("/tmp/archive"),
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            notify_mock = mocker.patch.object(app, "notify")
            app._pending_archive_path = "/tmp/a.md"
            app._on_archive_confirmed(True)
            await pilot.pause()

        notify_mock.assert_any_call("Archived a.md", severity="information")
        notify_mock.assert_any_call("ghost.md doesn't exist", severity="warning")
        assert not any(row["file_path"] == "/tmp/a.md" for row in app._rows)

    @pytest.mark.anyio
    async def test_delete_failure_notifies_error_severity(self, mocker):
        mocker.patch("bim.tui.query.get_repo")
        mock_command = mocker.patch("bim.commands.delete_note.delete_note.CommandDeleteNote")
        mock_command.return_value.execute.return_value = CommandResult(success=False, error="Deletion failed")

        app = KanbanTuiApp(rows=_sample_rows(), columns=_sample_columns(), group_by="status")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            notify_mock = mocker.patch.object(app, "notify")
            app._pending_delete_path = "/tmp/a.md"
            app._on_delete_confirmed(True)
            await pilot.pause()

        notify_mock.assert_any_call("Deletion failed", severity="error")
        assert any(row["file_path"] == "/tmp/a.md" for row in app._rows)

    @pytest.mark.anyio
    async def test_delete_success_with_warning_notifies_warning_severity_and_deleted_toast(self, mocker):
        mocker.patch("bim.tui.query.get_repo")
        mock_command = mocker.patch("bim.commands.delete_note.delete_note.CommandDeleteNote")
        mock_command.return_value.execute.return_value = CommandResult(
            success=True,
            metadata={"deleted_count": 1},
            warnings=["ghost.md doesn't exist"],
        )

        app = KanbanTuiApp(rows=_sample_rows(), columns=_sample_columns(), group_by="status")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            notify_mock = mocker.patch.object(app, "notify")
            app._pending_delete_path = "/tmp/a.md"
            app._on_delete_confirmed(True)
            await pilot.pause()

        notify_mock.assert_any_call("ghost.md doesn't exist", severity="warning")
        notify_mock.assert_any_call("Deleted a.md")
        assert not any(row["file_path"] == "/tmp/a.md" for row in app._rows)

    @pytest.mark.anyio
    async def test_format_failure_notifies_error_severity(self, mocker):
        mocker.patch("bim.tui.query.get_repo")
        mocker.patch("bim.dependencies.get_formatter")
        mock_command = mocker.patch("bim.commands.format_note.format_note.CommandFormatNote")
        mock_command.return_value.execute.return_value = CommandResult(success=False, error="Formatting failed")

        app = KanbanTuiApp(rows=_sample_rows(), columns=_sample_columns(), group_by="status")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            card = next(c for c in app.query(KanbanCard) if c.row["file_path"] == "/tmp/a.md")
            card.focus()
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

        app = KanbanTuiApp(rows=_sample_rows(), columns=_sample_columns(), group_by="status")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            card = next(c for c in app.query(KanbanCard) if c.row["file_path"] == "/tmp/a.md")
            card.focus()
            await pilot.pause()
            notify_mock = mocker.patch.object(app, "notify")
            app.action_format()
            await pilot.pause()

        notify_mock.assert_any_call("stray.md doesn't exist", severity="warning")
        notify_mock.assert_any_call("Formatted a.md")
