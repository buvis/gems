from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from buvis.pybase.zettel.domain.templates import Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from textual.widgets import Button, Input, Select


def _make_template(name: str = "note", questions: list[Question] | None = None):
    tmpl = MagicMock()
    tmpl.name = name
    tmpl.questions.return_value = questions or []
    tmpl.build_data.return_value = ZettelData(
        metadata={"title": "T", "type": name, "tags": []},
    )
    return tmpl


class TestCreateNoteApp:
    @pytest.mark.anyio
    async def test_compose_renders_form(self, mocker):
        mocker.patch(
            "bim.tui.create_note.get_templates",
            return_value={"note": _make_template()},
        )
        mocker.patch("bim.tui.create_note.get_formatter").return_value = MagicMock()
        mocker.patch("bim.tui.create_note.PrintZettelUseCase").return_value.execute.return_value = "preview"

        from bim.tui.create_note import CreateNoteApp

        app = CreateNoteApp(path_zettelkasten=Path("/tmp/zk"))
        async with app.run_test(size=(80, 30)) as pilot:
            await pilot.pause()
            assert app.query_one("#template-select", Select) is not None
            assert app.query_one("#title-input", Input) is not None
            assert app.query_one("#tags-input", Input) is not None
            # Create button disabled by default (no title)
            btn = app.query_one("#create-btn", Button)
            assert btn.disabled is True

    @pytest.mark.anyio
    async def test_preselected_type_populates(self, mocker):
        mocker.patch(
            "bim.tui.create_note.get_templates",
            return_value={"note": _make_template()},
        )
        mocker.patch("bim.tui.create_note.get_formatter").return_value = MagicMock()
        mocker.patch("bim.tui.create_note.PrintZettelUseCase").return_value.execute.return_value = "preview"
        mocker.patch(
            "buvis.pybase.zettel.domain.services.zettel_factory.ZettelFactory"
        ).create.return_value = MagicMock()
        mocker.patch(
            "buvis.pybase.zettel.domain.entities.zettel.zettel.Zettel"
        ).return_value.get_data.return_value = ZettelData()

        from bim.tui.create_note import CreateNoteApp

        app = CreateNoteApp(
            path_zettelkasten=Path("/tmp/zk"),
            preselected_type="note",
            preselected_title="My Title",
        )
        async with app.run_test(size=(80, 30)) as pilot:
            await pilot.pause()
            title_input = app.query_one("#title-input", Input)
            assert title_input.value == "My Title"

    @pytest.mark.anyio
    async def test_cancel_exits(self, mocker):
        mocker.patch(
            "bim.tui.create_note.get_templates",
            return_value={"note": _make_template()},
        )
        mocker.patch("bim.tui.create_note.get_formatter").return_value = MagicMock()

        from bim.tui.create_note import CreateNoteApp

        app = CreateNoteApp(path_zettelkasten=Path("/tmp/zk"))
        async with app.run_test(size=(80, 30)) as pilot:
            await pilot.pause()
            await pilot.click("#cancel-btn")
            await pilot.pause()

    @pytest.mark.anyio
    async def test_gather_answers_collects_form_values(self, mocker):
        mocker.patch(
            "bim.tui.create_note.get_templates",
            return_value={"note": _make_template()},
        )
        mocker.patch("bim.tui.create_note.get_formatter").return_value = MagicMock()
        mocker.patch("bim.tui.create_note.PrintZettelUseCase").return_value.execute.return_value = "preview"

        from bim.tui.create_note import CreateNoteApp

        app = CreateNoteApp(path_zettelkasten=Path("/tmp/zk"))
        async with app.run_test(size=(80, 40)) as pilot:
            await pilot.pause()
            title_input = app.query_one("#title-input", Input)
            title_input.value = "My Note"
            await pilot.pause()
            tags_input = app.query_one("#tags-input", Input)
            tags_input.value = "tag1, tag2"
            await pilot.pause()
            answers = app._gather_answers()
            assert answers["title"] == "My Note"
            assert answers["tags"] == "tag1, tag2"
