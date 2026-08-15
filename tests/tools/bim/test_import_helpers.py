from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bim.shared.import_helpers import interactive_import
from pytest_mock import MockerFixture


def _make_note(note_id: str = "202401151030") -> MagicMock:
    note = MagicMock()
    note.type = "note"
    note.id = note_id
    note.tags = ["test"]
    note.data = MagicMock()
    note.data.metadata = {}
    note.get_data.return_value = MagicMock()
    return note


class TestInteractiveImport:
    def test_overwrite_write_failure_leaves_existing_note_untouched(
        self,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """os.replace failure during the atomic write leaves the pre-existing note byte-for-byte intact."""
        path_note = tmp_path / "source.md"
        path_note.write_text("# Original", encoding="utf-8")

        path_zettelkasten = tmp_path / "zettelkasten"
        path_zettelkasten.mkdir()

        note = _make_note()
        output_path = path_zettelkasten / f"{note.id}.md"
        output_path.write_text("old content", encoding="utf-8")

        mock_console = mocker.patch("bim.shared.import_helpers.console")
        mock_console.confirm.side_effect = [True, True]

        mock_reader_cls = mocker.patch("buvis.pybase.zettel.ReadZettelUseCase")
        mock_reader_cls.return_value.execute.return_value = note

        mock_printer_cls = mocker.patch(
            "buvis.pybase.zettel.application.use_cases.print_zettel_use_case.PrintZettelUseCase"
        )
        mock_printer_cls.return_value.execute.return_value = "formatted content"

        mocker.patch("bim.dependencies.get_repo")
        mocker.patch("bim.dependencies.get_formatter")

        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=OSError("disk full"),
        )

        global_settings = MagicMock()
        global_settings.ollama_model = None

        with pytest.raises(OSError):
            interactive_import(path_note, path_zettelkasten, global_settings)

        assert output_path.read_text(encoding="utf-8") == "old content"
