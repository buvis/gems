from __future__ import annotations

from fctracker.cli import cli


class TestFctrackerCli:
    def test_help(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "balance" in result.output
        assert "transactions" in result.output

    def test_balance_help(self, runner) -> None:
        result = runner.invoke(cli, ["balance", "--help"])
        assert result.exit_code == 0

    def test_transactions_help(self, runner) -> None:
        result = runner.invoke(cli, ["transactions", "--help"])
        assert result.exit_code == 0
        assert "--account" in result.output
        assert "--currency" in result.output
        assert "--month" in result.output
