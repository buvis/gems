from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bim.commands.import_note.import_note import CommandImportNote, import_single


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
def note_mocks() -> tuple[MagicMock, MagicMock]:
    note = MagicMock()
    note.type = "note"
    note.id = "202401151030"
    note.tags = ["test"]
    note.data = MagicMock()
    note.data.metadata = {}
    note.get_data.return_value = MagicMock()
    repo = MagicMock()
    return repo, note


class TestImportSingle:
    def test_imports_note(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        note_mocks: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, note = note_mocks

        with (
            patch("bim.commands.import_note.import_note.get_repo", return_value=repo),
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.MarkdownZettelFormatter") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.format.return_value = "formatted content"

            import_single(note_file, zettelkasten_dir, quiet=True)

        output_path = zettelkasten_dir / f"{note.id}.md"
        assert output_path.is_file()
        assert output_path.read_text(encoding="utf-8") == "formatted content"

    def test_imports_project_sets_resources(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        note_mocks: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, note = note_mocks
        note.type = "project"

        with (
            patch("bim.commands.import_note.import_note.get_repo", return_value=repo),
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.MarkdownZettelFormatter") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.format.return_value = "formatted content"

            import_single(note_file, zettelkasten_dir, quiet=True)

        assert "project resources" in note.data.metadata["resources"]
        assert note_file.parent.resolve().as_uri() in note.data.metadata["resources"]

    def test_sets_tags(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        note_mocks: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, note = note_mocks

        with (
            patch("bim.commands.import_note.import_note.get_repo", return_value=repo),
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.MarkdownZettelFormatter") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.format.return_value = "formatted content"

            import_single(note_file, zettelkasten_dir, tags=["new"], quiet=True)

        assert note.tags == ["new"]

    def test_force_overwrites(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        note_mocks: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, note = note_mocks
        output_path = zettelkasten_dir / f"{note.id}.md"
        output_path.write_text("old", encoding="utf-8")

        with (
            patch("bim.commands.import_note.import_note.get_repo", return_value=repo),
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.MarkdownZettelFormatter") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.format.return_value = "formatted content"

            import_single(note_file, zettelkasten_dir, force_overwrite=True, quiet=True)

        assert output_path.read_text(encoding="utf-8") == "formatted content"

    def test_raises_without_force(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        note_mocks: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, note = note_mocks
        output_path = zettelkasten_dir / f"{note.id}.md"
        output_path.write_text("old", encoding="utf-8")

        with (
            patch("bim.commands.import_note.import_note.get_repo", return_value=repo),
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.MarkdownZettelFormatter") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.format.return_value = "formatted content"

            with pytest.raises(FileExistsError):
                import_single(note_file, zettelkasten_dir, quiet=True)

    def test_removes_original(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        note_mocks: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, note = note_mocks

        with (
            patch("bim.commands.import_note.import_note.get_repo", return_value=repo),
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.MarkdownZettelFormatter") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.format.return_value = "formatted content"

            import_single(note_file, zettelkasten_dir, remove_original=True, quiet=True)

        assert not note_file.exists()

    def test_quiet_suppresses_console(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        note_mocks: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, note = note_mocks

        with (
            patch("bim.commands.import_note.import_note.get_repo", return_value=repo),
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.MarkdownZettelFormatter") as mock_formatter,
            patch("bim.commands.import_note.import_note.console") as mock_console,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.format.return_value = "formatted content"

            import_single(note_file, zettelkasten_dir, quiet=True)
            mock_console.success.assert_not_called()

    def test_returns_message(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        note_mocks: tuple[MagicMock, MagicMock],
    ) -> None:
        repo, note = note_mocks

        with (
            patch("bim.commands.import_note.import_note.get_repo", return_value=repo),
            patch("bim.commands.import_note.import_note.ReadZettelUseCase") as mock_reader,
            patch("bim.commands.import_note.import_note.MarkdownZettelFormatter") as mock_formatter,
        ):
            mock_reader.return_value.execute.return_value = note
            mock_formatter.return_value.format.return_value = "formatted content"

            msg = import_single(note_file, zettelkasten_dir, quiet=True)

        assert note_file.name in msg
        assert f"{note.id}.md" in msg


class TestCommandImportNote:
    def test_missing_zettelkasten_raises(self, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test", encoding="utf-8")
        missing_dir = tmp_path / "missing"

        with pytest.raises(FileNotFoundError):
            CommandImportNote(paths=[note], path_zettelkasten=missing_dir)

    def test_scripted_calls_import_single(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
    ) -> None:
        with patch("bim.commands.import_note.import_note.import_single") as mock_import:
            cmd = CommandImportNote(
                paths=[note_file],
                path_zettelkasten=zettelkasten_dir,
                tags=["tag"],
                force=True,
                remove_original=True,
                scripted=True,
            )
            cmd.execute()
            mock_import.assert_called_once_with(
                note_file,
                zettelkasten_dir,
                tags=["tag"],
                force_overwrite=True,
                remove_original=True,
            )

    def test_batch_imports_all(
        self,
        tmp_path: Path,
        zettelkasten_dir: Path,
    ) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A", encoding="utf-8")
        b.write_text("# B", encoding="utf-8")

        with patch("bim.commands.import_note.import_note.import_single") as mock_import:
            cmd = CommandImportNote(
                paths=[a, b],
                path_zettelkasten=zettelkasten_dir,
                scripted=True,
            )
            cmd.execute()
            assert mock_import.call_count == 2
            mock_import.assert_any_call(
                a, zettelkasten_dir, tags=None, force_overwrite=False, remove_original=False,
            )
            mock_import.assert_any_call(
                b, zettelkasten_dir, tags=None, force_overwrite=False, remove_original=False,
            )

    def test_batch_skips_missing(
        self,
        note_file: Path,
        zettelkasten_dir: Path,
        tmp_path: Path,
    ) -> None:
        missing = tmp_path / "missing.md"

        with (
            patch("bim.commands.import_note.import_note.import_single") as mock_import,
            patch("bim.commands.import_note.import_note.console") as mock_console,
        ):
            cmd = CommandImportNote(
                paths=[missing, note_file],
                path_zettelkasten=zettelkasten_dir,
                scripted=True,
            )
            cmd.execute()
            mock_console.failure.assert_called_once()
            mock_import.assert_called_once_with(
                note_file, zettelkasten_dir, tags=None, force_overwrite=False, remove_original=False,
            )
