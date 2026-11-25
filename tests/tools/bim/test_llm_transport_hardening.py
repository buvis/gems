from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from bim.shared.llm.base import MAX_REPLY_BYTES, BackendError, BackendReason, JsonObject, LLMRequest, run_cli
from bim.shared.llm.http import HttpBackend
from bim.shared.llm.settings import HttpBackendSettings

_BODY_SIZE = 16 * 1024 * 1024
_CHUNK = 64 * 1024


class _LoopbackServer:
    """Real loopback HTTP server that records how much redirect body it managed to send."""

    def __init__(self) -> None:
        self.status = 200
        self.location: str | None = "http://127.0.0.1:1/elsewhere"
        self.ok_payload: dict[str, Any] = {}
        self.sent = 0
        self.body_attempted = False
        self.done = threading.Event()

    def reset(self, status: int, location: str | None, ok_payload: dict[str, Any] | None = None) -> None:
        self.status = status
        self.location = location
        self.ok_payload = ok_payload or {}
        self.sent = 0
        self.body_attempted = False
        self.done.clear()


def _handler_for(state: _LoopbackServer) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        timeout = 10

        def log_message(self, format: str, *args: object) -> None:
            return

        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            try:
                if state.status == 200:
                    self._reply_ok()
                else:
                    self._reply_redirect()
            except OSError:
                pass
            finally:
                state.done.set()

        def _reply_ok(self) -> None:
            content = json.dumps({"choices": [{"message": {"content": json.dumps(state.ok_payload)}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _reply_redirect(self) -> None:
            self.send_response(state.status)
            if state.location is not None:
                self.send_header("Location", state.location)
            self.send_header("Content-Length", str(_BODY_SIZE))
            self.end_headers()
            self.wfile.flush()
            state.body_attempted = True
            chunk = b"x" * _CHUNK
            for _ in range(_BODY_SIZE // _CHUNK):
                self.wfile.write(chunk)
                self.wfile.flush()
                state.sent += _CHUNK

    return Handler


@pytest.fixture
def server() -> Iterator[tuple[_LoopbackServer, str]]:
    state = _LoopbackServer()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(state))
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _backend(endpoint: str) -> HttpBackend:
    return HttpBackend("x", HttpBackendSettings(kind="openai", endpoint=endpoint, model="m"))


class TestRedirectBodyIsNeverRead:
    @pytest.mark.parametrize("status", [302, 307])
    def test_redirect_with_a_huge_body_is_an_exit_error_and_the_body_is_not_downloaded(
        self, server: tuple[_LoopbackServer, str], status: int
    ) -> None:
        state, url = server
        state.reset(status, "http://127.0.0.1:1/elsewhere")
        assert _BODY_SIZE > MAX_REPLY_BYTES

        with pytest.raises(BackendError) as exc:
            _backend(url).complete(LLMRequest(prompt="p"), JsonObject, timeout=5.0)

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == "x"
        assert exc.value.detail.startswith("redirect not followed")
        assert state.done.wait(timeout=15)
        assert state.body_attempted
        assert state.sent < _BODY_SIZE

    def test_redirect_without_a_location_header_is_still_an_exit_error(
        self, server: tuple[_LoopbackServer, str]
    ) -> None:
        state, url = server
        state.reset(302, None)

        with pytest.raises(BackendError) as exc:
            _backend(url).complete(LLMRequest(prompt="p"), JsonObject, timeout=5.0)

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.detail.startswith("redirect not followed")
        assert state.done.wait(timeout=15)
        assert state.sent < _BODY_SIZE

    @pytest.mark.parametrize("payload", [{"a": 1}, {"issuer": "philips", "pages": [1, 2]}])
    def test_ok_reply_from_the_same_server_returns_the_validated_payload(
        self, server: tuple[_LoopbackServer, str], payload: dict[str, Any]
    ) -> None:
        state, url = server
        state.reset(200, None, payload)

        result = _backend(url).complete(LLMRequest(prompt="p"), JsonObject, timeout=5.0)

        assert type(result) is JsonObject
        assert result.root == payload


_SLEEPER = "import time; time.sleep(60)"


def _gone(pid: int, wait: float = 5.0) -> bool:
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[int]]:
    pids: list[int] = []
    real_popen = subprocess.Popen

    def recording_popen(*args: Any, **kwargs: Any) -> subprocess.Popen[Any]:
        proc = real_popen(*args, **kwargs)
        pids.append(proc.pid)
        return proc

    monkeypatch.setattr("bim.shared.llm.base.subprocess.Popen", recording_popen)
    try:
        yield pids
    finally:
        for pid in pids:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass


class TestThreadStartFailure:
    @pytest.mark.parametrize("failing_call", [1, 2, 3])
    def test_thread_start_failure_is_an_exit_error_and_the_child_does_not_keep_running(
        self, monkeypatch: pytest.MonkeyPatch, spawned: list[int], failing_call: int
    ) -> None:
        real_start = threading.Thread.start
        calls: list[int] = []

        def flaky_start(self: threading.Thread) -> None:
            calls.append(1)
            if len(calls) == failing_call:
                raise RuntimeError("can't start new thread")
            real_start(self)

        monkeypatch.setattr("bim.shared.llm.base.threading.Thread.start", flaky_start)
        began = time.monotonic()

        with pytest.raises(BackendError) as exc:
            run_cli([sys.executable, "-c", _SLEEPER], "prompt", timeout=30, backend="x")

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == "x"
        assert time.monotonic() - began < 15
        assert len(spawned) == 1
        assert _gone(spawned[0])


_TOOL = """#!{python}
import json
import os
import sys

stdin = sys.stdin.read()
print(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(), "stdin": stdin}}))
"""


class TestRelativeExecutable:
    @pytest.mark.parametrize(
        ("args", "prompt"),
        [(["./rel-arg", "--flag"], "prompt"), (["../up", "-x", "plain"], "other prompt"), ([], "")],
    )
    def test_relative_executable_runs_with_literal_arguments_in_a_fresh_temp_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: list[str], prompt: str
    ) -> None:
        tool = tmp_path / "tool"
        tool.write_text(_TOOL.format(python=sys.executable))
        tool.chmod(0o755)
        monkeypatch.chdir(tmp_path)

        out = run_cli(["./tool", *args], prompt, timeout=30, backend="x")

        reply = json.loads(out)
        assert reply["argv"] == args
        assert reply["stdin"] == prompt
        assert Path(reply["cwd"]).resolve() != tmp_path.resolve()

    def test_runs_the_file_which_found_when_the_path_climbs_out_of_a_symlink(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # work/link -> real/sub, so the OS reads work/link/../bin/tool as real/bin/tool;
        # normalizing the string first would pick the decoy at work/bin/tool.
        for where, marker in (("real", "checked"), ("work", "decoy")):
            tool = tmp_path / where / "bin" / "tool"
            tool.parent.mkdir(parents=True)
            tool.write_text(f"#!{sys.executable}\nprint({marker!r})\n")
            tool.chmod(0o755)
        (tmp_path / "real" / "sub").mkdir()
        (tmp_path / "work" / "link").symlink_to(tmp_path / "real" / "sub")
        monkeypatch.chdir(tmp_path / "work")

        out = run_cli(["link/../bin/tool"], "", timeout=30, backend="x")

        assert out.strip() == "checked"

    @pytest.mark.parametrize("name", ["./does-not-exist", "no-such-tool-for-bim-tests"])
    def test_missing_executable_is_an_exit_error_naming_the_path_problem(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
    ) -> None:
        monkeypatch.chdir(tmp_path)

        with pytest.raises(BackendError) as exc:
            run_cli([name, "arg"], "prompt", timeout=30, backend="x")

        assert exc.value.reason is BackendReason.EXIT
        assert "is not on PATH" in exc.value.detail
