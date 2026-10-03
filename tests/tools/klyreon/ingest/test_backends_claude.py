"""Phase 1: the claude adapter, subprocess MOCKED only (never a real binary)."""

from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest
from klyreon.backends.base import BackendError, BackendReason, IngestPayload
from klyreon.backends.claude import ClaudeBackend

pytestmark = pytest.mark.klyreon

_GOOD_PAYLOAD = {"zettels": [], "conflicts": [], "corroborations": []}


def _fake_run(stdout: str = "", returncode: int = 0, *, timeout: bool = False):
    def run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if timeout:
            raise subprocess.TimeoutExpired(cmd=args[0] if args else kwargs.get("args"), timeout=1)
        return subprocess.CompletedProcess(
            args=args[0] if args else [], returncode=returncode, stdout=stdout, stderr="err"
        )

    return run


@pytest.fixture
def present_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("klyreon.backends.claude.shutil.which", lambda _name: "/usr/bin/claude")


class TestArgv:
    def test_argv_carries_json_schema_and_empty_tools(
        self, present_binary: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: dict[str, Any] = {}

        def capture(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            seen["argv"] = args
            seen["input"] = kwargs.get("input")
            seen["cwd"] = kwargs.get("cwd")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps(_GOOD_PAYLOAD), stderr="")

        monkeypatch.setattr(subprocess, "run", capture)
        ClaudeBackend().run("the prompt", timeout=10)
        argv = seen["argv"]
        assert "--json-schema" in argv
        # --tools "" : the flag is present and its value is the empty string.
        assert "--tools" in argv
        assert argv[argv.index("--tools") + 1] == ""
        assert seen["input"] == "the prompt"  # prompt on stdin
        assert seen["cwd"] is not None  # a temp cwd

    def test_model_flag_only_when_set(self, present_binary: None, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, Any] = {}

        def capture(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            seen["argv"] = args
            return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps(_GOOD_PAYLOAD), stderr="")

        monkeypatch.setattr(subprocess, "run", capture)
        ClaudeBackend(model="sonnet").run("p", timeout=10)
        assert "--model" in seen["argv"]
        assert seen["argv"][seen["argv"].index("--model") + 1] == "sonnet"


class TestOutcomes:
    def test_success_returns_payload(self, present_binary: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout=json.dumps(_GOOD_PAYLOAD)))
        payload = ClaudeBackend().run("p", timeout=10)
        assert isinstance(payload, IngestPayload)

    def test_success_envelope_result_field(self, present_binary: None, monkeypatch: pytest.MonkeyPatch) -> None:
        envelope = {"result": _GOOD_PAYLOAD, "type": "result"}
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout=json.dumps(envelope)))
        assert isinstance(ClaudeBackend().run("p", timeout=10), IngestPayload)

    def test_nonzero_exit_is_exit_reason(self, present_binary: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_run(returncode=2))
        with pytest.raises(BackendError) as exc:
            ClaudeBackend().run("p", timeout=10)
        assert exc.value.reason is BackendReason.EXIT

    def test_timeout_is_timeout_reason(self, present_binary: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_run(timeout=True))
        with pytest.raises(BackendError) as exc:
            ClaudeBackend().run("p", timeout=10)
        assert exc.value.reason is BackendReason.TIMEOUT

    def test_unparseable_stdout_is_parse_reason(self, present_binary: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout="not json at all"))
        with pytest.raises(BackendError) as exc:
            ClaudeBackend().run("p", timeout=10)
        assert exc.value.reason is BackendReason.PARSE

    def test_schema_mismatch_is_schema_reason(self, present_binary: None, monkeypatch: pytest.MonkeyPatch) -> None:
        bad = {"zettels": [{"title": "x", "type": "not-a-type"}]}
        monkeypatch.setattr(subprocess, "run", _fake_run(stdout=json.dumps(bad)))
        with pytest.raises(BackendError) as exc:
            ClaudeBackend().run("p", timeout=10)
        assert exc.value.reason is BackendReason.SCHEMA

    def test_absent_binary_is_exit_reason_naming_tool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("klyreon.backends.claude.shutil.which", lambda _name: None)
        with pytest.raises(BackendError) as exc:
            ClaudeBackend().run("p", timeout=10)
        assert exc.value.reason is BackendReason.EXIT
        assert "claude" in exc.value.detail
