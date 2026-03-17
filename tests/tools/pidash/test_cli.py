from __future__ import annotations

from click.testing import CliRunner
from pidash.cli import cli


class TestPidashCli:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "dashboard" in result.output.lower()

    def test_nonexistent_path(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["/nonexistent/path"])
        assert result.exit_code != 0
