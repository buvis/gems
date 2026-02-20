from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fren.commands.directorize.directorize import CommandDirectorize


class TestDirectorizeBasic:
    def test_wraps_file_in_directory(self, tmp_path: Path) -> None:
        source = tmp_path / "report.pdf"
        source.write_text("x")

        result = CommandDirectorize(directory=str(tmp_path)).execute()

        assert (tmp_path / "report" / "report.pdf").exists()
        assert result.output == "Directorized 1 file(s)"

    def test_multiple_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        CommandDirectorize(directory=str(tmp_path)).execute()

        assert (tmp_path / "a" / "a.txt").exists()
        assert (tmp_path / "b" / "b.txt").exists()

    def test_skips_hidden_files(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".DS_Store"
        hidden.write_text("x")

        result = CommandDirectorize(directory=str(tmp_path)).execute()

        assert hidden.exists()
        assert result.output == "Directorized 0 file(s)"

    def test_skips_directories(self, tmp_path: Path) -> None:
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "inside.txt").write_text("x")

        result = CommandDirectorize(directory=str(tmp_path)).execute()

        assert (tmp_path / "subdir" / "inside.txt").exists()
        assert result.output == "Directorized 0 file(s)"


class TestDirectorizeCollision:
    def test_existing_destination_warns(self, tmp_path: Path) -> None:
        source = tmp_path / "report.pdf"
        source.write_text("x")
        existing_dir = tmp_path / "report"
        existing_dir.mkdir()
        (existing_dir / "report.pdf").write_text("existing")

        result = CommandDirectorize(directory=str(tmp_path)).execute()

        assert source.exists()
        assert any("Destination exists, skipped" in warning for warning in result.warnings)

    def test_target_name_is_existing_file_warns(self, tmp_path: Path) -> None:
        (tmp_path / "report.pdf").write_text("x")
        (tmp_path / "report").write_text("blocker")  # file, not dir

        result = CommandDirectorize(directory=str(tmp_path)).execute()

        assert any("Failed to directorize" in w for w in result.warnings)


class TestDirectorizeErrors:
    def test_permission_error_warns(self, tmp_path: Path) -> None:
        source = tmp_path / "report.pdf"
        source.write_text("x")

        with patch(
            "fren.commands.directorize.directorize.Path.mkdir",
            side_effect=PermissionError("denied"),
        ):
            result = CommandDirectorize(directory=str(tmp_path)).execute()

        assert any("Failed to directorize report.pdf" in warning for warning in result.warnings)
