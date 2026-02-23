from __future__ import annotations

import pytest
from bim.tui.query import KanbanCard, KanbanLane, KanbanTuiApp
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
