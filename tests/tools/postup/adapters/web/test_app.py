"""App-factory and payload-endpoint tests for ``postup serve``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from postup.adapters.web.app import create_app
from starlette.testclient import TestClient

from tests.tools.postup.adapters.web.conftest import (
    SAMPLE_DATA,
    SAMPLE_EPICS,
    SAMPLE_HISTORY,
    SAMPLE_PREV,
    make_settings,
    write_contracts,
)


def _client_over(out_dir: Path, *, host: str = "127.0.0.1") -> TestClient:
    with (
        patch("postup.adapters.web.app.start_watcher", new_callable=AsyncMock),
        patch("postup.adapters.web.app.stop_watcher", new_callable=AsyncMock),
    ):
        app = create_app(make_settings(out_dir), host=host)
        return TestClient(app, base_url="http://127.0.0.1")


class TestHealth:
    def test_health_ok(self, client: TestClient) -> None:
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestTrustedHost:
    def test_foreign_host_rejected(self, out_dir: Path) -> None:
        with (
            patch("postup.adapters.web.app.start_watcher", new_callable=AsyncMock),
            patch("postup.adapters.web.app.stop_watcher", new_callable=AsyncMock),
        ):
            app = create_app(make_settings(out_dir), host="127.0.0.1")
            with TestClient(app, base_url="http://evil.example.com") as c:
                assert c.get("/api/health").status_code == 400

    def test_loopback_host_passes(self, out_dir: Path) -> None:
        with _client_over(out_dir) as c:
            assert c.get("/api/health").status_code == 200


class TestPayloadEndpoints:
    def test_data_roundtrip(self, out_dir: Path) -> None:
        write_contracts(out_dir)
        with _client_over(out_dir) as c:
            r = c.get("/api/data")
        assert r.status_code == 200
        assert r.json() == SAMPLE_DATA

    def test_epics_roundtrip(self, out_dir: Path) -> None:
        write_contracts(out_dir)
        with _client_over(out_dir) as c:
            r = c.get("/api/epics")
        assert r.status_code == 200
        assert r.json() == SAMPLE_EPICS

    def test_data_prev_roundtrip(self, out_dir: Path) -> None:
        write_contracts(out_dir)
        with _client_over(out_dir) as c:
            r = c.get("/api/data-prev")
        assert r.status_code == 200
        assert r.json() == SAMPLE_PREV

    def test_history_roundtrip_is_raw_text(self, out_dir: Path) -> None:
        write_contracts(out_dir)
        with _client_over(out_dir) as c:
            r = c.get("/api/history")
        assert r.status_code == 200
        assert r.text == SAMPLE_HISTORY


class TestEmptyState:
    def test_never_collected_data_returns_explicit_empty_state_not_500(self, client: TestClient) -> None:
        r = client.get("/api/data")
        assert r.status_code == 200
        body = r.json()
        assert body["repos"] == []
        assert body["schema_version"] == SAMPLE_DATA["schema_version"]

    def test_epics_absent_returns_404(self, client: TestClient) -> None:
        assert client.get("/api/epics").status_code == 404

    def test_data_prev_absent_returns_404(self, client: TestClient) -> None:
        assert client.get("/api/data-prev").status_code == 404

    def test_history_absent_returns_empty_body(self, client: TestClient) -> None:
        r = client.get("/api/history")
        assert r.status_code == 200
        assert r.text == ""

    def test_unreadable_data_returns_422_not_500(self, out_dir: Path) -> None:
        (out_dir / "data.json").write_text("{ not json", encoding="utf-8")
        with _client_over(out_dir) as c:
            assert c.get("/api/data").status_code == 422


class TestStaticIndex:
    def _index_html(self) -> str:
        return "<html><head><title>postup</title></head><body>app</body></html>"

    def test_index_injects_token_on_loopback(self, out_dir: Path, tmp_path: Path) -> None:
        build = tmp_path / "build"
        build.mkdir()
        (build / "index.html").write_text(self._index_html(), encoding="utf-8")
        (build / "app.js").write_text("console.log(1)", encoding="utf-8")
        with (
            patch("postup.adapters.web.app.BUILD_DIR", build),
            patch("postup.adapters.web.app.start_watcher", new_callable=AsyncMock),
            patch("postup.adapters.web.app.stop_watcher", new_callable=AsyncMock),
        ):
            app = create_app(make_settings(out_dir), host="127.0.0.1")
            with TestClient(app, base_url="http://127.0.0.1") as c:
                index = c.get("/")
                asset = c.get("/app.js")
        token = app.state.buvis_token
        script = f'<script>window.__BUVIS_TOKEN__ = "{token}";</script>'
        assert index.status_code == 200
        assert script in index.text
        assert index.text.index(script) < index.text.index("</head>")
        assert asset.status_code == 200 and asset.text == "console.log(1)"

    def test_index_omits_token_on_non_loopback(self, out_dir: Path, tmp_path: Path) -> None:
        build = tmp_path / "build"
        build.mkdir()
        html = self._index_html()
        (build / "index.html").write_text(html, encoding="utf-8")
        with (
            patch("postup.adapters.web.app.BUILD_DIR", build),
            patch("postup.adapters.web.app.start_watcher", new_callable=AsyncMock),
            patch("postup.adapters.web.app.stop_watcher", new_callable=AsyncMock),
        ):
            app = create_app(make_settings(out_dir), host="0.0.0.0")
            with TestClient(app, base_url="http://127.0.0.1") as c:
                index = c.get("/")
        assert index.status_code == 200
        assert "__BUVIS_TOKEN__" not in index.text
        assert index.text == html

    def test_missing_build_serves_fallback_message(self, out_dir: Path, tmp_path: Path) -> None:
        empty = tmp_path / "nobuild"
        empty.mkdir()
        with (
            patch("postup.adapters.web.app.BUILD_DIR", empty),
            patch("postup.adapters.web.app.start_watcher", new_callable=AsyncMock),
            patch("postup.adapters.web.app.stop_watcher", new_callable=AsyncMock),
        ):
            app = create_app(make_settings(out_dir), host="127.0.0.1")
            with TestClient(app, base_url="http://127.0.0.1") as c:
                r = c.get("/")
        assert r.status_code == 200
        assert "Frontend not built" in r.text


class TestServedBuildMatchesLoaderContract:
    """The endpoint paths must match the committed loader's ``loadFromApi``."""

    def test_loader_fetches_the_paths_the_routes_expose(self) -> None:
        loader = Path(__file__).resolve().parents[5] / "src/tools/postup/adapters/web/frontend/src/lib/payload.js"
        text = loader.read_text(encoding="utf-8")
        for path in ("/api/data", "/api/epics", "/api/data-prev", "/api/history"):
            assert f"'{path}'" in text, f"loader no longer fetches {path}"
