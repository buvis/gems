from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from starlette.testclient import TestClient

from bim.commands.serve._app import create_app
from bim.commands.serve.serve import CommandServe


@dataclass
class SourceSpec:
    directory: str | None
    extensions: list[str] | None = None


@dataclass
class ColumnSpec:
    name: str


@dataclass
class DashboardSpec:
    title: str


@dataclass
class SchemaSpec:
    label: str


@dataclass
class ItemSpec:
    title: str


@dataclass
class ActionSpec:
    name: str


@dataclass
class OutputSpec:
    format: str = "json"


@dataclass
class QuerySpecStub:
    source: SourceSpec
    columns: list[ColumnSpec] | None
    dashboard: DashboardSpec | None
    schema: dict[str, SchemaSpec]
    item: ItemSpec | None
    actions: list[ActionSpec] | None
    output: OutputSpec


@pytest.fixture
def client() -> TestClient:
    with (
        patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
        patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
    ):
        app = create_app(default_directory="zettels", archive_directory="archive")
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture
def query_spec() -> QuerySpecStub:
    return QuerySpecStub(
        source=SourceSpec(directory=None, extensions=["md"]),
        columns=[ColumnSpec(name="title")],
        dashboard=None,
        schema={"custom": SchemaSpec(label="Custom")},
        item=None,
        actions=[ActionSpec(name="open")],
        output=OutputSpec(format="json"),
    )


class TestCommandServe:
    def test_init_sets_attributes(self) -> None:
        cmd = CommandServe(
            default_directory="zettels",
            archive_directory="archive",
            host="0.0.0.0",
            port=9001,
            no_browser=True,
        )

        assert cmd.default_directory == "zettels"
        assert cmd.archive_directory == "archive"
        assert cmd.host == "0.0.0.0"
        assert cmd.port == 9001
        assert cmd.no_browser is True


class TestServeHealth:
    def test_health_ok(self, client: TestClient) -> None:
        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestServeQueries:
    def test_list_queries(self, client: TestClient) -> None:
        with patch("bim.commands.serve._routes.list_query_files") as mock_list:
            mock_list.return_value = {
                "alpha": Path("/tmp/alpha.yaml"),
                "beta": Path("/tmp/beta.yaml"),
            }

            response = client.get("/api/queries")

        assert response.status_code == 200
        assert response.json() == {
            "queries": {
                "alpha": "/tmp/alpha.yaml",
                "beta": "/tmp/beta.yaml",
            }
        }

    def test_get_query_spec(self, client: TestClient, query_spec: QuerySpecStub) -> None:
        with (
            patch("bim.commands.serve._routes.resolve_query_file") as mock_resolve,
            patch("bim.commands.serve._routes.parse_query_file") as mock_parse,
        ):
            mock_resolve.return_value = Path("/tmp/query.yaml")
            mock_parse.return_value = query_spec

            response = client.get("/api/queries/example")

        assert response.status_code == 200
        body = response.json()
        assert body["output"]["format"] == "json"
        assert body["schema"]["custom"]["label"] == "Custom"

    def test_exec_query(self, client: TestClient, query_spec: QuerySpecStub) -> None:
        query_spec.source.directory = None
        with (
            patch("bim.commands.serve._routes.resolve_query_file") as mock_resolve,
            patch("bim.commands.serve._routes.parse_query_file") as mock_parse,
            patch("bim.commands.serve._routes.get_repo") as mock_repo,
            patch("bim.commands.serve._routes.get_evaluator") as mock_eval,
            patch("bim.commands.serve._routes.QueryZettelsUseCase") as mock_use_case_cls,
        ):
            repo = MagicMock()
            evaluator = MagicMock()
            use_case = MagicMock()
            mock_repo.return_value = repo
            mock_eval.return_value = evaluator
            mock_use_case_cls.return_value = use_case
            use_case.execute.return_value = [{"title": "Z1"}]
            mock_resolve.return_value = Path("/tmp/query.yaml")
            mock_parse.return_value = query_spec

            response = client.post("/api/queries/example/exec")

        assert response.status_code == 200
        body = response.json()
        assert body["rows"] == [{"title": "Z1"}]
        assert body["count"] == 1
        assert body["columns"] == [{"name": "title"}]
        assert body["schema"]["custom"]["label"] == "Custom"
        assert query_spec.source.directory == "zettels"
        mock_use_case_cls.assert_called_once_with(repo, evaluator)
        use_case.execute.assert_called_once_with(query_spec)

    def test_exec_adhoc(self, client: TestClient, query_spec: QuerySpecStub) -> None:
        query_spec.source.directory = None
        with (
            patch("bim.commands.serve._routes.parse_query_spec") as mock_parse,
            patch("bim.commands.serve._routes.get_repo") as mock_repo,
            patch("bim.commands.serve._routes.get_evaluator") as mock_eval,
            patch("bim.commands.serve._routes.QueryZettelsUseCase") as mock_use_case_cls,
        ):
            repo = MagicMock()
            evaluator = MagicMock()
            use_case = MagicMock()
            mock_repo.return_value = repo
            mock_eval.return_value = evaluator
            mock_use_case_cls.return_value = use_case
            use_case.execute.return_value = [{"title": "Z1"}]
            mock_parse.return_value = query_spec

            response = client.post("/api/queries/_adhoc", json={"spec": {"source": {}}})

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert query_spec.source.directory == "zettels"
        mock_use_case_cls.assert_called_once_with(repo, evaluator)
        use_case.execute.assert_called_once_with(query_spec)

    def test_get_query_missing_returns_404(self, client: TestClient) -> None:
        with patch("bim.commands.serve._routes.resolve_query_file") as mock_resolve:
            mock_resolve.side_effect = FileNotFoundError("nope")

            response = client.get("/api/queries/missing")

        assert response.status_code == 404
        assert "nope" in response.json()["detail"]


class TestServeZettels:
    def test_get_zettel(self, client: TestClient) -> None:
        data = SimpleNamespace(
            metadata={"title": "Note"},
            reference={"ref": "A1"},
            sections=[("Heading", "Body")],
            file_path="note.md",
        )
        zettel = MagicMock()
        zettel.get_data.return_value = data
        repo = MagicMock()
        repo.find_by_location.return_value = zettel

        with (
            patch("pathlib.Path.is_file", return_value=True),
            patch("bim.commands.serve._routes.get_repo", return_value=repo),
        ):
            response = client.get("/api/zettels/note.md")

        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["title"] == "Note"
        assert body["reference"]["ref"] == "A1"
        assert body["sections"] == [{"heading": "Heading", "body": "Body"}]
        assert body["file_path"] == "note.md"
        repo.find_by_location.assert_called_once_with("note.md")

    def test_patch_zettel_metadata(self, client: TestClient) -> None:
        data = SimpleNamespace(
            metadata={},
            reference={},
            sections=[],
            file_path="note.md",
        )
        zettel = MagicMock()
        zettel.get_data.return_value = data
        repo = MagicMock()
        repo.find_by_location.return_value = zettel
        formatter = MagicMock()
        use_case = MagicMock()
        use_case.execute.return_value = "formatted"

        with (
            patch("pathlib.Path.is_file", return_value=True),
            patch("pathlib.Path.write_text") as mock_write,
            patch("bim.commands.serve._routes.get_repo", return_value=repo),
            patch("bim.commands.serve._routes.get_formatter", return_value=formatter),
            patch("bim.commands.serve._routes.PrintZettelUseCase", return_value=use_case) as mock_use_case_cls,
        ):
            response = client.patch(
                "/api/zettels/note.md",
                json={"field": "title", "value": "New Title"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert data.metadata["title"] == "New Title"
        mock_use_case_cls.assert_called_once_with(formatter)
        use_case.execute.assert_called_once_with(data)
        mock_write.assert_called_once_with("formatted", encoding="utf-8")

    def test_get_zettel_missing_returns_404(self, client: TestClient) -> None:
        with patch("pathlib.Path.is_file", return_value=False):
            response = client.get("/api/zettels/missing.md")

        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]


class TestServeErrors:
    def test_unknown_action_returns_404(self, client: TestClient) -> None:
        response = client.post(
            "/api/actions/missing",
            json={"file_path": "note.md", "args": {}, "row": {}},
        )

        assert response.status_code == 404
        assert "Unknown action" in response.json()["detail"]
