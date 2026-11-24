from __future__ import annotations

import _thread
import os
import signal
import sys
import tempfile
import threading
import time
import tracemalloc
from pathlib import Path

import pytest
from bim.shared.llm import (
    BackendError,
    BackendReason,
    CommandBackendSettings,
    JsonObject,
    LLMConfigError,
    LLMRequest,
    build_registry,
)
from bim.shared.llm.base import MAX_REPLY_BYTES, MAX_STDERR_BYTES, run_cli
from bim.shared.llm.command import CommandBackend
from bim.shared.llm.registry import build_backend
from pydantic import BaseModel, ConfigDict

_ECHO_STDIN = "import sys; data = sys.stdin.buffer.read(); sys.stdout.buffer.write(b'got:' + data)"
_PRINT_CWD = "import os, sys; sys.stdout.write(os.getcwd())"
_SLEEP = "import time; time.sleep(60)"
_SPAWN_CHILD_THEN_SLEEP = (
    "import os, subprocess, sys, time\n"
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    "with open(sys.argv[1], 'w') as fh:\n"
    "    fh.write(f'{os.getpid()} {child.pid}\\n{os.getcwd()}')\n"
    "time.sleep(60)\n"
)
_RECORD = "import os, sys\nwith open(sys.argv[1], 'w') as fh:\n    fh.write(f'{os.getpid()}\\n{os.getcwd()}')\n"
_RECORD_THEN_FAIL = {
    "exit": _RECORD + "sys.exit(1)\n",
    "timeout": _RECORD + "import time\ntime.sleep(60)\n",
    "overflow": _RECORD + "while True:\n    sys.stdout.buffer.write(b'x' * 65536)\n",
}
_ECHO_ARGS_AND_STDIN = (
    "import json, sys\n"
    "stdin = sys.stdin.buffer.read().decode('utf-8')\n"
    "sys.stdout.write(json.dumps({'args': sys.argv[1:], 'stdin': stdin}))\n"
)


class _Tx(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: str
    currency: str


class _Echo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    args: list[str]
    stdin: str


def _py(script: str, *args: str) -> list[str]:
    return [sys.executable, "-c", script, *args]


def _is_gone(pid: int, limit: float = 2.0) -> bool:
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def _read_pids(pid_file: Path) -> tuple[int, ...]:
    return tuple(int(part) for part in pid_file.read_text().splitlines()[0].split())


def _read_cwd(pid_file: Path) -> Path:
    return Path(pid_file.read_text().splitlines()[1])


def _kill_leftovers(pid_file: Path) -> None:
    if not pid_file.exists() or len(pid_file.read_text().splitlines()) < 2:
        return
    for pid in _read_pids(pid_file):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


class TestCommandRunCli:
    @pytest.mark.parametrize(
        "prompt",
        ["", "cena 12,50 Kč\nřádek 2", "x" * 1_000_003, "ř" * 500_001 + "!"],
        ids=["empty", "czech", "ascii-1000003", "multibyte-1000003-bytes"],
    )
    def test_command_run_cli_sends_the_prompt_on_stdin_and_returns_stdout(self, prompt: str) -> None:
        assert run_cli(_py(_ECHO_STDIN), prompt, timeout=4.0, backend="shell") == "got:" + prompt

    def test_command_run_cli_runs_in_a_fresh_bim_llm_temp_dir_that_is_removed_after(self) -> None:
        first = Path(run_cli(_py(_PRINT_CWD), "", timeout=4.0, backend="shell"))
        second = Path(run_cli(_py(_PRINT_CWD), "", timeout=4.0, backend="shell"))

        assert first != second
        for cwd in (first, second):
            assert cwd.name.startswith("bim-llm-")
            assert cwd.parent.resolve() == Path(tempfile.gettempdir()).resolve()
            assert not cwd.exists()

    @pytest.mark.parametrize(
        ("failure", "reason"),
        [("exit", BackendReason.EXIT), ("timeout", BackendReason.TIMEOUT), ("overflow", BackendReason.EXIT)],
    )
    def test_command_run_cli_removes_its_temp_dir_when_the_command_fails(
        self, tmp_path: Path, failure: str, reason: BackendReason
    ) -> None:
        record = tmp_path / "record"
        try:
            with pytest.raises(BackendError) as exc:
                run_cli(_py(_RECORD_THEN_FAIL[failure], str(record)), "", timeout=1.0, backend="shell")

            assert exc.value.reason is reason
            cwd = _read_cwd(record)
            assert cwd.name.startswith("bim-llm-")
            assert not cwd.exists()
        finally:
            _kill_leftovers(record)

    @pytest.mark.parametrize("argv0", ["bim-llm-no-such-cli", sys.executable + "-missing"])
    def test_command_run_cli_rejects_a_missing_executable_before_spawning(self, argv0: str) -> None:
        with pytest.raises(BackendError) as exc:
            run_cli([argv0, "-p"], "hello", timeout=2.0, backend="local-cli")

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == "local-cli"
        assert f"{argv0!r} is not on PATH" in exc.value.detail

    def test_command_run_cli_maps_a_spawn_os_error_to_exit(self, tmp_path: Path) -> None:
        broken = tmp_path / "bad-cli"
        broken.write_text("#!/nonexistent/bim-llm-interpreter\n")
        broken.chmod(0o755)

        with pytest.raises(BackendError) as exc:
            run_cli([str(broken)], "hello", timeout=2.0, backend="shell")

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == "shell"
        assert "No such file or directory" in exc.value.detail

    def test_command_run_cli_rejects_a_lone_surrogate_prompt_without_running(self, tmp_path: Path) -> None:
        marker = tmp_path / "ran"
        script = "import sys; open(sys.argv[1], 'w').write('ran')"

        with pytest.raises(BackendError) as exc:
            run_cli(_py(script, str(marker)), "total \ud800 CZK", timeout=2.0, backend="pdf-cli")

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == "pdf-cli"
        assert "prompt is not valid UTF-8" in exc.value.detail
        assert not marker.exists()

    def test_command_run_cli_timeout_kills_the_whole_process_group(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "pids"
        try:
            started = time.monotonic()
            with pytest.raises(BackendError) as exc:
                run_cli(_py(_SPAWN_CHILD_THEN_SLEEP, str(pid_file)), "", timeout=2.0, backend="slow-cli")
            elapsed = time.monotonic() - started

            assert exc.value.reason is BackendReason.TIMEOUT
            assert exc.value.backend == "slow-cli"
            assert elapsed < 2.0 + 1.5
            parent, child = _read_pids(pid_file)
            assert _is_gone(parent)
            assert _is_gone(child)
        finally:
            _kill_leftovers(pid_file)

    def test_command_run_cli_keyboard_interrupt_kills_the_process_group_and_reraises(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "pids"
        stop = threading.Event()

        def interrupt_once_running() -> None:
            deadline = time.monotonic() + 3.0
            while not stop.is_set() and time.monotonic() < deadline:
                if pid_file.exists() and pid_file.read_text().strip():
                    time.sleep(0.3)
                    if not stop.is_set():
                        _thread.interrupt_main()
                    return
                time.sleep(0.05)

        interrupter = threading.Thread(target=interrupt_once_running, daemon=True)
        try:
            interrupter.start()
            with pytest.raises(KeyboardInterrupt):
                run_cli(_py(_SPAWN_CHILD_THEN_SLEEP, str(pid_file)), "", timeout=4.0, backend="shell")

            parent, child = _read_pids(pid_file)
            assert _is_gone(parent)
            assert _is_gone(child)
            assert not _read_cwd(pid_file).exists()
        finally:
            stop.set()
            interrupter.join(timeout=5.0)
            _kill_leftovers(pid_file)

    def test_command_run_cli_endless_stdout_fails_as_overflow_before_the_timeout(self) -> None:
        script = "import sys\nchunk = b'x' * 65536\nwhile True:\n    sys.stdout.buffer.write(chunk)\n"
        started = time.monotonic()

        with pytest.raises(BackendError) as exc:
            run_cli(_py(script), "", timeout=3.0, backend="chatty-cli")

        assert time.monotonic() - started < 3.0
        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == "chatty-cli"
        assert f"output larger than {MAX_REPLY_BYTES} bytes" in exc.value.detail

    def test_command_run_cli_accepts_stdout_of_exactly_the_cap(self) -> None:
        script = f"import sys; sys.stdout.buffer.write(b'y' * {MAX_REPLY_BYTES})"

        out = run_cli(_py(script), "", timeout=4.0, backend="shell")

        assert len(out) == MAX_REPLY_BYTES
        assert set(out) == {"y"}

    @pytest.mark.parametrize(
        "payload",
        [f"b'y' * {MAX_REPLY_BYTES + 1}", f"('\\u00e9' * {MAX_REPLY_BYTES // 2 + 1}).encode('utf-8')"],
        ids=["ascii-one-byte-over", "two-byte-chars-over-in-bytes-under-in-chars"],
    )
    def test_command_run_cli_rejects_stdout_one_byte_over_the_cap(self, payload: str) -> None:
        script = f"import sys; sys.stdout.buffer.write({payload})"

        with pytest.raises(BackendError) as exc:
            run_cli(_py(script), "", timeout=4.0, backend="shell")

        assert exc.value.reason is BackendReason.EXIT
        assert f"output larger than {MAX_REPLY_BYTES} bytes" in exc.value.detail

    def test_command_run_cli_non_zero_exit_reports_the_stderr_excerpt(self) -> None:
        script = "import sys; sys.stdout.write('{}'); sys.stderr.write('\\n  boom: unknown flag --x  \\n'); sys.exit(3)"

        with pytest.raises(BackendError) as exc:
            run_cli(_py(script), "", timeout=2.0, backend="flaky-cli")

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == "flaky-cli"
        assert "boom: unknown flag --x" in exc.value.detail

    def test_command_run_cli_zero_exit_with_stderr_returns_stdout(self) -> None:
        script = "import sys; sys.stderr.write('warning: slow model'); sys.stdout.write('{\"ok\": true}')"

        assert run_cli(_py(script), "", timeout=2.0, backend="shell") == '{"ok": true}'

    def test_command_run_cli_stderr_flood_then_exit_one_gives_a_bounded_excerpt(self) -> None:
        flood = 8 * MAX_STDERR_BYTES
        script = f"import sys; sys.stderr.write('flood-start\\n' + 'Q' * {flood}); sys.stderr.flush(); sys.exit(1)"

        with pytest.raises(BackendError) as exc:
            run_cli(_py(script), "", timeout=3.0, backend="noisy-cli")

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == "noisy-cli"
        assert "flood-start" in exc.value.detail
        assert "Q" * 300 not in exc.value.detail
        assert len(exc.value.detail) < 600

    def test_command_run_cli_endless_stderr_flood_times_out_with_bounded_detail_and_memory(self) -> None:
        script = "import sys\nchunk = b'E' * 65536\nwhile True:\n    sys.stderr.buffer.write(chunk)\n"
        started_tracing = not tracemalloc.is_tracing()
        if started_tracing:
            tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            baseline = tracemalloc.get_traced_memory()[0]
            started = time.monotonic()
            with pytest.raises(BackendError) as exc:
                run_cli(_py(script), "", timeout=1.0, backend="noisy-cli")
            elapsed = time.monotonic() - started
            growth = tracemalloc.get_traced_memory()[1] - baseline
        finally:
            if started_tracing:
                tracemalloc.stop()

        assert elapsed < 1.0 + 1.5
        assert exc.value.reason is BackendReason.TIMEOUT
        assert exc.value.backend == "noisy-cli"
        assert len(exc.value.detail) < 600
        assert growth < 16 * 1024 * 1024

    def test_command_run_cli_non_utf8_stderr_on_failure_is_replaced_not_raised(self) -> None:
        script = "import sys; sys.stderr.buffer.write(b'bad byte \\xff here'); sys.exit(2)"

        with pytest.raises(BackendError) as exc:
            run_cli(_py(script), "", timeout=2.0, backend="shell")

        assert exc.value.reason is BackendReason.EXIT
        assert "bad byte \ufffd here" in exc.value.detail

    def test_command_run_cli_non_utf8_stderr_on_success_returns_stdout(self) -> None:
        script = "import sys; sys.stderr.buffer.write(b'\\xfe\\xff'); sys.stdout.write('fine')"

        assert run_cli(_py(script), "", timeout=2.0, backend="shell") == "fine"

    def test_command_run_cli_invalid_utf8_stdout_is_a_parse_error(self) -> None:
        script = 'import sys; sys.stdout.buffer.write(b\'{"a": "\\xff"}\')'

        with pytest.raises(BackendError) as exc:
            run_cli(_py(script), "", timeout=2.0, backend="latin-cli")

        assert exc.value.reason is BackendReason.PARSE
        assert exc.value.backend == "latin-cli"
        assert exc.value.detail.startswith("output is not UTF-8")


class _FakeRunCli:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout
        self.calls: list[tuple[object, str, float, str]] = []

    def __call__(self, argv: list[str], stdin_text: str, *, timeout: float, backend: str) -> str:
        self.calls.append((argv, stdin_text, timeout, backend))
        return self.stdout


def _settings(argv: list[str], *, unattended: bool = False) -> CommandBackendSettings:
    return CommandBackendSettings(kind="command", argv=argv, unattended=unattended)


class TestCommandBackend:
    @pytest.mark.parametrize(
        ("name", "argv", "request_", "timeout", "model", "stdout", "expected"),
        [
            (
                "shell",
                ["llm", "-m", "{model}", "--system", "$PROMPT"],
                LLMRequest(prompt="extract 12.50 CZK", system="be strict"),
                7.5,
                "qwen3:14b",
                '{"amount": "12.50", "currency": "CZK"}',
                _Tx(amount="12.50", currency="CZK"),
            ),
            (
                "local-llm",
                ["ollama-run"],
                LLMRequest(prompt="total 99 EUR"),
                42.0,
                None,
                '{"amount": "99.00", "currency": "EUR"}',
                _Tx(amount="99.00", currency="EUR"),
            ),
        ],
    )
    def test_command_backend_passes_literal_argv_and_prompt_on_stdin_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
        name: str,
        argv: list[str],
        request_: LLMRequest,
        timeout: float,
        model: str | None,
        stdout: str,
        expected: _Tx,
    ) -> None:
        fake = _FakeRunCli(stdout)
        monkeypatch.setattr("bim.shared.llm.command.run_cli", fake)

        result = CommandBackend(name, _settings(argv)).complete(request_, _Tx, timeout=timeout, model=model)

        assert result == expected
        assert fake.calls == [(argv, request_.as_text(), timeout, name)]
        sent_argv = fake.calls[0][0]
        assert isinstance(sent_argv, list)
        assert all(request_.prompt not in element for element in sent_argv)

    def test_command_backend_validates_stdout_against_json_object(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("bim.shared.llm.command.run_cli", _FakeRunCli('{"issuer_slug": "philips", "pages": [1]}'))

        result = CommandBackend("doc-cli", _settings(["llm"])).complete(LLMRequest(prompt="x"), JsonObject, timeout=5.0)

        assert type(result) is JsonObject
        assert result.root == {"issuer_slug": "philips", "pages": [1]}

    @pytest.mark.parametrize("stdout", ["not json", "```json\n{}\n```", ""])
    def test_command_backend_non_json_stdout_is_a_parse_error(
        self, monkeypatch: pytest.MonkeyPatch, stdout: str
    ) -> None:
        monkeypatch.setattr("bim.shared.llm.command.run_cli", _FakeRunCli(stdout))

        with pytest.raises(BackendError) as exc:
            CommandBackend("shell", _settings(["llm"])).complete(LLMRequest(prompt="x"), _Tx, timeout=5.0)

        assert exc.value.reason is BackendReason.PARSE
        assert exc.value.backend == "shell"

    def test_command_backend_extra_key_in_stdout_is_a_schema_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stdout = '{"amount": "12.50", "currency": "CZK", "note": "surprise"}'
        monkeypatch.setattr("bim.shared.llm.command.run_cli", _FakeRunCli(stdout))

        with pytest.raises(BackendError) as exc:
            CommandBackend("tx-cli", _settings(["llm"])).complete(LLMRequest(prompt="x"), _Tx, timeout=5.0)

        assert exc.value.reason is BackendReason.SCHEMA
        assert exc.value.backend == "tx-cli"
        assert exc.value.detail.startswith("reply does not match _Tx: ")

    def test_command_backend_runs_a_real_command_without_a_shell(self) -> None:
        literal_args = ["$HOME; echo pwned", "{prompt}", "*"]
        backend = CommandBackend("shell", _settings(_py(_ECHO_ARGS_AND_STDIN, *literal_args)))
        request = LLMRequest(prompt="Total: 12,50 Kč", system="Reply in JSON")

        result = backend.complete(request, _Echo, timeout=4.0, model="qwen3:14b")

        assert result == _Echo(args=literal_args, stdin="Reply in JSON\n\nTotal: 12,50 Kč")

    def test_command_backend_timeout_is_a_timeout_error(self) -> None:
        backend = CommandBackend("slow-cli", _settings(_py(_SLEEP)))
        started = time.monotonic()

        with pytest.raises(BackendError) as exc:
            backend.complete(LLMRequest(prompt="x"), _Tx, timeout=2.0)

        assert time.monotonic() - started < 2.0 + 1.5
        assert exc.value.reason is BackendReason.TIMEOUT
        assert exc.value.backend == "slow-cli"

    def test_command_backend_missing_executable_is_an_exit_error(self) -> None:
        backend = CommandBackend("gone-cli", _settings(["bim-llm-no-such-cli", "-m", "x"]))

        with pytest.raises(BackendError) as exc:
            backend.complete(LLMRequest(prompt="x"), _Tx, timeout=2.0)

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == "gone-cli"
        assert "'bim-llm-no-such-cli' is not on PATH" in exc.value.detail

    def test_command_backend_non_zero_exit_is_an_exit_error(self) -> None:
        script = "import sys; sys.stderr.write('model not found'); sys.exit(4)"
        backend = CommandBackend("broken-cli", _settings(_py(script)))

        with pytest.raises(BackendError) as exc:
            backend.complete(LLMRequest(prompt="x"), _Tx, timeout=2.0)

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == "broken-cli"
        assert "model not found" in exc.value.detail

    @pytest.mark.parametrize(("name", "unattended"), [("shell", True), ("local-llm", False)])
    def test_command_backend_unattended_safe_follows_the_setting(self, name: str, unattended: bool) -> None:
        backend = CommandBackend(name, _settings(["llm"], unattended=unattended))

        assert backend.name == name
        assert backend.unattended_safe is unattended

    @pytest.mark.parametrize("name", ["shell", "my-cli"])
    def test_command_build_backend_builds_a_command_backend(self, name: str) -> None:
        backend = build_backend(name, _settings(["llm"], unattended=True))

        assert isinstance(backend, CommandBackend)
        assert backend.name == name
        assert backend.unattended_safe is True

    def test_command_registry_refuses_an_unattended_command_backend_without_opt_in(self) -> None:
        registry = build_registry({"shell": _settings(["llm"]), "trusted": _settings(["llm"], unattended=True)})

        with pytest.raises(LLMConfigError) as exc:
            registry.get("shell", unattended=True)

        assert str(exc.value) == (
            "backend 'shell' cannot run unattended: a command backend cannot prove its tools are off; "
            "set llm.shell.unattended: true to accept that risk"
        )
        assert isinstance(registry.get("shell"), CommandBackend)
        assert isinstance(registry.get("trusted", unattended=True), CommandBackend)
        assert registry.get("trusted", unattended=True).name == "trusted"
