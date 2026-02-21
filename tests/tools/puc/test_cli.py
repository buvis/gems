from __future__ import annotations

from click.testing import CliRunner
from puc.cli import cli


class TestPucCli:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "strip" in result.output

    def test_strip_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["strip", "--help"])
        assert result.exit_code == 0
        assert "FILES" in result.output
