from __future__ import annotations

from bim.cli import cli
from click.testing import CliRunner


class TestBimCliHelp:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "CLI to BUVIS InfoMesh" in result.output

    def test_import_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["import", "--help"])
        assert result.exit_code == 0
        assert "Import a note" in result.output

    def test_format_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["format", "--help"])
        assert result.exit_code == 0
        assert "Format a note" in result.output

    def test_sync_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["sync", "--help"])
        assert result.exit_code == 0
        assert "Synchronize note" in result.output

    def test_create_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["create", "--help"])
        assert result.exit_code == 0
        assert "Create a new zettel" in result.output

    def test_query_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["query", "--help"])
        assert result.exit_code == 0
        assert "Query zettels" in result.output

    def test_edit_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["edit", "--help"])
        assert result.exit_code == 0
        assert "Edit zettel metadata" in result.output

    def test_archive_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["archive", "--help"])
        assert result.exit_code == 0
        assert "Archive zettel" in result.output

    def test_show_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["show", "--help"])
        assert result.exit_code == 0
        assert "Display zettel content" in result.output

    def test_delete_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["delete", "--help"])
        assert result.exit_code == 0
        assert "Permanently delete" in result.output

    def test_serve_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0
        assert "Start web dashboard" in result.output

    def test_help_lists_all_subcommands(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for cmd in ("import", "format", "sync", "create", "query", "edit", "archive", "show", "delete", "serve"):
            assert cmd in result.output
