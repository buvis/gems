from __future__ import annotations

from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

from bim.cli import query
from bim.params.query import QueryParams
from buvis.pybase.result import CommandResult
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
            patch("bim.dependencies.resolve_query_file") as mock_resolve,
            patch("bim.dependencies.parse_query_file") as mock_parse,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_evaluator") as mock_get_evaluator,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
            patch("bim.shared.query_presentation.present_query_result") as mock_present,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten="/tmp/zk",
                path_archive="/tmp/archive",
            )
            spec = MagicMock()
            spec.source.extensions = [".md"]
            resolved = Path("/tmp/query.yml")
            mock_resolve.return_value = resolved
            mock_parse.return_value = spec
            repo = MagicMock()
            evaluator = MagicMock()
            mock_get_repo.return_value = repo
            mock_get_evaluator.return_value = evaluator
            instance = mock_cmd.return_value
            rows = [{"title": "Note"}]
            columns = ["title"]
            instance.execute.return_value = CommandResult(
                success=True,
                metadata={
                    "rows": rows,
                    "columns": columns,
                    "count": len(rows),
                    "directory": "/tmp/zk",
                    "spec": spec,
                },
            )

            result = runner.invoke(
                query,
                ["-f", "query.yml", "--tui", "-e"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_resolve.assert_called_once_with("query.yml", bundled_dir=ANY)
            mock_parse.assert_called_once_with(str(resolved))
            mock_get_repo.assert_called_once_with(extensions=spec.source.extensions)
            mock_get_evaluator.assert_called_once_with()
            mock_cmd.assert_called_once_with(
                params=QueryParams(
                    spec=spec,
                    default_directory=str(Path("/tmp/zk").expanduser().resolve()),
                    edit=True,
                    tui=True,
                ),
                repo=repo,
                evaluator=evaluator,
            )
            instance.execute.assert_called_once_with()
            mock_present.assert_called_once_with(
                rows,
                columns,
                spec,
                tui=True,
                edit=True,
                archive_directory=str(Path("/tmp/archive").expanduser().resolve()),
                directory="/tmp/zk",
                repo=repo,
                evaluator=evaluator,
            )

    def test_query_inline_yaml_executes_command(self, runner: CliRunner) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.dependencies.parse_query_string") as mock_parse,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_evaluator") as mock_get_evaluator,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
            patch("bim.shared.query_presentation.present_query_result") as mock_present,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten="/tmp/zk",
                path_archive="/tmp/archive",
            )
            spec = MagicMock()
            spec.source.extensions = [".md"]
            mock_parse.return_value = spec
            repo = MagicMock()
            evaluator = MagicMock()
            mock_get_repo.return_value = repo
            mock_get_evaluator.return_value = evaluator
            instance = mock_cmd.return_value
            rows = [{"title": "Note"}]
            columns = ["title"]
            instance.execute.return_value = CommandResult(
                success=True,
                metadata={
                    "rows": rows,
                    "columns": columns,
                    "count": len(rows),
                    "directory": "/tmp/zk",
                    "spec": spec,
                },
            )

            result = runner.invoke(
                query,
                ["-q", "sort: title"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_parse.assert_called_once_with("sort: title")
            mock_get_repo.assert_called_once_with(extensions=spec.source.extensions)
            mock_get_evaluator.assert_called_once_with()
            mock_cmd.assert_called_once_with(
                params=QueryParams(
                    spec=spec,
                    default_directory=str(Path("/tmp/zk").expanduser().resolve()),
                ),
                repo=repo,
                evaluator=evaluator,
            )
            instance.execute.assert_called_once_with()
            mock_present.assert_called_once_with(
                rows,
                columns,
                spec,
                tui=False,
                edit=False,
                archive_directory=str(Path("/tmp/archive").expanduser().resolve()),
                directory="/tmp/zk",
                repo=repo,
                evaluator=evaluator,
            )

    def test_query_without_args_reports_error(self, runner: CliRunner) -> None:
        with (
            patch("bim.cli.console") as mock_console,
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock()
            result = runner.invoke(query, [], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.failure.assert_called_once_with("Provide -f/--file or -q/--query")
            mock_cmd.assert_not_called()
