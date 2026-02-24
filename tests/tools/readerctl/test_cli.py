from __future__ import annotations

from readerctl.cli import cli


class TestReaderctlCli:
    def test_help(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "login" in result.output
        assert "add" in result.output

    def test_login_help(self, runner) -> None:
        result = runner.invoke(cli, ["login", "--help"])
        assert result.exit_code == 0

    def test_add_help(self, runner) -> None:
        result = runner.invoke(cli, ["add", "--help"])
        assert result.exit_code == 0
        assert "--url" in result.output
        assert "--file" in result.output
