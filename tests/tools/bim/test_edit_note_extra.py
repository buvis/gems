from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bim.commands.edit_note.edit_note import CommandEditNote
from bim.params.edit_note import EditNoteParams


class TestCommandEditNoteExtra:
    def test_no_changes_returns_error(self) -> None:
        mock_repo = MagicMock()
        params = EditNoteParams(paths=[Path("/tmp/note.md")], changes=None)
        cmd = CommandEditNote(params=params, repo=mock_repo)
        result = cmd.execute()

        assert result.success is False
        assert result.error == "No changes provided"

    def test_no_results_no_warnings(self, tmp_path: Path) -> None:
        """All paths are files but none produce results (shouldn't happen, but covers the branch)."""
        mock_repo = MagicMock()
        missing = tmp_path / "gone.md"
        params = EditNoteParams(paths=[missing], changes={"title": "X"})
        cmd = CommandEditNote(params=params, repo=mock_repo)
        result = cmd.execute()

        assert result.success is False
        assert len(result.warnings) > 0

    def test_mixed_existing_and_missing(self, tmp_path: Path) -> None:
        existing = tmp_path / "exists.md"
        existing.write_text("---\ntitle: T\n---\n")
        missing = tmp_path / "missing.md"

        mock_repo = MagicMock()
        mock_zettel = MagicMock()
        mock_repo.find_by_location.return_value = mock_zettel

        with patch("bim.commands.edit_note.edit_note.UpdateZettelUseCase"):
            params = EditNoteParams(paths=[existing, missing], changes={"title": "New"})
            cmd = CommandEditNote(params=params, repo=mock_repo)
            result = cmd.execute()

        assert result.success is True
        assert result.metadata["updated_count"] == 1
        assert any("missing.md" in w for w in result.warnings)
