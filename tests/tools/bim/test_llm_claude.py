from __future__ import annotations

import json
import shutil
from typing import Any

import pytest
from bim.shared.llm import (
    BackendError,
    BackendReason,
    ClaudeBackendSettings,
    JsonObject,
    LLMRequest,
    build_registry,
)
from bim.shared.llm.base import wire_schema
from bim.shared.llm.claude import CLAUDE_TIMEOUT_CUSHION_SECONDS, ClaudeBackend
from bim.shared.llm.registry import build_backend
from pydantic import BaseModel, ConfigDict

_ISOLATION_FLAGS = [
    "--tools",
    "",
    "--strict-mcp-config",
    "--safe-mode",
    "--disable-slash-commands",
    "--no-session-persistence",
]


class _Tx(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: str
    currency: str


class _Other(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issuer: str


_NAMES = ["claude", "claude-x"]


def _expected_argv(schema: type[BaseModel], model: str | None) -> list[str]:
    argv = ["claude", "-p", "--output-format", "json", "--json-schema", json.dumps(wire_schema(schema))]
    argv += _ISOLATION_FLAGS
    if model is not None:
        argv += ["--model", model]
    return argv


class _FakeRunCli:
    """Stands in for the subprocess seam: records each call, then returns stdout or raises."""

    def __init__(self, outcome: str | BackendError) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def __call__(self, argv: list[str], stdin_text: str, *, timeout: float, backend: str) -> str:
        self.calls.append({"argv": list(argv), "stdin": stdin_text, "timeout": timeout, "backend": backend})
        if isinstance(self.outcome, BackendError):
            raise self.outcome
        return self.outcome


@pytest.fixture
def claude_on_path(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    looked_up: list[str] = []

    def fake_which(cmd: str, *args: object, **kwargs: object) -> str | None:
        looked_up.append(cmd)
        return "/opt/bin/claude" if cmd == "claude" else None

    monkeypatch.setattr(shutil, "which", fake_which)
    return looked_up


def _install(monkeypatch: pytest.MonkeyPatch, outcome: str | BackendError) -> _FakeRunCli:
    fake = _FakeRunCli(outcome)
    monkeypatch.setattr("bim.shared.llm.claude.run_cli", fake)
    return fake


def _backend(name: str = "claude", model: str | None = None) -> ClaudeBackend:
    return ClaudeBackend(name, ClaudeBackendSettings(kind="claude", model=model))


def _envelope(**fields: object) -> str:
    return json.dumps({"type": "result", "is_error": False, **fields})


_TX_CZK = {"amount": "12.50", "currency": "CZK"}
_TX_USD = {"amount": "99.00", "currency": "USD"}


class TestClaudeArgv:
    def test_claude_timeout_cushion_is_thirty_seconds(self) -> None:
        assert CLAUDE_TIMEOUT_CUSHION_SECONDS == 30

    def test_claude_backend_is_unattended_safe_and_keeps_its_name(self) -> None:
        first = _backend("claude")
        second = _backend("claude-work", model="opus")

        assert first.unattended_safe is True
        assert second.unattended_safe is True
        assert (first.name, second.name) == ("claude", "claude-work")

    @pytest.mark.parametrize("schema", [_Tx, JsonObject])
    def test_claude_argv_without_model_carries_schema_and_every_isolation_flag(self, schema: type[BaseModel]) -> None:
        argv = _backend().argv(schema, None)

        assert argv == _expected_argv(schema, None)
        assert "--model" not in argv
        assert "--bare" not in argv

    def test_claude_argv_sends_the_schema_it_was_given(self) -> None:
        tx_argv = _backend().argv(_Tx, None)
        obj_argv = _backend().argv(JsonObject, None)

        assert json.loads(tx_argv[5]) == _Tx.model_json_schema()
        assert json.loads(obj_argv[5]) == {"type": "object"}

    @pytest.mark.parametrize("model", ["opus", "sonnet"])
    def test_claude_argv_appends_the_call_model(self, model: str) -> None:
        assert _backend().argv(_Tx, model) == _expected_argv(_Tx, model)

    @pytest.mark.parametrize("model", ["haiku", "claude-sonnet-4-5"])
    def test_claude_argv_falls_back_to_the_settings_model(self, model: str) -> None:
        assert _backend(model=model).argv(_Tx, None) == _expected_argv(_Tx, model)

    def test_claude_argv_call_model_overrides_the_settings_model(self) -> None:
        argv = _backend(model="sonnet").argv(_Tx, "opus")

        assert argv == _expected_argv(_Tx, "opus")
        assert "sonnet" not in argv


class TestClaudeComplete:
    @pytest.mark.parametrize(
        ("request_", "name", "timeout", "model"),
        [
            (LLMRequest(prompt="extract", system="be strict"), "claude", 12.5, None),
            (LLMRequest(prompt="classify this"), "claude-work", 100.0, "opus"),
        ],
    )
    def test_claude_complete_runs_the_cli_with_argv_stdin_and_cushioned_timeout(
        self,
        monkeypatch: pytest.MonkeyPatch,
        claude_on_path: list[str],
        request_: LLMRequest,
        name: str,
        timeout: float,
        model: str | None,
    ) -> None:
        fake = _install(monkeypatch, _envelope(structured_output=_TX_CZK))

        result = _backend(name).complete(request_, _Tx, timeout=timeout, model=model)

        assert result == _Tx(**_TX_CZK)
        assert fake.calls == [
            {
                "argv": _expected_argv(_Tx, model),
                "stdin": request_.as_text(),
                "timeout": timeout + 30,
                "backend": name,
            }
        ]

    def test_claude_complete_uses_the_settings_model_when_the_call_has_none(
        self, monkeypatch: pytest.MonkeyPatch, claude_on_path: list[str]
    ) -> None:
        fake = _install(monkeypatch, _envelope(structured_output=_TX_USD))

        result = _backend(model="haiku").complete(LLMRequest(prompt="x"), _Tx, timeout=5.0)

        assert result == _Tx(**_TX_USD)
        assert fake.calls[0]["argv"] == _expected_argv(_Tx, "haiku")

    @pytest.mark.parametrize("name", _NAMES)
    def test_claude_missing_executable_is_an_exit_error(self, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
        looked_up: list[str] = []

        def fake_which(cmd: str, *args: object, **kwargs: object) -> str | None:
            looked_up.append(cmd)
            return None

        def no_spawn(*args: object, **kwargs: object) -> None:
            raise AssertionError("the claude CLI must not be spawned")

        monkeypatch.setattr(shutil, "which", fake_which)
        monkeypatch.setattr("bim.shared.llm.base.subprocess.Popen", no_spawn)

        with pytest.raises(BackendError) as exc:
            _backend(name).complete(LLMRequest(prompt="x"), _Tx, timeout=5.0)

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == name
        assert "the 'claude' CLI is not on PATH" in exc.value.detail
        assert "claude" in looked_up

    @pytest.mark.parametrize(
        "error",
        [
            BackendError(BackendReason.TIMEOUT, "no reply within 35.0 seconds", backend="claude"),
            BackendError(BackendReason.EXIT, "exited with code 1: auth failed", backend="claude"),
            BackendError(BackendReason.EXIT, "exited with code 2: unknown option", backend="claude"),
        ],
    )
    def test_claude_surfaces_run_cli_failures(
        self, monkeypatch: pytest.MonkeyPatch, claude_on_path: list[str], error: BackendError
    ) -> None:
        fake = _install(monkeypatch, error)

        with pytest.raises(BackendError) as exc:
            _backend().complete(LLMRequest(prompt="x"), _Tx, timeout=5.0)

        assert exc.value.reason is error.reason
        assert error.detail in exc.value.detail
        assert len(fake.calls) == 1


class TestClaudeEnvelope:
    @pytest.mark.parametrize(
        ("stdout", "expected"),
        [
            (_envelope(structured_output=_TX_CZK, result=""), _TX_CZK),
            (_envelope(structured_output=_TX_USD, result=json.dumps(_TX_CZK)), _TX_USD),
            (_envelope(structured_output=json.dumps(_TX_USD)), _TX_USD),
            (_envelope(result=json.dumps(_TX_CZK)), _TX_CZK),
            (_envelope(result=_TX_USD), _TX_USD),
            (json.dumps(_TX_CZK), _TX_CZK),
        ],
        ids=["structured", "structured-wins", "structured-text", "result-text", "result-object", "bare"],
    )
    def test_claude_accepts_structured_output_result_and_bare_payloads(
        self, monkeypatch: pytest.MonkeyPatch, claude_on_path: list[str], stdout: str, expected: dict[str, str]
    ) -> None:
        _install(monkeypatch, stdout)

        result = _backend().complete(LLMRequest(prompt="x"), _Tx, timeout=5.0)

        assert type(result) is _Tx
        assert result == _Tx(**expected)

    @pytest.mark.parametrize(
        ("stdout", "expected"),
        [
            (
                _envelope(structured_output={"issuer_slug": "philips", "pages": [1, 2]}),
                {"issuer_slug": "philips", "pages": [1, 2]},
            ),
            (_envelope(structured_output={}, result=json.dumps({"a": 1})), {}),
        ],
        ids=["structured", "empty-structured-wins"],
    )
    def test_claude_json_object_schema_returns_the_structured_output(
        self, monkeypatch: pytest.MonkeyPatch, claude_on_path: list[str], stdout: str, expected: dict[str, Any]
    ) -> None:
        _install(monkeypatch, stdout)

        result = _backend().complete(LLMRequest(prompt="x"), JsonObject, timeout=5.0)

        assert type(result) is JsonObject
        assert result.root == expected

    @pytest.mark.parametrize("name", _NAMES)
    @pytest.mark.parametrize(
        "stdout",
        [_envelope(structured_output=[1, 2]), _envelope(result="[1]")],
        ids=["structured-list", "result-list-text"],
    )
    def test_claude_json_object_schema_rejects_a_reply_that_is_not_an_object(
        self, monkeypatch: pytest.MonkeyPatch, claude_on_path: list[str], stdout: str, name: str
    ) -> None:
        _install(monkeypatch, stdout)

        with pytest.raises(BackendError) as exc:
            _backend(name).complete(LLMRequest(prompt="x"), JsonObject, timeout=5.0)

        assert exc.value.reason is BackendReason.SCHEMA
        assert exc.value.backend == name

    @pytest.mark.parametrize("name", _NAMES)
    @pytest.mark.parametrize("text", ["Credit balance is too low", "Invalid API key"])
    def test_claude_is_error_envelope_is_an_exit_error_with_its_result(
        self, monkeypatch: pytest.MonkeyPatch, claude_on_path: list[str], text: str, name: str
    ) -> None:
        stdout = json.dumps({"type": "result", "is_error": True, "result": text, "structured_output": _TX_CZK})
        _install(monkeypatch, stdout)

        with pytest.raises(BackendError) as exc:
            _backend(name).complete(LLMRequest(prompt="x"), _Tx, timeout=5.0)

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == name
        assert text in exc.value.detail

    @pytest.mark.parametrize("name", _NAMES)
    @pytest.mark.parametrize(
        "stdout",
        [
            json.dumps({"type": "result", "is_error": True, "structured_output": _TX_CZK}),
            json.dumps({"type": "result", "is_error": True, "result": None, "structured_output": _TX_CZK}),
        ],
        ids=["no-result", "null-result"],
    )
    def test_claude_is_error_envelope_without_result_text_is_still_an_exit_error(
        self, monkeypatch: pytest.MonkeyPatch, claude_on_path: list[str], stdout: str, name: str
    ) -> None:
        _install(monkeypatch, stdout)

        with pytest.raises(BackendError) as exc:
            _backend(name).complete(LLMRequest(prompt="x"), _Tx, timeout=5.0)

        assert exc.value.reason is BackendReason.EXIT
        assert exc.value.backend == name

    @pytest.mark.parametrize("name", _NAMES)
    @pytest.mark.parametrize(
        "stdout",
        [
            "",
            "not json",
            '{"type": "result"',
            _envelope(result="not json"),
            _envelope(result="```json\n{}\n```"),
            _envelope(structured_output="not json"),
        ],
        ids=["empty", "text", "truncated", "result-not-json", "result-fenced", "structured-not-json"],
    )
    def test_claude_invalid_json_is_a_parse_error(
        self, monkeypatch: pytest.MonkeyPatch, claude_on_path: list[str], stdout: str, name: str
    ) -> None:
        _install(monkeypatch, stdout)

        with pytest.raises(BackendError) as exc:
            _backend(name).complete(LLMRequest(prompt="x"), _Tx, timeout=5.0)

        assert exc.value.reason is BackendReason.PARSE
        assert exc.value.backend == name

    @pytest.mark.parametrize("name", _NAMES)
    @pytest.mark.parametrize(
        "stdout",
        [json.dumps([_TX_CZK]), "42", "null", '"text"'],
        ids=["list", "number", "null", "string"],
    )
    def test_claude_valid_json_that_is_not_an_envelope_object_is_a_backend_error(
        self, monkeypatch: pytest.MonkeyPatch, claude_on_path: list[str], stdout: str, name: str
    ) -> None:
        _install(monkeypatch, stdout)

        with pytest.raises(BackendError) as exc:
            _backend(name).complete(LLMRequest(prompt="x"), _Tx, timeout=5.0)

        assert exc.value.reason in {BackendReason.PARSE, BackendReason.SCHEMA}
        assert exc.value.backend == name

    @pytest.mark.parametrize("name", _NAMES)
    @pytest.mark.parametrize(
        ("schema", "stdout"),
        [
            (_Tx, _envelope(structured_output={"amount": "1.00"})),
            (_Tx, _envelope(result=json.dumps({**_TX_CZK, "note": "surprise"}))),
            (_Tx, _envelope(result=[_TX_CZK])),
            (_Tx, json.dumps({**_TX_USD, "note": "surprise"})),
            (_Other, _envelope(structured_output=_TX_CZK)),
            (_Other, _envelope(result=json.dumps({"issuer": "philips", "note": "surprise"}))),
        ],
        ids=["missing-field", "extra-key", "list", "bare-extra-key", "other-wrong-fields", "other-extra-key"],
    )
    def test_claude_reply_that_does_not_match_the_schema_is_a_schema_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        claude_on_path: list[str],
        schema: type[BaseModel],
        stdout: str,
        name: str,
    ) -> None:
        _install(monkeypatch, stdout)

        with pytest.raises(BackendError) as exc:
            _backend(name).complete(LLMRequest(prompt="x"), schema, timeout=5.0)

        assert exc.value.reason is BackendReason.SCHEMA
        assert exc.value.backend == name
        assert exc.value.detail.startswith(f"reply does not match {schema.__name__}: ")


class TestClaudeRegistry:
    @pytest.mark.parametrize(("name", "model"), [("claude", "sonnet"), ("claude-work", None)])
    def test_build_backend_builds_a_claude_backend_for_kind_claude(self, name: str, model: str | None) -> None:
        backend = build_backend(name, ClaudeBackendSettings(kind="claude", model=model))

        assert isinstance(backend, ClaudeBackend)
        assert backend.name == name
        assert backend.argv(_Tx, None) == _expected_argv(_Tx, model)

    def test_claude_backend_from_build_registry_is_allowed_unattended(self) -> None:
        registry = build_registry({"claude-main": ClaudeBackendSettings(kind="claude", model="opus")})

        backend = registry.get("claude-main", unattended=True)

        assert isinstance(backend, ClaudeBackend)
        assert backend.name == "claude-main"
        assert backend.unattended_safe is True
