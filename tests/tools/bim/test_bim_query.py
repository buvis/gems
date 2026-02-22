from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bim.commands.query.query import CommandQuery
from bim.params.query import QueryParams


class TestCommandQuery:
    def test_execute_uses_default_directory_when_spec_has_none(self) -> None:
        spec = MagicMock()
        spec.source.directory = None
        spec.filter = None
        spec.lookups = []
        spec.columns = None
        spec.sort = None
        spec.expand = None
        spec.output.limit = None
        spec.output.sample = None

        params = QueryParams(spec=spec, default_directory="/tmp/zk")
        repo = MagicMock()
        evaluator = MagicMock()
        repo.find_all.return_value = []

        cmd = CommandQuery(params=params, repo=repo, evaluator=evaluator)

        with patch("bim.commands.query.query.QueryZettelsUseCase") as mock_use_case:
            mock_use_case.return_value.execute.return_value = []
            result = cmd.execute()

        assert spec.source.directory == "/tmp/zk"
        assert result.success is True
        assert result.metadata["rows"] == []
        assert result.metadata["columns"] == []
        assert result.metadata["count"] == 0

    def test_execute_preserves_explicit_directory(self) -> None:
        spec = MagicMock()
        spec.source.directory = "/tmp/explicit"
        spec.filter = None
        spec.lookups = []
        spec.columns = None
        spec.sort = None
        spec.expand = None
        spec.output.limit = None
        spec.output.sample = None

        params = QueryParams(spec=spec, default_directory="/tmp/default")
        repo = MagicMock()
        evaluator = MagicMock()

        cmd = CommandQuery(params=params, repo=repo, evaluator=evaluator)

        with patch("bim.commands.query.query.QueryZettelsUseCase") as mock_use_case:
            mock_use_case.return_value.execute.return_value = []
            result = cmd.execute()

        assert spec.source.directory == "/tmp/explicit"
        assert result.success is True

    def test_execute_returns_rows_and_columns(self) -> None:
        spec = MagicMock()
        spec.source.directory = "/tmp/zk"
        spec.filter = None
        spec.lookups = []
        spec.columns = None
        spec.sort = None
        spec.expand = None
        spec.output.limit = None
        spec.output.sample = None

        params = QueryParams(spec=spec, default_directory="/tmp/zk")
        repo = MagicMock()
        evaluator = MagicMock()

        rows = [
            {"id": 1, "title": "First"},
            {"id": 2, "title": "Second"},
        ]

        cmd = CommandQuery(params=params, repo=repo, evaluator=evaluator)

        with patch("bim.commands.query.query.QueryZettelsUseCase") as mock_use_case:
            mock_use_case.return_value.execute.return_value = rows
            result = cmd.execute()

        assert result.success is True
        assert result.metadata["rows"] == rows
        assert result.metadata["columns"] == ["id", "title"]
        assert result.metadata["count"] == 2

    def test_execute_resolves_directory_path(self) -> None:
        spec = MagicMock()
        spec.source.directory = "/tmp/zk"
        spec.filter = None
        spec.lookups = []
        spec.columns = None
        spec.sort = None
        spec.expand = None
        spec.output.limit = None
        spec.output.sample = None

        params = QueryParams(spec=spec, default_directory="/tmp/zk")
        repo = MagicMock()
        evaluator = MagicMock()

        cmd = CommandQuery(params=params, repo=repo, evaluator=evaluator)

        with patch("bim.commands.query.query.QueryZettelsUseCase") as mock_use_case:
            mock_use_case.return_value.execute.return_value = []
            result = cmd.execute()

        expected_dir = str(Path("/tmp/zk").expanduser().resolve())
        assert result.metadata["directory"] == expected_dir

    def test_execute_passes_repo_and_evaluator_to_use_case(self) -> None:
        spec = MagicMock()
        spec.source.directory = "/tmp/zk"
        spec.filter = None
        spec.lookups = []
        spec.columns = None
        spec.sort = None
        spec.expand = None
        spec.output.limit = None
        spec.output.sample = None

        params = QueryParams(spec=spec, default_directory="/tmp/zk")
        repo = MagicMock()
        evaluator = MagicMock()

        cmd = CommandQuery(params=params, repo=repo, evaluator=evaluator)

        with patch("bim.commands.query.query.QueryZettelsUseCase") as mock_use_case:
            mock_use_case.return_value.execute.return_value = []
            cmd.execute()

        mock_use_case.assert_called_once_with(repo, evaluator)
        mock_use_case.return_value.execute.assert_called_once_with(spec)

    def test_execute_returns_spec_in_metadata(self) -> None:
        spec = MagicMock()
        spec.source.directory = "/tmp/zk"
        spec.filter = None
        spec.lookups = []
        spec.columns = None
        spec.sort = None
        spec.expand = None
        spec.output.limit = None
        spec.output.sample = None

        params = QueryParams(spec=spec, default_directory="/tmp/zk")
        repo = MagicMock()
        evaluator = MagicMock()

        cmd = CommandQuery(params=params, repo=repo, evaluator=evaluator)

        with patch("bim.commands.query.query.QueryZettelsUseCase") as mock_use_case:
            mock_use_case.return_value.execute.return_value = []
            result = cmd.execute()

        assert result.metadata["spec"] is spec
