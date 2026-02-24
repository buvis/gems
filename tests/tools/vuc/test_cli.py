from __future__ import annotations

from vuc.cli import cli


class TestVucCli:
    def test_help(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "multilang" in result.output

    def test_multilang_help(self, runner) -> None:
        result = runner.invoke(cli, ["multilang", "--help"])
        assert result.exit_code == 0
