from __future__ import annotations

from outlookctl.cli import cli


class TestOutlookctlCli:
    def test_help(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "create_timeblock" in result.output
