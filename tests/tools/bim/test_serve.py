from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from bim.commands.serve._app import create_app
from bim.commands.serve.serve import CommandServe
from pytest_mock import MockerFixture
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


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    zettels_dir = tmp_path / "zettels"
    zettels_dir.mkdir()
    with (
        patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
        patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
    ):
        app = create_app(default_directory=str(zettels_dir), archive_directory="archive")
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
        from bim.params.serve import ServeParams

        params = ServeParams(
            default_directory="zettels",
            archive_directory="archive",
            host="0.0.0.0",
            port=9001,
            no_browser=True,
        )
        cmd = CommandServe(params=params)

        assert cmd.params.default_directory == "zettels"
        assert cmd.params.archive_directory == "archive"
        assert cmd.params.host == "0.0.0.0"
        assert cmd.params.port == 9001
        assert cmd.params.no_browser is True


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

            response = client.post("/api/queries/example/exec")

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

            response = client.post("/api/queries/_adhoc", json={"spec": {"source": {}}})

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

            response = client.post(f"/api/queries/{name}/exec")

        assert response.status_code == 404
        assert response.json()["detail"] == f"Unknown query: {name}"
        mock_resolve.assert_not_called()


class TestServeZettels:
    def test_get_zettel(self, client: TestClient, tmp_path: Path) -> None:
        file_path = tmp_path / "zettels" / "note.md"
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
            response = client.get(f"/api/zettels/{file_path}")

        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["title"] == "Note"
        assert body["reference"]["ref"] == "A1"
        assert body["sections"] == [{"heading": "Heading", "body": "Body"}]
        assert body["file_path"] == "note.md"
        repo.find_by_location.assert_called_once_with(str(file_path))

    def test_get_zettel_outside_vault_returns_403(self, client: TestClient) -> None:
        outside_path = Path("/etc/passwd")

        with patch("bim.commands.serve._routes.get_repo") as mock_get_repo:
            response = client.get(f"/api/zettels/{outside_path}")

        assert response.status_code == 403
        mock_get_repo.assert_not_called()

    def test_patch_zettel_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"
        outside_path = Path("/etc/passwd")

        with patch("bim.commands.serve._routes.get_repo") as mock_get_repo:
            response = client.patch(
                f"/api/zettels/{outside_path}",
                json={"field": "title", "value": "New Title"},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_get_repo.assert_not_called()

    def test_patch_zettel_without_token_returns_401(self, client: TestClient, tmp_path: Path) -> None:
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.serve._routes.get_repo") as mock_get_repo:
            response = client.patch(
                f"/api/zettels/{real_file}",
                json={"field": "title", "value": "New Title"},
            )

        assert response.status_code == 401
        mock_get_repo.assert_not_called()

    def test_patch_zettel_with_wrong_token_returns_401(self, client: TestClient, tmp_path: Path) -> None:
        client.app.state.buvis_token = "correct-token"
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.serve._routes.get_repo") as mock_get_repo:
            response = client.patch(
                f"/api/zettels/{real_file}",
                json={"field": "title", "value": "New Title"},
                headers={"X-Buvis-Token": "wrong-token"},
            )

        assert response.status_code == 401
        mock_get_repo.assert_not_called()

    def test_patch_zettel_metadata(self, client: TestClient, tmp_path: Path) -> None:
        client.app.state.buvis_token = "test-token"
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        data = SimpleNamespace(
            metadata={},
            reference={},
            sections=[],
            file_path=str(real_file),
        )
        zettel = MagicMock()
        zettel.get_data.return_value = data
        repo = MagicMock()
        repo.find_by_location.return_value = zettel
        formatter = MagicMock()
        use_case = MagicMock()
        use_case.execute.return_value = "formatted"

        with (
            patch("bim.commands.serve._routes.get_repo", return_value=repo),
            patch("bim.commands.serve._routes.get_formatter", return_value=formatter),
            patch("bim.commands.serve._routes.PrintZettelUseCase", return_value=use_case) as mock_use_case_cls,
        ):
            response = client.patch(
                f"/api/zettels/{real_file}",
                json={"field": "title", "value": "New Title"},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert data.metadata["title"] == "New Title"
        mock_use_case_cls.assert_called_once_with(formatter)
        use_case.execute.assert_called_once_with(data)
        assert real_file.read_text(encoding="utf-8") == "formatted"

    def test_patch_zettel_write_failure_leaves_original_untouched(
        self, client: TestClient, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        client.app.state.buvis_token = "test-token"
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("original content", encoding="utf-8")

        data = SimpleNamespace(
            metadata={},
            reference={},
            sections=[],
            file_path=str(real_file),
        )
        zettel = MagicMock()
        zettel.get_data.return_value = data
        repo = MagicMock()
        repo.find_by_location.return_value = zettel
        formatter = MagicMock()
        use_case = MagicMock()
        use_case.execute.return_value = "formatted"

        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=OSError("disk full"),
        )

        with (
            patch("bim.commands.serve._routes.get_repo", return_value=repo),
            patch("bim.commands.serve._routes.get_formatter", return_value=formatter),
            patch("bim.commands.serve._routes.PrintZettelUseCase", return_value=use_case),
            pytest.raises(OSError),
        ):
            client.patch(
                f"/api/zettels/{real_file}",
                json={"field": "title", "value": "New Title"},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert real_file.read_text(encoding="utf-8") == "original content"

    def test_get_zettel_missing_returns_404(self, client: TestClient, tmp_path: Path) -> None:
        file_path = tmp_path / "zettels" / "missing.md"
        with patch("pathlib.Path.is_file", return_value=False):
            response = client.get(f"/api/zettels/{file_path}")

        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]


class TestServeActions:
    def test_exec_action_without_token_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/api/actions/some-action",
            json={"file_path": "note.md", "args": {}, "row": {}},
        )

        assert response.status_code == 401

    def test_patch_action_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"

        with patch("bim.commands.serve._actions.get_repo") as mock_get_repo:
            response = client.post(
                "/api/actions/patch",
                json={"file_path": "/etc/passwd", "args": {}, "row": {}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_get_repo.assert_not_called()

    def test_sync_note_action_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"

        with patch("bim.commands.sync_note.sync_note.CommandSyncNote") as mock_command:
            response = client.post(
                "/api/actions/sync_note",
                json={"file_path": "/etc/passwd", "args": {}, "row": {}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_command.assert_not_called()

    def test_create_note_action_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"

        with patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_command:
            response = client.post(
                "/api/actions/create_note",
                json={"file_path": "/etc/passwd", "args": {}, "row": {}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_command.assert_not_called()

    def test_archive_action_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"

        with patch("bim.commands.archive_note.archive_note.CommandArchiveNote") as mock_command:
            response = client.post(
                "/api/actions/archive",
                json={"file_path": "/etc/passwd", "args": {}, "row": {}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_command.assert_not_called()

    def test_open_action_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"

        with patch("bim.commands.serve._actions.open_in_os") as mock_open_in_os:
            response = client.post(
                "/api/actions/open",
                json={"file_path": "/etc/passwd", "args": {}, "row": {}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_open_in_os.assert_not_called()

    def test_format_action_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"

        with patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_command:
            response = client.post(
                "/api/actions/format",
                json={"file_path": "/etc/passwd", "args": {}, "row": {}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_command.assert_not_called()

    def test_delete_action_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"

        with patch("bim.commands.delete_note.delete_note.CommandDeleteNote") as mock_command:
            response = client.post(
                "/api/actions/delete",
                json={"file_path": "/etc/passwd", "args": {}, "row": {}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_command.assert_not_called()

    def test_import_action_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"

        with patch("bim.commands.import_note.import_note.CommandImportNote") as mock_command:
            response = client.post(
                "/api/actions/import",
                json={"file_path": "/etc/passwd", "args": {}, "row": {}},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_command.assert_not_called()


class TestServeErrors:
    def test_unknown_action_returns_404(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"
        response = client.post(
            "/api/actions/missing",
            json={"file_path": "note.md", "args": {}, "row": {}},
            headers={"X-Buvis-Token": "test-token"},
        )

        assert response.status_code == 404
        assert "Unknown action" in response.json()["detail"]


class TestServeOpen:
    def test_open_file_without_token_returns_401(self, client: TestClient, tmp_path: Path) -> None:
        real_file = tmp_path / "zettels" / "note.md"
        real_file.write_text("placeholder", encoding="utf-8")

        with patch("bim.commands.serve._routes.open_in_os") as mock_open_in_os:
            response = client.post(
                "/api/open",
                json={"path": str(real_file)},
            )

        assert response.status_code == 401
        mock_open_in_os.assert_not_called()

    def test_open_file_outside_vault_returns_403(self, client: TestClient) -> None:
        client.app.state.buvis_token = "test-token"
        outside_path = Path("/etc/passwd")

        with patch("bim.commands.serve._routes.open_in_os") as mock_open_in_os:
            response = client.post(
                "/api/open",
                json={"path": str(outside_path)},
                headers={"X-Buvis-Token": "test-token"},
            )

        assert response.status_code == 403
        mock_open_in_os.assert_not_called()
