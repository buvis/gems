from __future__ import annotations

from pinger.cli import cli


class TestPingerCli:
    def test_help(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "wait" in result.output

    def test_wait_help(self, runner) -> None:
        result = runner.invoke(cli, ["wait", "--help"])
        assert result.exit_code == 0
        assert "--timeout" in result.output
