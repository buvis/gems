"""Remote authentication gates the browser, every API route, and event streams."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from bim.commands.serve._app import create_app
from bim.commands.serve._security import TOKEN_HEADER
from starlette.testclient import TestClient


@pytest.fixture
def remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.chdir(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("---\ntitle: Scratch\n---\n\n# Body\n\nPRIVATE-NOTE\n")
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html><head></head><body>dashboard</body></html>")

    async def finite_events(queue):
        from bim.commands.serve._sse import _subscribers

        try:
            yield 'data: {"type":"file_change","files":[]}\n\n'
        finally:
            _subscribers.discard(queue)

    with (
        patch("bim.commands.serve._app.STATIC_DIR", static),
        patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock),
        patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock),
        patch("bim.commands.serve._sse._event_stream", finite_events),
    ):
        app = create_app(str(vault), host="0.0.0.0")
        with TestClient(app, base_url="http://127.0.0.1") as client:
            yield client, vault, app.state.buvis_token


class TestRemoteAuthentication:
    @pytest.mark.parametrize("credentials", ["missing", "invalid", "valid"])
    @pytest.mark.parametrize("endpoint", ["health", "queries", "queries/inbox", "zettels", "events"])
    def test_read_token_matrix(self, remote, endpoint: str, credentials: str) -> None:
        client, vault, token = remote
        path = f"/api/zettels/{vault / 'note.md'}" if endpoint == "zettels" else f"/api/{endpoint}"
        headers = {} if credentials == "missing" else {TOKEN_HEADER: token if credentials == "valid" else "wrong"}
        response = client.get(path, headers=headers)
        if credentials == "valid":
            assert response.status_code == 200
        else:
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == 'Basic realm="bim", charset="UTF-8"'
            assert "PRIVATE-NOTE" not in response.text

    @pytest.mark.parametrize(
        "method,endpoint",
        [
            ("POST", "queries/all/exec"),
            ("POST", "queries/_adhoc"),
            ("PATCH", "zettels/note.md"),
            ("POST", "open"),
            ("POST", "actions/archive"),
            ("OPTIONS", "health"),
            ("GET", "future-endpoint"),
        ],
    )
    def test_every_api_request_requires_auth_before_validation(self, remote, method: str, endpoint: str) -> None:
        client, _, _ = remote
        assert client.request(method, f"/api/{endpoint}").status_code == 401

    @pytest.mark.parametrize("host", ["evil.example", "www.localhost", "0.0.0.0", "localhost.evil.example"])
    def test_foreign_host_rejected_even_with_valid_token(self, remote, host: str) -> None:
        client, _, token = remote
        assert client.get("/api/health", headers={"Host": host, TOKEN_HEADER: token}).status_code == 400

    @pytest.mark.parametrize("host", ["localhost:8000", "127.0.0.1:8000", "[::1]:8000"])
    def test_tunnel_host_allowed(self, remote, host: str) -> None:
        client, _, token = remote
        assert client.get("/api/health", headers={"Host": host, TOKEN_HEADER: token}).status_code == 200

    def test_browser_challenge_then_authenticated_page_fetch_mutation_and_eventsource(self, remote) -> None:
        client, vault, token = remote
        response = client.get("/")
        assert response.status_code == 401
        assert "Basic" in response.headers["www-authenticate"]
        client.auth = ("bim", token)
        page = client.get("/")
        assert page.status_code == 200
        assert "dashboard" in page.text
        assert token not in page.text
        assert page.headers["cache-control"] == "no-store"
        assert client.get("/api/queries").status_code == 200
        assert client.get(f"/api/zettels/{vault / 'note.md'}").status_code == 200
        # Remote frontend supplies an empty token header; cached Basic auth must work.
        result = client.post(
            "/api/queries/_adhoc",
            headers={TOKEN_HEADER: "", "Origin": "http://127.0.0.1"},
            json={"spec": {"columns": [{"field": "title"}]}},
        )
        assert result.status_code == 200, result.text
        with client.stream("GET", "/api/events") as events:
            assert events.status_code == 200
            assert "text/event-stream" in events.headers["content-type"]
            assert 'data: {"type":"file_change"' in "".join(events.iter_text())

    @pytest.mark.parametrize("auth_kind", ["header", "browser"])
    def test_authenticated_mutation_updates_scratch_note(self, remote, auth_kind: str) -> None:
        client, vault, token = remote
        headers = {TOKEN_HEADER: token}
        if auth_kind == "browser":
            client.auth = ("bim", token)
            headers = {TOKEN_HEADER: "", "Origin": "http://127.0.0.1"}
        note = vault / "note.md"
        response = client.patch(f"/api/zettels/{note}", headers=headers, json={"field": "title", "value": "Updated"})
        assert response.status_code == 200, response.text
        assert "Updated" in note.read_text()

    def test_explicit_invalid_header_does_not_fall_back_to_browser_auth(self, remote) -> None:
        client, _, token = remote
        client.auth = ("bim", token)
        response = client.get("/api/health", headers={TOKEN_HEADER: "wrong"})
        assert response.status_code == 401

    def test_cross_site_fetch_metadata_rejected_without_origin(self, remote) -> None:
        client, _, token = remote
        client.auth = ("bim", token)
        response = client.post("/api/queries/_adhoc", headers={"Sec-Fetch-Site": "cross-site"}, json={"spec": {}})
        assert response.status_code == 403

    @pytest.mark.parametrize("authorization", ["Basic !", "Basic /w==", "Bearer wrong", "Basic Ymlt", ""])
    def test_malformed_browser_auth_rejected(self, remote, authorization: str) -> None:
        client, _, _ = remote
        assert client.get("/api/health", headers={"Authorization": authorization}).status_code == 401

    @pytest.mark.parametrize("username,password", [("wrong", "valid"), ("bim", "wrong")])
    def test_invalid_browser_credentials_rejected(self, remote, username: str, password: str) -> None:
        client, _, token = remote
        client.auth = (username, token if password == "valid" else password)
        assert client.get("/").status_code == 401

    @pytest.mark.parametrize("origin", ["http://evil.example", "null", "https://127.0.0.1"])
    def test_browser_credentials_do_not_allow_cross_origin_mutations(self, remote, origin: str) -> None:
        client, _, token = remote
        client.auth = ("bim", token)
        result = client.post("/api/queries/_adhoc", headers={"Origin": origin}, json={"spec": {}})
        assert result.status_code == 403

    def test_token_in_url_does_not_authenticate(self, remote) -> None:
        client, _, token = remote
        response = client.get("/api/health", params={"token": token})
        assert response.status_code == 401
        assert token not in response.text

    def test_loopback_behavior_unchanged(self, tmp_path: Path) -> None:
        app = create_app(str(tmp_path))
        with TestClient(app, base_url="http://127.0.0.1") as client:
            assert client.get("/api/health").status_code == 200
            assert client.post("/api/open", json={"path": str(tmp_path / "missing")}).status_code == 401
            basic = base64.b64encode(f"bim:{app.state.buvis_token}".encode()).decode()
            assert (
                client.post(
                    "/api/open", headers={"Authorization": f"Basic {basic}"}, json={"path": str(tmp_path / "missing")}
                ).status_code
                == 401
            )


class TestEventStreamBootstrap:
    def test_stream_sends_initial_frame_without_waiting_for_vault_changes(self) -> None:
        import asyncio

        from bim.commands.serve._sse import _event_stream, _subscribers

        async def receive_first_frame():
            queue = asyncio.Queue()
            _subscribers.add(queue)
            stream = _event_stream(queue)
            try:
                assert await asyncio.wait_for(anext(stream), timeout=0.1) == ": connected\n\n"
            finally:
                await stream.aclose()
            assert queue not in _subscribers

        asyncio.run(receive_first_frame())
