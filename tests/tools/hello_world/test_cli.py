from __future__ import annotations

from click.testing import CliRunner
from hello_world.cli import cli


class TestHelloWorldCli:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--font" in result.output
        assert "--list-fonts" in result.output
        assert "--random-font" in result.output
        assert "--diag" in result.output
