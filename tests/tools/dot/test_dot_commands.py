from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from dot.cli import cli


class TestDotCommands:
    @patch("dot.cli.ShellAdapter")
    @patch("dot.commands.status.status.CommandStatus")
    def test_status_success(self, mock_cmd_cls: MagicMock, mock_shell: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="All clean")
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0

    @patch("dot.cli.ShellAdapter")
    @patch("dot.commands.status.status.CommandStatus")
    def test_status_with_warnings(self, mock_cmd_cls: MagicMock, mock_shell: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, warnings=["file.txt was modified"])
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0

    @patch("dot.cli.ShellAdapter")
    @patch("dot.commands.status.status.CommandStatus")
    def test_status_failure(self, mock_cmd_cls: MagicMock, mock_shell: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=False, error="Git error", metadata={"details": "some details"}
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0  # Click doesn't set non-zero for console.failure

    @patch("dot.cli.ShellAdapter")
    @patch("dot.commands.add.add.CommandAdd")
    def test_add_success(self, mock_cmd_cls: MagicMock, mock_shell: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Added")
        runner = CliRunner()
        result = runner.invoke(cli, ["add", "/tmp/test.txt"])
        assert result.exit_code == 0

    @patch("dot.cli.ShellAdapter")
    @patch("dot.commands.pull.pull.CommandPull")
    def test_pull_success(self, mock_cmd_cls: MagicMock, mock_shell: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Dotfiles pulled successfully"
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["pull"])
        assert result.exit_code == 0

    @patch("dot.cli.ShellAdapter")
    @patch("dot.commands.pull.pull.CommandPull")
    def test_pull_failure(self, mock_cmd_cls: MagicMock, mock_shell: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="Pull failed")
        runner = CliRunner()
        result = runner.invoke(cli, ["pull"])
        assert result.exit_code == 0

    @patch("dot.cli.ShellAdapter")
    @patch("dot.commands.commit.commit.CommandCommit")
    def test_commit_success(self, mock_cmd_cls: MagicMock, mock_shell: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Changes committed")
        runner = CliRunner()
        result = runner.invoke(cli, ["commit", "-m", "test msg"])
        assert result.exit_code == 0

    @patch("dot.cli.ShellAdapter")
    @patch("dot.commands.commit.commit.CommandCommit")
    def test_commit_failure(self, mock_cmd_cls: MagicMock, mock_shell: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=False, error="Commit failed", warnings=["unstaged"]
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["commit", "-m", "test msg"])
        assert result.exit_code == 0

    @patch("dot.cli.ShellAdapter")
    @patch("dot.commands.push.push.CommandPush")
    def test_push_success(self, mock_cmd_cls: MagicMock, mock_shell: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Changes pushed")
        runner = CliRunner()
        result = runner.invoke(cli, ["push"])
        assert result.exit_code == 0

    @patch("dot.cli.ShellAdapter")
    @patch("dot.commands.push.push.CommandPush")
    def test_push_failure(self, mock_cmd_cls: MagicMock, mock_shell: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="Push failed")
        runner = CliRunner()
        result = runner.invoke(cli, ["push"])
        assert result.exit_code == 0
