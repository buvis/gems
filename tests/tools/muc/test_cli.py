from __future__ import annotations

from muc.cli import cli


class TestMucCli:
    def test_help(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "limit" in result.output
        assert "tidy" in result.output
        assert "cover" in result.output

    def test_limit_help(self, runner) -> None:
        result = runner.invoke(cli, ["limit", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output

    def test_tidy_help(self, runner) -> None:
        result = runner.invoke(cli, ["tidy", "--help"])
        assert result.exit_code == 0
        assert "--yes" in result.output

    def test_cover_help(self, runner) -> None:
        result = runner.invoke(cli, ["cover", "--help"])
        assert result.exit_code == 0
