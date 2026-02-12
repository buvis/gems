"""Tests for safe_rglob symlink-safe recursive globbing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from buvis.pybase.filesystem.dir_tree.safe_rglob import is_safe_path, safe_rglob


class TestIsSafePath:
    """Tests for is_safe_path function."""

    def test_oserror_returns_false(self, tmp_path: Path) -> None:
        """OSError during resolution returns False (lines 32-33)."""
        mock_path = MagicMock(spec=Path)
        mock_path.is_symlink.side_effect = OSError("Permission denied")

        result = is_safe_path(mock_path, [tmp_path])
        assert result is False

    def test_runtimeerror_returns_false(self, tmp_path: Path) -> None:
        """RuntimeError (e.g., symlink loop) returns False."""
        mock_path = MagicMock(spec=Path)
        mock_path.is_symlink.return_value = False
        mock_path.resolve.side_effect = RuntimeError("Symlink loop")

        result = is_safe_path(mock_path, [tmp_path])
        assert result is False

    def test_broken_symlink_returns_false(self, tmp_path: Path) -> None:
        """Broken symlink returns False."""
        broken_link = tmp_path / "broken"
        broken_link.symlink_to(tmp_path / "nonexistent")

        result = is_safe_path(broken_link, [tmp_path])
        assert result is False

    def test_path_outside_allowed_returns_false(self, tmp_path: Path) -> None:
        """Path outside allowed bases returns False."""
        outside_path = tmp_path.parent / "outside"
        outside_path.mkdir(exist_ok=True)
        try:
            result = is_safe_path(outside_path, [tmp_path])
            assert result is False
        finally:
            outside_path.rmdir()

    def test_valid_path_inside_allowed_returns_true(self, tmp_path: Path) -> None:
        """Valid path inside allowed bases returns True."""
        inside = tmp_path / "inside.txt"
        inside.write_text("test")

        result = is_safe_path(inside, [tmp_path])
        assert result is True


class TestSafeRglob:
    """Tests for safe_rglob function."""

    def test_yields_files_inside_directory(self, tmp_path: Path) -> None:
        """Yields paths that are inside the directory."""
        (tmp_path / "file1.txt").write_text("ok")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file2.txt").write_text("ok")

        results = list(safe_rglob(tmp_path, "*.txt"))
        assert len(results) == 2
        assert tmp_path / "file1.txt" in results
        assert tmp_path / "subdir" / "file2.txt" in results

    def test_skips_broken_symlinks(self, tmp_path: Path) -> None:
        """Skips broken symlinks."""
        (tmp_path / "valid.txt").write_text("ok")
        (tmp_path / "broken").symlink_to(tmp_path / "nonexistent")

        results = list(safe_rglob(tmp_path))
        result_names = [p.name for p in results]
        assert "valid.txt" in result_names
        assert "broken" not in result_names
