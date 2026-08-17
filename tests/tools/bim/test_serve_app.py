from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from bim.commands.serve._app import create_app
from bim.commands.serve.serve import CommandServe
from buvis.pybase.adapters import console
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.testclient import TestClient


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


class TestServeTrustedHost:
    def test_foreign_host_header_rejected(self, tmp_path: Path) -> None:
        zettels_dir = tmp_path / "zettels"
        zettels_dir.mkdir()
        with (
            patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
            patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
        ):
            app = create_app(default_directory=str(zettels_dir), archive_directory="archive")
            with TestClient(app, base_url="http://evil.example.com") as test_client:
                response = test_client.get("/api/health")

        assert response.status_code == 400

    def test_matching_loopback_host_passes_through(self, tmp_path: Path) -> None:
        zettels_dir = tmp_path / "zettels"
        zettels_dir.mkdir()
        with (
            patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
            patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
        ):
            app = create_app(default_directory=str(zettels_dir), archive_directory="archive")
            with TestClient(app, base_url="http://127.0.0.1") as test_client:
                response = test_client.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_non_loopback_host_installs_wildcard_allowed_hosts_and_warns(self, tmp_path: Path) -> None:
        zettels_dir = tmp_path / "zettels"
        zettels_dir.mkdir()
        with (
            patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
            patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
            console.capture() as capture,
        ):
            app = create_app(
                default_directory=str(zettels_dir),
                archive_directory="archive",
                host="0.0.0.0",
            )

        trusted_host_middlewares = [m for m in app.user_middleware if m.cls is TrustedHostMiddleware]

        assert len(trusted_host_middlewares) == 1
        assert trusted_host_middlewares[0].kwargs["allowed_hosts"] == ["*"]
        assert "0.0.0.0" in capture.get()

    def test_non_loopback_host_still_rejects_mutating_request_without_token(self, tmp_path: Path) -> None:
        zettels_dir = tmp_path / "zettels"
        zettels_dir.mkdir()
        with (
            patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
            patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
        ):
            app = create_app(default_directory=str(zettels_dir), archive_directory="archive", host="0.0.0.0")
            with TestClient(app, base_url="http://127.0.0.1") as test_client:
                response = test_client.post(
                    "/api/actions/some-action",
                    json={"file_path": "note.md", "args": {}, "row": {}},
                )

        assert response.status_code == 401


class TestServeIndexTokenInjection:
    def test_get_root_injects_token_before_head_close(self, tmp_path: Path) -> None:
        zettels_dir = tmp_path / "zettels"
        zettels_dir.mkdir()
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text(
            "<html><head><title>bim</title></head><body>app</body></html>",
            encoding="utf-8",
        )
        (static_dir / "app.js").write_text("console.log('asset');", encoding="utf-8")

        with (
            patch("bim.commands.serve._app.STATIC_DIR", static_dir),
            patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
            patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
        ):
            app = create_app(default_directory=str(zettels_dir), archive_directory="archive")
            with TestClient(app, base_url="http://127.0.0.1") as test_client:
                index_response = test_client.get("/")
                asset_response = test_client.get("/app.js")

        token = app.state.buvis_token
        expected_script = f'<script>window.__BUVIS_TOKEN__ = "{token}";</script>'

        assert index_response.status_code == 200
        body = index_response.text
        assert expected_script in body
        assert body.index(expected_script) < body.index("</head>")
        assert "<title>bim</title>" in body

        assert asset_response.status_code == 200
        assert asset_response.text == "console.log('asset');"

    def test_get_root_omits_token_on_non_loopback_host(self, tmp_path: Path) -> None:
        zettels_dir = tmp_path / "zettels"
        zettels_dir.mkdir()
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        index_html = "<html><head><title>bim</title></head><body>app</body></html>"
        (static_dir / "index.html").write_text(index_html, encoding="utf-8")

        with (
            patch("bim.commands.serve._app.STATIC_DIR", static_dir),
            patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
            patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
        ):
            app = create_app(default_directory=str(zettels_dir), archive_directory="archive", host="0.0.0.0")
            with TestClient(app, base_url="http://127.0.0.1") as test_client:
                index_response = test_client.get("/")

        token = app.state.buvis_token
        body = index_response.text

        assert index_response.status_code == 200
        assert token not in body
        assert "__BUVIS_TOKEN__" not in body
        assert body == index_html

    def test_get_root_not_in_openapi_schema(self, tmp_path: Path) -> None:
        zettels_dir = tmp_path / "zettels"
        zettels_dir.mkdir()
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text(
            "<html><head><title>bim</title></head><body>app</body></html>",
            encoding="utf-8",
        )

        with (
            patch("bim.commands.serve._app.STATIC_DIR", static_dir),
            patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
            patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
        ):
            app = create_app(default_directory=str(zettels_dir), archive_directory="archive")

        assert "/" not in app.openapi()["paths"]

    def test_get_root_missing_head_close_still_returns_200_and_warns(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``console.capture()`` cannot be used here: ``TestClient`` runs the
        handler on a worker thread and Rich buffers per thread, so the capture
        entered on the main thread never sees it. ``capsys`` captures the real
        stdout and does observe it."""
        zettels_dir = tmp_path / "zettels"
        zettels_dir.mkdir()
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text(
            "<html><body>app</body></html>",
            encoding="utf-8",
        )

        with (
            patch("bim.commands.serve._app.STATIC_DIR", static_dir),
            patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
            patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
        ):
            app = create_app(default_directory=str(zettels_dir), archive_directory="archive")
            with TestClient(app, base_url="http://127.0.0.1") as test_client:
                response = test_client.get("/")

        assert response.status_code == 200
        assert "</head>" in capsys.readouterr().out


class TestServeIndexMissing:
    def test_index_missing_returns_404(self, tmp_path: Path) -> None:
        zettels_dir = tmp_path / "zettels"
        zettels_dir.mkdir()
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "app.js").write_text("console.log('asset');", encoding="utf-8")

        with (
            patch("bim.commands.serve._app.STATIC_DIR", static_dir),
            patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
            patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
        ):
            app = create_app(default_directory=str(zettels_dir), archive_directory="archive")
            with TestClient(app, base_url="http://127.0.0.1") as test_client:
                response = test_client.get("/")

        assert response.status_code == 404


class TestCommandServeExecute:
    def test_execute_passes_host_to_create_app(self) -> None:
        from bim.params.serve import ServeParams

        params = ServeParams(
            default_directory="zettels",
            archive_directory="archive",
            host="0.0.0.0",
            port=9001,
            no_browser=True,
        )
        cmd = CommandServe(params=params)

        with (
            patch("bim.commands.serve._app.create_app") as mock_create_app,
            patch("uvicorn.run") as mock_uvicorn_run,
        ):
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app

            cmd.execute()

        mock_create_app.assert_called_once_with("zettels", "archive", host="0.0.0.0")
        mock_uvicorn_run.assert_called_once_with(mock_app, host="0.0.0.0", port=9001, log_level="info")
