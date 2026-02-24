from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from fren.cli import cli


class TestFrenCommands:
    @patch("fren.commands.slug.slug.CommandSlug")
    def test_slug_success(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        target = tmp_path / "test file.txt"
        target.write_text("content")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Renamed 1 file")
        result = runner.invoke(cli, ["slug", str(target)])
        assert result.exit_code == 0

    @patch("fren.commands.directorize.directorize.CommandDirectorize")
    def test_directorize_success(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Wrapped 3 files")
        result = runner.invoke(cli, ["directorize", str(tmp_path)])
        assert result.exit_code == 0

    @patch("fren.commands.flatten.flatten.CommandFlatten")
    def test_flatten_success(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        dst = tmp_path / "dst"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Flattened 5 files")
        result = runner.invoke(cli, ["flatten", str(src), str(dst)])
        assert result.exit_code == 0

    @patch("fren.commands.normalize.normalize.CommandNormalize")
    def test_normalize_success(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Normalized 2 dirs")
        result = runner.invoke(cli, ["normalize", str(tmp_path)])
        assert result.exit_code == 0

    @patch("fren.commands.slug.slug.CommandSlug")
    def test_slug_failure(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        target = tmp_path / "a.txt"
        target.write_text("x")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="permission denied")
        result = runner.invoke(cli, ["slug", str(target)])
        assert result.exit_code == 0  # CLI prints failure but doesn't sys.exit

    @patch("fren.commands.slug.slug.CommandSlug")
    def test_slug_with_warnings(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        target = tmp_path / "a.txt"
        target.write_text("x")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Renamed 1", warnings=["Path not found: missing"]
        )
        result = runner.invoke(cli, ["slug", str(target)])
        assert result.exit_code == 0

    @patch("fren.commands.slug.slug.CommandSlug")
    def test_slug_success_no_output(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        target = tmp_path / "a.txt"
        target.write_text("x")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        result = runner.invoke(cli, ["slug", str(target)])
        assert result.exit_code == 0

    @patch("fren.commands.slug.slug.CommandSlug")
    def test_slug_failure_no_error(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        target = tmp_path / "a.txt"
        target.write_text("x")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False)
        result = runner.invoke(cli, ["slug", str(target)])
        assert result.exit_code == 0

    @patch("fren.commands.directorize.directorize.CommandDirectorize")
    def test_directorize_failure(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="bad")
        result = runner.invoke(cli, ["directorize", str(tmp_path)])
        assert result.exit_code == 0

    @patch("fren.commands.directorize.directorize.CommandDirectorize")
    def test_directorize_with_warnings(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Wrapped 1", warnings=["skipped x"]
        )
        result = runner.invoke(cli, ["directorize", str(tmp_path)])
        assert result.exit_code == 0

    @patch("fren.commands.directorize.directorize.CommandDirectorize")
    def test_directorize_success_no_output(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        result = runner.invoke(cli, ["directorize", str(tmp_path)])
        assert result.exit_code == 0

    @patch("fren.commands.flatten.flatten.CommandFlatten")
    def test_flatten_failure(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        dst = tmp_path / "dst"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="bad")
        result = runner.invoke(cli, ["flatten", str(src), str(dst)])
        assert result.exit_code == 0

    @patch("fren.commands.flatten.flatten.CommandFlatten")
    def test_flatten_with_warnings(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        dst = tmp_path / "dst"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Copied 1", warnings=["collision"]
        )
        result = runner.invoke(cli, ["flatten", str(src), str(dst)])
        assert result.exit_code == 0

    @patch("fren.commands.flatten.flatten.CommandFlatten")
    def test_flatten_success_no_output(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        dst = tmp_path / "dst"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        result = runner.invoke(cli, ["flatten", str(src), str(dst)])
        assert result.exit_code == 0

    @patch("fren.commands.normalize.normalize.CommandNormalize")
    def test_normalize_failure(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="bad")
        result = runner.invoke(cli, ["normalize", str(tmp_path)])
        assert result.exit_code == 0

    @patch("fren.commands.normalize.normalize.CommandNormalize")
    def test_normalize_with_warnings(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Normalized 1", warnings=["Failed to normalize x"]
        )
        result = runner.invoke(cli, ["normalize", str(tmp_path)])
        assert result.exit_code == 0

    @patch("fren.commands.normalize.normalize.CommandNormalize")
    def test_normalize_success_no_output(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        result = runner.invoke(cli, ["normalize", str(tmp_path)])
        assert result.exit_code == 0
