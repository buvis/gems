from __future__ import annotations

import signal
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx2")

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


class TestServeLifespan:
    def test_watcher_runs_for_app_lifetime(self, tmp_path: Path) -> None:
        with (
            patch("bim.commands.serve._app.start_watcher", new_callable=AsyncMock) as start,
            patch("bim.commands.serve._app.stop_watcher", new_callable=AsyncMock) as stop,
        ):
            app = create_app(default_directory=str(tmp_path), archive_directory="archive")
            with TestClient(app):
                start.assert_awaited_once_with(str(tmp_path))
                stop.assert_not_awaited()
            stop.assert_awaited_once()


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

    def test_non_loopback_host_installs_explicit_allowed_hosts_and_warns(self, tmp_path: Path) -> None:
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
        assert set(trusted_host_middlewares[0].kwargs["allowed_hosts"]) == {"127.0.0.1", "localhost", "[::1]"}
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
                test_client.auth = ("bim", app.state.buvis_token)
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

        mock_create_app.assert_called_once_with(
            "zettels",
            "archive",
            host="0.0.0.0",
            business_triage_root=None,
            doc_settings=None,
            path_projects=None,
            path_daily=None,
            path_articles=None,
        )
        mock_uvicorn_run.assert_called_once_with(
            mock_app, host="0.0.0.0", port=9001, log_level="info", access_log=False
        )


class TestRemoteTokenHandoff:
    @pytest.mark.parametrize("interrupt", [False, True])
    def test_private_file_exists_only_during_server_lifetime(self, tmp_path: Path, interrupt: bool) -> None:
        from bim.params.serve import ServeParams

        params = ServeParams(default_directory=str(tmp_path), host="0.0.0.0", no_browser=True)
        written = []
        from buvis.pybase.filesystem.atomic_write import atomic_write_text

        def record_write(path, content, **kwargs):
            written.append(path)
            atomic_write_text(path, content, **kwargs)

        def run_server(app, **kwargs):
            assert len(written) == 1
            token_path = written[0]
            assert token_path.read_text() == app.state.buvis_token
            assert token_path.stat().st_mode & 0o777 == 0o600
            assert token_path.parent.stat().st_mode & 0o777 == 0o700
            assert kwargs["access_log"] is False
            if interrupt:
                raise KeyboardInterrupt

        with (
            patch("buvis.pybase.filesystem.atomic_write.atomic_write_text", side_effect=record_write),
            patch("uvicorn.run", side_effect=run_server),
            console.capture() as capture,
        ):
            if interrupt:
                with pytest.raises(KeyboardInterrupt):
                    CommandServe(params).execute()
            else:
                CommandServe(params).execute()
        assert len(written) == 1
        assert not written[0].parent.exists()
        assert str(written[0]) in capture.get().replace("\n", "")

    @pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="POSIX signals only")
    @pytest.mark.parametrize("signame", ["SIGTERM", "SIGHUP"])
    def test_token_directory_removed_when_uvicorn_reraises_stop_signal(self, tmp_path: Path, signame: str) -> None:
        from bim.params.serve import ServeParams

        signum = getattr(signal, signame)
        previous = signal.getsignal(signum)
        token_dirs = []

        def run_server(app, **kwargs):
            token_dirs.extend(Path(tempfile.gettempdir()).glob("bim-serve-*"))
            # uvicorn restores the prior handler, then re-raises the captured signal.
            signal.raise_signal(signum)

        params = ServeParams(default_directory=str(tmp_path), host="0.0.0.0", no_browser=True)
        with (
            patch.object(tempfile, "tempdir", str(tmp_path)),
            patch("uvicorn.run", side_effect=run_server),
            pytest.raises(SystemExit),
        ):
            CommandServe(params).execute()

        assert len(token_dirs) == 1
        assert not token_dirs[0].exists()
        assert signal.getsignal(signum) == previous

    @pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="POSIX signals")
    def test_sighup_stops_a_real_server_gracefully_without_traceback(self, tmp_path: Path) -> None:
        import socket
        import subprocess
        import sys
        import time

        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        script = (
            "import tempfile\n"
            f"tempfile.tempdir = {str(tmp_path)!r}\n"
            "from bim.commands.serve.serve import CommandServe\n"
            "from bim.params.serve import ServeParams\n"
            f"CommandServe(ServeParams(default_directory={str(tmp_path)!r}, host='0.0.0.0', port={port},"
            " no_browser=True)).execute()\n"
        )
        server = subprocess.Popen(
            [sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                pytest.fail("server did not start")
            server.send_signal(signal.SIGHUP)
            output, _ = server.communicate(timeout=30)
        finally:
            if server.poll() is None:
                server.kill()

        assert "Traceback" not in output
        assert "Shutting down" in output
        assert not list(tmp_path.glob("bim-serve-*"))


class TestServeBrowserStartup:
    @pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.1"])
    def test_remote_bind_leaves_browser_to_tunnel_client(self, tmp_path: Path, host: str) -> None:
        from bim.params.serve import ServeParams

        with patch("webbrowser.open") as open_browser, patch("uvicorn.run"):
            CommandServe(ServeParams(default_directory=str(tmp_path), host=host)).execute()
        open_browser.assert_not_called()

    def test_loopback_still_opens_local_browser(self, tmp_path: Path) -> None:
        from bim.params.serve import ServeParams

        with patch("webbrowser.open") as open_browser, patch("uvicorn.run"):
            CommandServe(ServeParams(default_directory=str(tmp_path))).execute()
        open_browser.assert_called_once_with("http://127.0.0.1:8000")
