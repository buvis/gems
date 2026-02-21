from __future__ import annotations

from click.testing import CliRunner
from dot.cli import cli


class TestDotCliHelp:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "status" in result.output
        assert "add" in result.output
        assert "pull" in result.output
        assert "commit" in result.output
        assert "push" in result.output

    def test_status_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0

    def test_add_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["add", "--help"])
        assert result.exit_code == 0

    def test_pull_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["pull", "--help"])
        assert result.exit_code == 0

    def test_commit_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["commit", "--help"])
        assert result.exit_code == 0
        assert "--message" in result.output

    def test_push_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["push", "--help"])
        assert result.exit_code == 0
