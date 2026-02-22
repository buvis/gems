from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from fren.cli import cli


class TestFrenCommands:
    @patch("fren.commands.slug.slug.CommandSlug")
    def test_slug_success(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        target = tmp_path / "test file.txt"
        target.write_text("content")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Renamed 1 file")
        runner = CliRunner()
        result = runner.invoke(cli, ["slug", str(target)])
        assert result.exit_code == 0

    @patch("fren.commands.directorize.directorize.CommandDirectorize")
    def test_directorize_success(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Wrapped 3 files")
        runner = CliRunner()
        result = runner.invoke(cli, ["directorize", str(tmp_path)])
        assert result.exit_code == 0

    @patch("fren.commands.flatten.flatten.CommandFlatten")
    def test_flatten_success(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        dst = tmp_path / "dst"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Flattened 5 files")
        runner = CliRunner()
        result = runner.invoke(cli, ["flatten", str(src), str(dst)])
        assert result.exit_code == 0

    @patch("fren.commands.normalize.normalize.CommandNormalize")
    def test_normalize_success(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Normalized 2 dirs")
        runner = CliRunner()
        result = runner.invoke(cli, ["normalize", str(tmp_path)])
        assert result.exit_code == 0

    @patch("fren.commands.slug.slug.CommandSlug")
    def test_slug_failure(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        target = tmp_path / "a.txt"
        target.write_text("x")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="permission denied")
        runner = CliRunner()
        result = runner.invoke(cli, ["slug", str(target)])
        assert result.exit_code == 0  # CLI prints failure but doesn't sys.exit
