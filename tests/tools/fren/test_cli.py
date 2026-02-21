from __future__ import annotations

from click.testing import CliRunner
from fren.cli import cli


class TestFrenCli:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "slug" in result.output
        assert "directorize" in result.output
        assert "flatten" in result.output
        assert "normalize" in result.output

    def test_slug_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["slug", "--help"])
        assert result.exit_code == 0

    def test_directorize_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["directorize", "--help"])
        assert result.exit_code == 0

    def test_flatten_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["flatten", "--help"])
        assert result.exit_code == 0

    def test_normalize_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["normalize", "--help"])
        assert result.exit_code == 0
