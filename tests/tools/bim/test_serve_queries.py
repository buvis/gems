from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from starlette.testclient import TestClient


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


@dataclass
class LookupSpec:
    source: SourceSpec


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

    def test_exec_query(self, client: TestClient, query_spec: QuerySpecStub, tmp_path: Path) -> None:
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

            response = client.post(
                "/api/queries/example/exec",
                headers={"X-Buvis-Token": client.app.state.buvis_token},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["rows"] == [{"title": "Z1"}]
        assert body["count"] == 1
        assert body["columns"] == [{"name": "title"}]
        assert body["schema"]["custom"]["label"] == "Custom"
        assert query_spec.source.directory == str(tmp_path / "zettels")
        mock_use_case_cls.assert_called_once_with(repo, evaluator)
        use_case.execute.assert_called_once_with(query_spec)

    def test_exec_adhoc(self, client: TestClient, query_spec: QuerySpecStub, tmp_path: Path) -> None:
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

            response = client.post(
                "/api/queries/_adhoc",
                json={"spec": {"source": {}}},
                headers={"X-Buvis-Token": client.app.state.buvis_token},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert query_spec.source.directory == str(tmp_path / "zettels")
        mock_use_case_cls.assert_called_once_with(repo, evaluator)
        use_case.execute.assert_called_once_with(query_spec)

    def test_get_query_missing_returns_404(self, client: TestClient) -> None:
        with patch("bim.commands.serve._routes.resolve_query_file") as mock_resolve:
            mock_resolve.side_effect = FileNotFoundError("nope")

            response = client.get("/api/queries/missing")

        assert response.status_code == 404
        assert "nope" in response.json()["detail"]

    @pytest.mark.parametrize("name", ["report.yaml", "report.yml"])
    def test_get_query_yaml_suffix_returns_404(self, client: TestClient, name: str) -> None:
        with patch("bim.commands.serve._routes.resolve_query_file") as mock_resolve:
            mock_resolve.return_value = Path("/tmp/query.yaml")

            response = client.get(f"/api/queries/{name}")

        assert response.status_code == 404
        assert response.json()["detail"] == f"Unknown query: {name}"
        mock_resolve.assert_not_called()

    @pytest.mark.parametrize("name", ["report.yaml", "report.yml"])
    def test_exec_query_yaml_suffix_returns_404(self, client: TestClient, name: str) -> None:
        with patch("bim.commands.serve._routes.resolve_query_file") as mock_resolve:
            mock_resolve.return_value = Path("/tmp/query.yaml")

            response = client.post(
                f"/api/queries/{name}/exec",
                headers={"X-Buvis-Token": client.app.state.buvis_token},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == f"Unknown query: {name}"
        mock_resolve.assert_not_called()

    def test_exec_query_missing_returns_404(self, client: TestClient) -> None:
        with patch("bim.commands.serve._routes.resolve_query_file") as mock_resolve:
            mock_resolve.side_effect = FileNotFoundError("nope")

            response = client.post(
                "/api/queries/missing/exec",
                headers={"X-Buvis-Token": client.app.state.buvis_token},
            )

        assert response.status_code == 404
        assert "nope" in response.json()["detail"]


class TestServeQueriesSecurity:
    def test_exec_adhoc_without_token_returns_401(self, client: TestClient, query_spec: QuerySpecStub) -> None:
        with (
            patch("bim.commands.serve._routes.parse_query_spec") as mock_parse,
            patch("bim.commands.serve._routes.get_repo") as mock_repo,
            patch("bim.commands.serve._routes.get_evaluator") as mock_eval,
            patch("bim.commands.serve._routes.QueryZettelsUseCase") as mock_use_case_cls,
        ):
            mock_parse.return_value = query_spec

            response = client.post("/api/queries/_adhoc", json={"spec": {"source": {}}})

        assert response.status_code == 401
        mock_parse.assert_not_called()
        mock_repo.assert_not_called()
        mock_eval.assert_not_called()
        mock_use_case_cls.assert_not_called()

    def test_exec_adhoc_with_wrong_token_returns_401(self, client: TestClient, query_spec: QuerySpecStub) -> None:
        client.app.state.buvis_token = "correct-token"

        with (
            patch("bim.commands.serve._routes.parse_query_spec") as mock_parse,
            patch("bim.commands.serve._routes.get_repo") as mock_repo,
            patch("bim.commands.serve._routes.get_evaluator") as mock_eval,
            patch("bim.commands.serve._routes.QueryZettelsUseCase") as mock_use_case_cls,
        ):
            mock_parse.return_value = query_spec

            response = client.post(
                "/api/queries/_adhoc",
                json={"spec": {"source": {}}},
                headers={"X-Buvis-Token": "wrong-token"},
            )

        assert response.status_code == 401
        mock_parse.assert_not_called()
        mock_repo.assert_not_called()
        mock_eval.assert_not_called()
        mock_use_case_cls.assert_not_called()

    def test_exec_query_without_token_returns_401(self, client: TestClient, query_spec: QuerySpecStub) -> None:
        with (
            patch("bim.commands.serve._routes.resolve_query_file") as mock_resolve,
            patch("bim.commands.serve._routes.parse_query_file") as mock_parse,
            patch("bim.commands.serve._routes.get_repo") as mock_repo,
            patch("bim.commands.serve._routes.get_evaluator") as mock_eval,
            patch("bim.commands.serve._routes.QueryZettelsUseCase") as mock_use_case_cls,
        ):
            mock_resolve.return_value = Path("/tmp/query.yaml")
            mock_parse.return_value = query_spec

            response = client.post("/api/queries/example/exec")

        assert response.status_code == 401
        mock_resolve.assert_not_called()
        mock_repo.assert_not_called()
        mock_eval.assert_not_called()
        mock_use_case_cls.assert_not_called()

    def test_exec_query_with_wrong_token_returns_401(self, client: TestClient, query_spec: QuerySpecStub) -> None:
        client.app.state.buvis_token = "correct-token"

        with (
            patch("bim.commands.serve._routes.resolve_query_file") as mock_resolve,
            patch("bim.commands.serve._routes.parse_query_file") as mock_parse,
            patch("bim.commands.serve._routes.get_repo") as mock_repo,
            patch("bim.commands.serve._routes.get_evaluator") as mock_eval,
            patch("bim.commands.serve._routes.QueryZettelsUseCase") as mock_use_case_cls,
        ):
            mock_resolve.return_value = Path("/tmp/query.yaml")
            mock_parse.return_value = query_spec

            response = client.post(
                "/api/queries/example/exec",
                headers={"X-Buvis-Token": "wrong-token"},
            )

        assert response.status_code == 401
        mock_resolve.assert_not_called()
        mock_repo.assert_not_called()
        mock_eval.assert_not_called()
        mock_use_case_cls.assert_not_called()

    def test_exec_adhoc_source_directory_outside_vault_returns_403(
        self, client: TestClient, query_spec: QuerySpecStub
    ) -> None:
        client.app.state.buvis_token = "test-token"
        query_spec.source.directory = "/etc"

        with (
            patch("bim.commands.serve._routes.parse_query_spec") as mock_parse,
            patch("bim.commands.serve._routes.get_repo") as mock_repo,
            patch("bim.commands.serve._routes.get_evaluator") as mock_eval,
            patch("bim.commands.serve._routes.QueryZettelsUseCase") as mock_use_case_cls,
        ):
            mock_parse.return_value = query_spec

            response = client.post(
                "/api/queries/_adhoc",
                json={"spec": {"source": {"directory": "/etc"}}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_repo.assert_not_called()
        mock_eval.assert_not_called()
        mock_use_case_cls.assert_not_called()

    def test_exec_adhoc_lookup_directory_outside_vault_returns_403(
        self, client: TestClient, query_spec: QuerySpecStub
    ) -> None:
        client.app.state.buvis_token = "test-token"
        query_spec.lookups = [LookupSpec(source=SourceSpec(directory="/etc"))]

        with (
            patch("bim.commands.serve._routes.parse_query_spec") as mock_parse,
            patch("bim.commands.serve._routes.get_repo") as mock_repo,
            patch("bim.commands.serve._routes.get_evaluator") as mock_eval,
            patch("bim.commands.serve._routes.QueryZettelsUseCase") as mock_use_case_cls,
        ):
            mock_parse.return_value = query_spec

            response = client.post(
                "/api/queries/_adhoc",
                json={"spec": {"source": {}, "lookups": [{"source": {"directory": "/etc"}}]}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_repo.assert_not_called()
        mock_eval.assert_not_called()
        mock_use_case_cls.assert_not_called()

    def test_exec_adhoc_with_in_vault_source_directory_returns_200(
        self, client: TestClient, query_spec: QuerySpecStub, tmp_path: Path
    ) -> None:
        client.app.state.buvis_token = "test-token"
        in_vault_dir = str(tmp_path / "zettels")
        query_spec.source.directory = in_vault_dir

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

            response = client.post(
                "/api/queries/_adhoc",
                json={"spec": {"source": {"directory": in_vault_dir}}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert query_spec.source.directory == in_vault_dir

    def test_exec_adhoc_without_source_directory_returns_200_and_uses_default_directory(
        self, client: TestClient, query_spec: QuerySpecStub, tmp_path: Path
    ) -> None:
        client.app.state.buvis_token = "test-token"
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

            response = client.post(
                "/api/queries/_adhoc",
                json={"spec": {"source": {}}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert query_spec.source.directory == str(tmp_path / "zettels")
