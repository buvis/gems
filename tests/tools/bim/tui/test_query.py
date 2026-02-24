from __future__ import annotations

import pytest
from bim.tui.query import QueryTuiApp
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
