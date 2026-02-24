from __future__ import annotations

from morph.cli import cli


class TestMorphCli:
    def test_help(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "html2md" in result.output
        assert "deblank" in result.output

    def test_html2md_help(self, runner) -> None:
        result = runner.invoke(cli, ["html2md", "--help"])

        assert result.exit_code == 0

    def test_deblank_help(self, runner) -> None:
        result = runner.invoke(cli, ["deblank", "--help"])

        assert result.exit_code == 0
