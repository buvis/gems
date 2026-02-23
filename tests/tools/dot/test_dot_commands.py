from __future__ import annotations

from buvis.pybase.result import CommandResult
from dot.cli import cli


class TestDotCliHelp:
    def test_help(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "status" in result.output
        assert "add" in result.output
        assert "pull" in result.output
        assert "commit" in result.output
        assert "push" in result.output

    def test_status_help(self, runner) -> None:
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0

    def test_add_help(self, runner) -> None:
        result = runner.invoke(cli, ["add", "--help"])
        assert result.exit_code == 0

    def test_pull_help(self, runner) -> None:
        result = runner.invoke(cli, ["pull", "--help"])
        assert result.exit_code == 0

    def test_commit_help(self, runner) -> None:
        result = runner.invoke(cli, ["commit", "--help"])
        assert result.exit_code == 0
        assert "--message" in result.output

    def test_push_help(self, runner) -> None:
        result = runner.invoke(cli, ["push", "--help"])
        assert result.exit_code == 0


class TestDotCommands:
    def test_status_success(self, mocker, runner) -> None:
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.status.status.CommandStatus")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="All clean")
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0

    def test_status_with_warnings(self, mocker, runner) -> None:
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.status.status.CommandStatus")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, warnings=["file.txt was modified"])
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0

    def test_status_failure(self, mocker, runner) -> None:
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.status.status.CommandStatus")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=False, error="Git error", metadata={"details": "some details"}
        )
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0

    def test_add_success(self, mocker, runner) -> None:
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.add.add.CommandAdd")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Added")
        result = runner.invoke(cli, ["add", "/tmp/test.txt"])
        assert result.exit_code == 0

    def test_pull_success(self, mocker, runner) -> None:
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.pull.pull.CommandPull")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Dotfiles pulled successfully"
        )
        result = runner.invoke(cli, ["pull"])
        assert result.exit_code == 0

    def test_pull_failure(self, mocker, runner) -> None:
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.pull.pull.CommandPull")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="Pull failed")
        result = runner.invoke(cli, ["pull"])
        assert result.exit_code == 0

    def test_commit_success(self, mocker, runner) -> None:
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.commit.commit.CommandCommit")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Changes committed")
        result = runner.invoke(cli, ["commit", "-m", "test msg"])
        assert result.exit_code == 0

    def test_commit_failure(self, mocker, runner) -> None:
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.commit.commit.CommandCommit")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=False, error="Commit failed", warnings=["unstaged"]
        )
        result = runner.invoke(cli, ["commit", "-m", "test msg"])
        assert result.exit_code == 0

    def test_push_success(self, mocker, runner) -> None:
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.push.push.CommandPush")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Changes pushed")
        result = runner.invoke(cli, ["push"])
        assert result.exit_code == 0

    def test_push_failure(self, mocker, runner) -> None:
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.push.push.CommandPush")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="Push failed")
        result = runner.invoke(cli, ["push"])
        assert result.exit_code == 0
