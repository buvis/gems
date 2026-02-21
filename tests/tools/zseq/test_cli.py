from __future__ import annotations

from click.testing import CliRunner
from zseq.cli import cli


class TestZseqCli:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--path" in result.output
        assert "--misnamed-reporting" in result.output
