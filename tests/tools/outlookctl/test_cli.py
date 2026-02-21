from __future__ import annotations

from click.testing import CliRunner
from outlookctl.cli import cli


class TestOutlookctlCli:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "create_timeblock" in result.output
