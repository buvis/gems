from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bim.cli import query
from click.testing import CliRunner


class TestQueryCli:
    def test_list_queries_uses_bundled_dir(self, runner: CliRunner) -> None:
        bundled_dir = Path("/tmp/bundled")
        queries = {
            "alpha": Path("/tmp/alpha.yml"),
            "beta": Path("/tmp/beta.yml"),
        }

        with (
            patch("bim.commands.query.query.BUNDLED_QUERY_DIR", bundled_dir),
            patch("bim.dependencies.list_query_files") as mock_list,
            patch("bim.cli.console") as mock_console,
        ):
            mock_list.return_value = queries
            result = runner.invoke(query, ["--list"], catch_exceptions=False)

        assert result.exit_code == 0
        mock_list.assert_called_once_with(bundled_dir=bundled_dir)
        mock_console.print.assert_any_call(f"{'alpha':30s} {queries['alpha']}", mode="raw")
        mock_console.print.assert_any_call(f"{'beta':30s} {queries['beta']}", mode="raw")

    def test_query_file_executes_command(self, runner: CliRunner) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten="/tmp/zk",
                path_archive="/tmp/archive",
            )
            instance = mock_cmd.return_value

            result = runner.invoke(
                query,
                ["-f", "query.yml", "--tui", "-e"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                default_directory=str(Path("/tmp/zk").expanduser().resolve()),
                archive_directory=str(Path("/tmp/archive").expanduser().resolve()),
                file="query.yml",
                query=None,
                edit=True,
                tui=True,
            )
            instance.execute.assert_called_once_with()

    def test_query_inline_yaml_executes_command(self, runner: CliRunner) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten="/tmp/zk",
                path_archive="/tmp/archive",
            )
            instance = mock_cmd.return_value

            result = runner.invoke(
                query,
                ["-q", "sort: title"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                default_directory=str(Path("/tmp/zk").expanduser().resolve()),
                archive_directory=str(Path("/tmp/archive").expanduser().resolve()),
                file=None,
                query="sort: title",
                edit=False,
                tui=False,
            )
            instance.execute.assert_called_once_with()

    def test_query_without_args_invokes_command(self, runner: CliRunner) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten="/tmp/zk",
                path_archive="/tmp/archive",
            )
            instance = mock_cmd.return_value

            result = runner.invoke(query, [], catch_exceptions=False)

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                default_directory=str(Path("/tmp/zk").expanduser().resolve()),
                archive_directory=str(Path("/tmp/archive").expanduser().resolve()),
                file=None,
                query=None,
                edit=False,
                tui=False,
            )
            instance.execute.assert_called_once_with()
