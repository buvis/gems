from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from bim.tui.edit_note import EditNoteApp, EditScreen, _gather_changes
from textual.app import App, ComposeResult
from textual.widgets import Button, Checkbox, Input, Select


def _fake_zettel_data(
    metadata: dict[str, Any] | None = None,
) -> MagicMock:
    data = MagicMock()
    data.metadata = metadata or {
        "title": "Test Note",
        "type": "note",
        "tags": ["tag1", "tag2"],
        "processed": False,
        "publish": False,
    }
    data.reference = {}
    data.sections = [("body", "Some content")]
    return data


class EditHost(App[dict[str, Any] | None]):
    """Host app for testing EditScreen modal."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self.result: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        yield Button("trigger")

    def on_mount(self) -> None:
        self.push_screen(EditScreen(self._path), callback=self._on_result)

    def _on_result(self, value: dict[str, Any] | None) -> None:
        self.result = value
        self.exit()


class TestGatherChanges:
    def test_no_changes(self):
        original = {"title": "T", "type": "note", "tags": ["a"], "processed": False, "publish": False}
        query_one = MagicMock()

        title_input = MagicMock(spec=Input)
        title_input.value = "T"
        type_select = MagicMock(spec=Select)
        type_select.value = "note"
        tags_input = MagicMock(spec=Input)
        tags_input.value = "a"
        processed_cb = MagicMock(spec=Checkbox)
        processed_cb.value = False
        publish_cb = MagicMock(spec=Checkbox)
        publish_cb.value = False

        def side_effect(selector, cls):
            return {
                "#edit-title": title_input,
                "#edit-type": type_select,
                "#edit-tags": tags_input,
                "#edit-processed": processed_cb,
                "#edit-publish": publish_cb,
            }[selector]

        query_one.side_effect = side_effect
        assert _gather_changes(query_one, original) == {}

    def test_title_changed(self):
        original = {"title": "Old", "type": "note", "tags": [], "processed": False, "publish": False}
        query_one = MagicMock()

        title_input = MagicMock(spec=Input)
        title_input.value = "New"
        type_select = MagicMock(spec=Select)
        type_select.value = "note"
        tags_input = MagicMock(spec=Input)
        tags_input.value = ""
        processed_cb = MagicMock(spec=Checkbox)
        processed_cb.value = False
        publish_cb = MagicMock(spec=Checkbox)
        publish_cb.value = False

        def side_effect(selector, cls):
            return {
                "#edit-title": title_input,
                "#edit-type": type_select,
                "#edit-tags": tags_input,
                "#edit-processed": processed_cb,
                "#edit-publish": publish_cb,
            }[selector]

        query_one.side_effect = side_effect
        changes = _gather_changes(query_one, original)
        assert changes == {"title": "New"}


class TestEditNoteApp:
    @pytest.mark.anyio
    async def test_form_renders_fields(self, mocker):
        fake_data = _fake_zettel_data()
        mocker.patch(
            "bim.tui.edit_note.get_repo"
        ).return_value.find_by_location.return_value.get_data.return_value = fake_data
        mocker.patch("bim.tui.edit_note.get_formatter").return_value = MagicMock()
        mocker.patch("bim.tui.edit_note.PrintZettelUseCase").return_value.execute.return_value = "preview"

        app = EditNoteApp(Path("/tmp/test.md"))
        async with app.run_test(size=(80, 30)) as pilot:
            await pilot.pause()
            title = app.query_one("#edit-title", Input)
            assert title.value == "Test Note"
            tags = app.query_one("#edit-tags", Input)
            assert tags.value == "tag1, tag2"

    @pytest.mark.anyio
    async def test_cancel_exits(self, mocker):
        fake_data = _fake_zettel_data()
        mocker.patch(
            "bim.tui.edit_note.get_repo"
        ).return_value.find_by_location.return_value.get_data.return_value = fake_data
        mocker.patch("bim.tui.edit_note.get_formatter").return_value = MagicMock()
        mocker.patch("bim.tui.edit_note.PrintZettelUseCase").return_value.execute.return_value = "preview"

        app = EditNoteApp(Path("/tmp/test.md"))
        async with app.run_test(size=(80, 30)) as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()


class TestEditScreen:
    @pytest.mark.anyio
    async def test_cancel_dismisses_none(self, mocker):
        fake_data = _fake_zettel_data()
        mocker.patch(
            "bim.tui.edit_note.get_repo"
        ).return_value.find_by_location.return_value.get_data.return_value = fake_data
        mocker.patch("bim.tui.edit_note.get_formatter").return_value = MagicMock()
        mocker.patch("bim.tui.edit_note.PrintZettelUseCase").return_value.execute.return_value = "preview"

        app = EditHost(Path("/tmp/test.md"))
        async with app.run_test(size=(100, 50)) as pilot:
            await pilot.pause()
            await pilot.click("#cancel-btn")
            await pilot.pause()
        assert app.result is None
