from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bim.commands.import_note.import_note import CommandImportNote


def _make_note(note_id: str | None = "202401151030") -> MagicMock:
    note = MagicMock()
    note.type = "note"
    note.id = note_id
    note.tags = ["test"]
    note.data = MagicMock()
    note.data.metadata = {}
    note.get_data.return_value = MagicMock()
    return note


@pytest.fixture
def note_file(tmp_path: Path) -> Path:
    path = tmp_path / "note.md"
    path.write_text("# Test", encoding="utf-8")
    return path


@pytest.fixture
def zettelkasten_dir(tmp_path: Path) -> Path:
    path = tmp_path / "zettelkasten"
    path.mkdir()
    return path


@pytest.fixture
def deps() -> tuple[MagicMock, MagicMock]:
    return MagicMock(), MagicMock()


class TestCommandImportNote:
    def test_missing_zettelkasten_raises(self, tmp_path: Path, deps: tuple[MagicMock, MagicMock]) -> None:
        repo, formatter = deps
        note = tmp_path / "note.md"
        note.write_text("# Test", encoding="utf-8")
        missing_dir = tmp_path / "missing"

        with pytest.raises(FileNotFoundError):
            CommandImportNote(
                paths=[note],
                path_zettelkasten=missing_dir,
                repo=repo,
                formatter=formatter,
            )

    def test_imports_note(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        deps: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, formatter = deps
        note = _make_note()

        with (
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.PrintZettelUseCase") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.execute.return_value = "formatted content"

            cmd = CommandImportNote(
                paths=[note_file],
                path_zettelkasten=zettelkasten_dir,
                repo=repo,
                formatter=formatter,
            )
            result = cmd.execute()

        output_path = zettelkasten_dir / f"{note.id}.md"
        assert result.success
        assert result.metadata["imported_count"] == 1
        assert output_path.is_file()
        assert output_path.read_text(encoding="utf-8") == "formatted content"

    def test_imports_project_sets_resources(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        deps: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, formatter = deps
        note = _make_note()
        note.type = "project"

        with (
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.PrintZettelUseCase") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.execute.return_value = "formatted content"

            cmd = CommandImportNote(
                paths=[note_file],
                path_zettelkasten=zettelkasten_dir,
                repo=repo,
                formatter=formatter,
            )
            cmd.execute()

        assert "project resources" in note.data.metadata["resources"]
        assert note_file.parent.resolve().as_uri() in note.data.metadata["resources"]

    def test_sets_tags(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        deps: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, formatter = deps
        note = _make_note()

        with (
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.PrintZettelUseCase") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.execute.return_value = "formatted content"

            cmd = CommandImportNote(
                paths=[note_file],
                path_zettelkasten=zettelkasten_dir,
                repo=repo,
                formatter=formatter,
                tags=["new"],
            )
            cmd.execute()

        assert note.tags == ["new"]

    def test_missing_file(
        self,
        tmp_path: Path,
        zettelkasten_dir: Path,
        deps: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, formatter = deps
        missing = tmp_path / "missing.md"

        cmd = CommandImportNote(
            paths=[missing],
            path_zettelkasten=zettelkasten_dir,
            repo=repo,
            formatter=formatter,
        )
        result = cmd.execute()

        assert not result.success
        assert f"{missing} doesn't exist" in result.warnings

    def test_missing_id(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        deps: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, formatter = deps
        note = _make_note(note_id=None)

        with (
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.PrintZettelUseCase") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note

            cmd = CommandImportNote(
                paths=[note_file],
                path_zettelkasten=zettelkasten_dir,
                repo=repo,
                formatter=formatter,
            )
            result = cmd.execute()

        assert not result.success
        assert f"Note at {note_file} has no ID, skipping" in result.warnings
        assert list(zettelkasten_dir.iterdir()) == []
        mock_formatter.assert_not_called()

    def test_force_overwrites(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        deps: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, formatter = deps
        note = _make_note()
        output_path = zettelkasten_dir / f"{note.id}.md"
        output_path.write_text("old", encoding="utf-8")

        with (
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.PrintZettelUseCase") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.execute.return_value = "formatted content"

            cmd = CommandImportNote(
                paths=[note_file],
                path_zettelkasten=zettelkasten_dir,
                repo=repo,
                formatter=formatter,
                force=True,
            )
            result = cmd.execute()

        assert result.success
        assert output_path.read_text(encoding="utf-8") == "formatted content"

    def test_raises_without_force(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        deps: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, formatter = deps
        note = _make_note()
        output_path = zettelkasten_dir / f"{note.id}.md"
        output_path.write_text("old", encoding="utf-8")

        with patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader:
            mock_reader.return_value.execute.return_value = note

            cmd = CommandImportNote(
                paths=[note_file],
                path_zettelkasten=zettelkasten_dir,
                repo=repo,
                formatter=formatter,
            )
            result = cmd.execute()

        assert not result.success
        assert f"{output_path} already exists" in result.warnings
        assert output_path.read_text(encoding="utf-8") == "old"

    def test_removes_original(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        deps: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, formatter = deps
        note = _make_note()

        with (
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.PrintZettelUseCase") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.execute.return_value = "formatted content"

            cmd = CommandImportNote(
                paths=[note_file],
                path_zettelkasten=zettelkasten_dir,
                repo=repo,
                formatter=formatter,
                remove_original=True,
            )
            result = cmd.execute()

        assert result.success
        assert not note_file.exists()

    def test_batch_imports_all(
        self,
        tmp_path: Path,
        zettelkasten_dir: Path,
        deps: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, formatter = deps
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A", encoding="utf-8")
        b.write_text("# B", encoding="utf-8")
        note_a = _make_note(note_id="1")
        note_b = _make_note(note_id="2")

        with (
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.PrintZettelUseCase") as mock_formatter,
        ):
            mock_reader.return_value.execute.side_effect = [note_a, note_b]
            mock_formatter.return_value.execute.return_value = "formatted content"

            cmd = CommandImportNote(
                paths=[a, b],
                path_zettelkasten=zettelkasten_dir,
                repo=repo,
                formatter=formatter,
            )
            result = cmd.execute()

        assert result.success
        assert result.metadata["imported_count"] == 2
        assert (zettelkasten_dir / "1.md").is_file()
        assert (zettelkasten_dir / "2.md").is_file()
