from __future__ import annotations

import json
import sys
import threading
import time
import types
from typing import TYPE_CHECKING, Any, Literal

import pytest
from bim.shared.llm import (
    BackendError,
    BackendReason,
    HttpBackendSettings,
    JsonObject,
    LLMConfigError,
    LLMRequest,
    build_registry,
)
from bim.shared.llm.base import MAX_REPLY_BYTES
from bim.shared.llm.http import HttpBackend, build_chat_request, read_chat_content
from bim.shared.llm.registry import build_backend
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from pathlib import Path

Kind = Literal["ollama", "llamacpp", "openai"]
CHUNK = 8192


class _RequestException(OSError):
    pass


class _ConnectionError(_RequestException):
    pass


class _HTTPError(_RequestException):
    pass


class _Timeout(_RequestException):
    pass


class _FakeExceptions(types.ModuleType):
    Timeout = _Timeout
    ConnectionError = _ConnectionError
    HTTPError = _HTTPError
    RequestException = _RequestException


class _FakeRequests(types.ModuleType):
    def __init__(self, post: Callable[..., Any], exceptions: _FakeExceptions) -> None:
        super().__init__("requests")
        self.post = post
        self.exceptions = exceptions


class _Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    score: int


class _FakeResponse:
    def __init__(self, status_code: int = 200, chunks: Iterable[bytes] = ()) -> None:
        self.status_code = status_code
        self._chunks = chunks
        self.body_read = False
        self.chunk_sizes: list[int] = []
        self.closed = threading.Event()

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise _HTTPError(f"{self.status_code} Server Error: boom")

    def iter_content(self, chunk_size: int = 1) -> Iterator[bytes]:
        self.body_read = True
        self.chunk_sizes.append(chunk_size)
        return iter(self._chunks)

    def close(self) -> None:
        self.closed.set()


def _install_requests(monkeypatch: pytest.MonkeyPatch, outcome: Any) -> list[tuple[str, dict[str, Any]]]:
    """Put a fake ``requests`` in sys.modules; return the recorded ``post`` calls.

    ``outcome`` is a response to return, an exception to raise, or a callable that builds the response.
    """
    calls: list[tuple[str, dict[str, Any]]] = []

    def post(*args: Any, **kwargs: Any) -> _FakeResponse:
        url = args[0] if args else kwargs.pop("url")
        calls.append((url, kwargs))
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, _FakeResponse):
            return outcome
        return outcome()

    exceptions = _FakeExceptions("requests.exceptions")
    monkeypatch.setitem(sys.modules, "requests", _FakeRequests(post, exceptions))
    monkeypatch.setitem(sys.modules, "requests.exceptions", exceptions)
    return calls


def _envelope(kind: Kind, content: object) -> bytes:
    message = {"role": "assistant", "content": content}
    if kind == "ollama":
        return json.dumps({"model": "m", "message": message, "done": True}).encode()
    return json.dumps({"choices": [{"index": 0, "message": message}]}).encode()


def _split(data: bytes) -> list[bytes]:
    """Split a body into two chunks so the reader must join them."""
    middle = len(data) // 2
    return [data[:middle], data[middle:]]


def _ok(kind: Kind, content: object) -> _FakeResponse:
    return _FakeResponse(200, _split(_envelope(kind, content)))


def _backend(
    kind: Kind, endpoint: str = "http://llm.test:8080", model: str | None = "m", name: str = "box"
) -> HttpBackend:
    return HttpBackend(name, HttpBackendSettings(kind=kind, endpoint=endpoint, model=model))


def _url(kind: Kind, endpoint: str = "http://llm.test:8080") -> str:
    return f"{endpoint}/api/chat" if kind == "ollama" else f"{endpoint}/v1/chat/completions"


def _fail(backend: HttpBackend, schema: type[BaseModel] = _Verdict, timeout: float = 5.0) -> BackendError:
    with pytest.raises(BackendError) as info:
        backend.complete(LLMRequest(prompt="p"), schema, timeout=timeout)
    assert info.value.backend == backend.name
    return info.value


MESSAGES = [{"role": "system", "content": "be terse"}, {"role": "user", "content": "classify this"}]


class TestHttpBuildChatRequest:
    @pytest.mark.parametrize(
        ("endpoint", "model"), [("http://localhost:11434", "qwen3:8b"), ("http://gpu.lan:9000", "llama3.1")]
    )
    def test_http_ollama_request_posts_json_format_to_api_chat(self, endpoint: str, model: str) -> None:
        url, body = build_chat_request("ollama", endpoint, model, MESSAGES, {"type": "object"})

        assert url == f"{endpoint}/api/chat"
        assert body == {"model": model, "messages": MESSAGES, "format": "json", "stream": False}

    @pytest.mark.parametrize(
        ("endpoint", "model"), [("http://localhost:8080", "gemma-3"), ("http://gpu.lan:9001", "qwen3-30b")]
    )
    def test_http_llamacpp_request_sends_json_schema_and_disables_thinking(self, endpoint: str, model: str) -> None:
        schema = _Verdict.model_json_schema()

        url, body = build_chat_request("llamacpp", endpoint, model, MESSAGES, schema)

        assert url == f"{endpoint}/v1/chat/completions"
        assert body == {
            "model": model,
            "messages": MESSAGES,
            "response_format": {"type": "json_schema", "json_schema": {"name": "reply", "schema": schema}},
            "chat_template_kwargs": {"enable_thinking": False},
            "stream": False,
        }

    def test_http_llamacpp_request_without_model_omits_model_key(self) -> None:
        url, body = build_chat_request("llamacpp", "http://localhost:8080", None, MESSAGES, {"type": "object"})

        assert url == "http://localhost:8080/v1/chat/completions"
        assert "model" not in body
        assert body["messages"] == MESSAGES

    @pytest.mark.parametrize(
        ("endpoint", "model"), [("https://api.example.com", "gpt-x"), ("http://vllm.lan", "mixtral")]
    )
    def test_http_openai_request_matches_llamacpp_without_chat_template_kwargs(self, endpoint: str, model: str) -> None:
        schema = {"type": "object"}

        url, body = build_chat_request("openai", endpoint, model, MESSAGES, schema)

        assert url == f"{endpoint}/v1/chat/completions"
        assert body == {
            "model": model,
            "messages": MESSAGES,
            "response_format": {"type": "json_schema", "json_schema": {"name": "reply", "schema": schema}},
            "stream": False,
        }


class TestHttpReadChatContent:
    @pytest.mark.parametrize("text", ['{"a": 1}', "plain words"])
    def test_http_ollama_content_comes_from_message(self, text: str) -> None:
        assert read_chat_content("ollama", {"message": {"role": "assistant", "content": text}}) == text

    @pytest.mark.parametrize("kind", ["llamacpp", "openai"])
    def test_http_chat_completions_content_comes_from_first_choice(self, kind: Kind) -> None:
        payload = {"choices": [{"message": {"content": "first"}}, {"message": {"content": "second"}}]}

        assert read_chat_content(kind, payload) == "first"

    @pytest.mark.parametrize("kind", ["llamacpp", "openai"])
    def test_http_empty_choices_raises_key_error_choices(self, kind: Kind) -> None:
        with pytest.raises(KeyError) as info:
            read_chat_content(kind, {"choices": []})
        assert info.value.args == ("choices",)

    @pytest.mark.parametrize(
        ("kind", "payload"),
        [("llamacpp", {"message": {"content": "x"}}), ("ollama", {"choices": [{"message": {"content": "x"}}]})],
    )
    def test_http_envelope_of_the_other_kind_raises_key_error(self, kind: Kind, payload: dict[str, Any]) -> None:
        with pytest.raises(KeyError):
            read_chat_content(kind, payload)

    @pytest.mark.parametrize(
        ("kind", "payload"),
        [
            ("openai", {"choices": [{"message": {"content": None}}]}),
            ("ollama", {"message": {"content": {"label": "x"}}}),
            ("openai", {"choices": [{"message": {"content": [1]}}]}),
            ("llamacpp", {"choices": [{"message": {"content": 3}}]}),
            ("ollama", {"message": {"content": True}}),
            ("ollama", {"message": {"content": [1]}}),
        ],
    )
    def test_http_non_text_content_raises_type_error(self, kind: Kind, payload: dict[str, Any]) -> None:
        with pytest.raises(TypeError):
            read_chat_content(kind, payload)


class TestHttpBackendRequest:
    def test_http_backend_is_named_and_unattended_safe(self) -> None:
        backend = _backend("ollama", name="local-gpu")

        assert backend.name == "local-gpu"
        assert backend.unattended_safe is True

    @pytest.mark.parametrize(("kind", "timeout"), [("ollama", 0.75), ("llamacpp", 42.0), ("openai", 12.5)])
    def test_http_backend_posts_streamed_without_redirects_and_passes_timeout(
        self, monkeypatch: pytest.MonkeyPatch, kind: Kind, timeout: float
    ) -> None:
        response = _ok(kind, '{"label": "a", "score": 1}')
        calls = _install_requests(monkeypatch, response)

        _backend(kind).complete(LLMRequest(prompt="p"), _Verdict, timeout=timeout)

        assert len(calls) == 1
        url, kwargs = calls[0]
        assert url == _url(kind)
        assert set(kwargs) == {"json", "timeout", "stream", "allow_redirects"}
        assert kwargs["timeout"] == timeout
        assert kwargs["stream"] is True
        assert kwargs["allow_redirects"] is False
        assert response.chunk_sizes == [CHUNK]
        assert response.closed.wait(1)

    def test_http_backend_llamacpp_body_carries_caller_schema_and_messages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _install_requests(monkeypatch, _ok("llamacpp", '{"label": "a", "score": 1}'))

        _backend("llamacpp", model="gemma").complete(
            LLMRequest(prompt="classify this", system="be terse"), _Verdict, timeout=5.0
        )

        assert calls[0][1]["json"] == {
            "model": "gemma",
            "messages": MESSAGES,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "reply", "schema": _Verdict.model_json_schema()},
            },
            "chat_template_kwargs": {"enable_thinking": False},
            "stream": False,
        }

    @pytest.mark.parametrize("kind", ["llamacpp", "openai"])
    def test_http_backend_json_object_caller_sends_plain_object_schema(
        self, monkeypatch: pytest.MonkeyPatch, kind: Kind
    ) -> None:
        calls = _install_requests(monkeypatch, _ok(kind, '{"anything": [1, 2]}'))

        _backend(kind).complete(LLMRequest(prompt="p"), JsonObject, timeout=5.0)

        assert calls[0][1]["json"]["response_format"]["json_schema"]["schema"] == {"type": "object"}

    def test_http_backend_without_system_sends_only_the_user_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _install_requests(monkeypatch, _ok("ollama", '{"label": "a", "score": 1}'))

        _backend("ollama").complete(LLMRequest(prompt="just the prompt"), _Verdict, timeout=5.0)

        assert calls[0][1]["json"]["messages"] == [{"role": "user", "content": "just the prompt"}]

    @pytest.mark.parametrize(("call_model", "expected"), [("call-model", "call-model"), (None, "settings-model")])
    def test_http_backend_call_model_overrides_settings_model(
        self, monkeypatch: pytest.MonkeyPatch, call_model: str | None, expected: str
    ) -> None:
        calls = _install_requests(monkeypatch, _ok("ollama", '{"label": "a", "score": 1}'))

        _backend("ollama", model="settings-model").complete(
            LLMRequest(prompt="p"), _Verdict, timeout=5.0, model=call_model
        )

        assert calls[0][1]["json"]["model"] == expected

    @pytest.mark.parametrize("kind", ["ollama", "llamacpp", "openai"])
    @pytest.mark.parametrize("call_model", ["x", "qwen3:8b"])
    def test_http_backend_call_model_is_used_when_settings_have_no_model(
        self, monkeypatch: pytest.MonkeyPatch, kind: Kind, call_model: str
    ) -> None:
        calls = _install_requests(monkeypatch, _ok(kind, '{"label": "a", "score": 1}'))

        result = _backend(kind, model=None).complete(LLMRequest(prompt="p"), _Verdict, timeout=5.0, model=call_model)

        assert result == _Verdict(label="a", score=1)
        assert calls[0][1]["json"]["model"] == call_model

    @pytest.mark.parametrize(("kind", "name"), [("ollama", "local"), ("openai", "cloud-box")])
    def test_http_backend_without_any_model_raises_config_error_before_posting(
        self, monkeypatch: pytest.MonkeyPatch, kind: Kind, name: str
    ) -> None:
        calls = _install_requests(monkeypatch, _ok(kind, '{"label": "a", "score": 1}'))

        with pytest.raises(LLMConfigError) as info:
            _backend(kind, model=None, name=name).complete(LLMRequest(prompt="p"), _Verdict, timeout=5.0)

        assert str(info.value) == f"backend {name!r} has no model; set llm.{name}.model"
        assert calls == []

    def test_http_backend_llamacpp_runs_without_model_and_omits_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _install_requests(monkeypatch, _ok("llamacpp", '{"label": "a", "score": 1}'))

        result = _backend("llamacpp", model=None).complete(LLMRequest(prompt="p"), _Verdict, timeout=5.0)

        assert result == _Verdict(label="a", score=1)
        assert "model" not in calls[0][1]["json"]

    @pytest.mark.parametrize("kind", ["ollama", "llamacpp", "openai"])
    def test_http_backend_strips_trailing_slash_from_endpoint(
        self, monkeypatch: pytest.MonkeyPatch, kind: Kind
    ) -> None:
        calls = _install_requests(monkeypatch, _ok(kind, '{"label": "a", "score": 1}'))

        _backend(kind, endpoint="http://slash.test:1234/").complete(LLMRequest(prompt="p"), _Verdict, timeout=5.0)

        assert calls[0][0] == _url(kind, "http://slash.test:1234")

    def test_http_backend_payload_never_carries_the_vault_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        vault = tmp_path / "scratch-vault"
        vault.mkdir()
        (vault / "note.md").write_text("---\nid: 1\n---\n", encoding="utf-8")
        monkeypatch.chdir(vault)
        calls = _install_requests(monkeypatch, _ok("llamacpp", '{"label": "a", "score": 1}'))

        _backend("llamacpp").complete(LLMRequest(prompt="classify this", system="be terse"), _Verdict, timeout=5.0)

        url, kwargs = calls[0]
        assert str(vault) not in url
        assert str(vault) not in json.dumps(kwargs["json"])
        assert "scratch-vault" not in json.dumps(kwargs["json"])


class TestHttpBackendReply:
    @pytest.mark.parametrize("kind", ["ollama", "llamacpp", "openai"])
    @pytest.mark.parametrize(("label", "score"), [("invoice", 3), ("receipt", 97)])
    def test_http_backend_returns_reply_validated_against_strict_schema(
        self, monkeypatch: pytest.MonkeyPatch, kind: Kind, label: str, score: int
    ) -> None:
        _install_requests(monkeypatch, _ok(kind, json.dumps({"label": label, "score": score})))

        result = _backend(kind).complete(LLMRequest(prompt="p"), _Verdict, timeout=5.0)

        assert result == _Verdict(label=label, score=score)

    @pytest.mark.parametrize("kind", ["ollama", "openai"])
    def test_http_backend_returns_reply_as_json_object(self, monkeypatch: pytest.MonkeyPatch, kind: Kind) -> None:
        reply = {"issuer_slug": "cez", "extra": {"nested": [1, 2]}}
        _install_requests(monkeypatch, _ok(kind, json.dumps(reply)))

        result = _backend(kind).complete(LLMRequest(prompt="p"), JsonObject, timeout=5.0)

        assert result.root == reply

    def test_http_backend_extra_key_passes_json_object(self, monkeypatch: pytest.MonkeyPatch) -> None:
        reply = {"label": "a", "score": 1, "surprise": True}
        _install_requests(monkeypatch, _ok("openai", json.dumps(reply)))

        result = _backend("openai").complete(LLMRequest(prompt="p"), JsonObject, timeout=5.0)

        assert result.root == reply

    @pytest.mark.parametrize(
        "reply", [{"label": "a", "score": 1, "surprise": True}, {"label": "a"}, {"label": "a", "score": "many"}]
    )
    def test_http_backend_reply_not_matching_strict_schema_is_schema_error(
        self, monkeypatch: pytest.MonkeyPatch, reply: dict[str, Any]
    ) -> None:
        response = _ok("openai", json.dumps(reply))
        _install_requests(monkeypatch, response)

        error = _fail(_backend("openai"))

        assert error.reason is BackendReason.SCHEMA
        assert error.detail.startswith("reply does not match")
        assert response.closed.wait(1)

    @pytest.mark.parametrize("content", ["sorry, no JSON", '{"label": "a", "score": '])
    def test_http_backend_non_json_reply_text_is_parse_error(
        self, monkeypatch: pytest.MonkeyPatch, content: str
    ) -> None:
        response = _ok("llamacpp", content)
        _install_requests(monkeypatch, response)

        error = _fail(_backend("llamacpp"))

        assert error.reason is BackendReason.PARSE
        assert error.detail.startswith("reply is not valid JSON")
        assert response.closed.wait(1)

    @pytest.mark.parametrize(
        ("kind", "envelope"),
        [
            ("llamacpp", {"id": "x", "object": "chat.completion"}),
            ("llamacpp", {"choices": []}),
            ("openai", {"choices": []}),
            ("openai", {"choices": [{"message": {"role": "assistant", "content": None}}]}),
            ("ollama", {"message": {"role": "assistant", "content": {"label": "a", "score": 1}}}),
            ("ollama", {"done": True}),
        ],
    )
    def test_http_backend_malformed_envelope_is_parse_error(
        self, monkeypatch: pytest.MonkeyPatch, kind: Kind, envelope: dict[str, Any]
    ) -> None:
        response = _FakeResponse(200, [json.dumps(envelope).encode()])
        _install_requests(monkeypatch, response)

        error = _fail(_backend(kind))

        assert error.reason is BackendReason.PARSE
        assert error.detail.startswith("malformed reply envelope: ")
        assert response.closed.wait(1)


class TestHttpBackendTransportErrors:
    def test_http_backend_without_requests_package_is_exit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "requests", None)

        error = _fail(_backend("ollama"))

        assert error.reason is BackendReason.EXIT
        assert error.detail.startswith("the 'requests' package is not installed")

    @pytest.mark.parametrize(("kind", "timeout"), [("ollama", 5.0), ("openai", 0.5)])
    def test_http_backend_post_timeout_is_timeout(
        self, monkeypatch: pytest.MonkeyPatch, kind: Kind, timeout: float
    ) -> None:
        _install_requests(monkeypatch, _Timeout("read timed out"))

        error = _fail(_backend(kind), timeout=timeout)

        assert error.reason is BackendReason.TIMEOUT
        assert error.detail.startswith(f"no reply from {_url(kind)} within {timeout}s")

    def test_http_backend_connection_error_is_exit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_requests(monkeypatch, _ConnectionError("connection refused"))

        error = _fail(_backend("llamacpp"))

        assert error.reason is BackendReason.EXIT
        assert error.detail.startswith(f"HTTP error calling {_url('llamacpp')}: ")
        assert "connection refused" in error.detail

    @pytest.mark.parametrize("status", [400, 500, 503])
    def test_http_backend_error_status_is_exit(self, monkeypatch: pytest.MonkeyPatch, status: int) -> None:
        response = _FakeResponse(status, [_envelope("ollama", "{}")])
        _install_requests(monkeypatch, response)

        error = _fail(_backend("ollama"))

        assert error.reason is BackendReason.EXIT
        assert error.detail.startswith(f"HTTP error calling {_url('ollama')}: ")
        assert str(status) in error.detail
        assert response.closed.wait(1)

    def test_http_backend_bare_request_exception_from_post_is_exit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_requests(monkeypatch, _RequestException("invalid header value"))

        error = _fail(_backend("openai"))

        assert error.reason is BackendReason.EXIT
        assert error.detail.startswith(f"HTTP error calling {_url('openai')}: ")
        assert "invalid header value" in error.detail

    def test_http_backend_connection_error_while_reading_body_is_exit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def broken_body() -> Iterator[bytes]:
            yield b'{"message": '
            raise _ConnectionError("connection reset mid-body")

        response = _FakeResponse(200, broken_body())
        _install_requests(monkeypatch, response)

        error = _fail(_backend("ollama"))

        assert error.reason is BackendReason.EXIT
        assert error.detail.startswith(f"HTTP error calling {_url('ollama')}: ")
        assert "connection reset mid-body" in error.detail
        assert response.closed.wait(1)

    @pytest.mark.parametrize("status", [300, 302, 399])
    def test_http_backend_redirect_is_exit_without_reading_body(
        self, monkeypatch: pytest.MonkeyPatch, status: int
    ) -> None:
        response = _FakeResponse(status, [_envelope("ollama", '{"label": "a", "score": 1}')])
        calls = _install_requests(monkeypatch, response)

        error = _fail(_backend("ollama"))

        assert error.reason is BackendReason.EXIT
        assert error.detail.startswith("redirect not followed")
        assert calls[0][1]["allow_redirects"] is False
        assert response.body_read is False
        assert response.closed.wait(1)

    @pytest.mark.parametrize("body", [b"<html>bad gateway</html>", b'{"message": {"content": "\xff"}}'])
    def test_http_backend_undecodable_envelope_is_exit(self, monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
        response = _FakeResponse(200, [body])
        _install_requests(monkeypatch, response)

        error = _fail(_backend("ollama"))

        assert error.reason is BackendReason.EXIT
        assert error.detail.startswith(f"HTTP error calling {_url('ollama')}: ")
        assert response.closed.wait(1)

    def test_http_backend_reply_of_exactly_max_bytes_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        envelope = _envelope("ollama", '{"label": "big", "score": 2}')
        data = envelope + b" " * (MAX_REPLY_BYTES - len(envelope))
        _install_requests(monkeypatch, _FakeResponse(200, [data[i : i + CHUNK] for i in range(0, len(data), CHUNK)]))

        result = _backend("ollama").complete(LLMRequest(prompt="p"), _Verdict, timeout=5.0)

        assert result == _Verdict(label="big", score=2)

    def test_http_backend_reply_one_byte_over_max_is_exit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        envelope = _envelope("ollama", '{"label": "big", "score": 2}')
        data = envelope + b" " * (MAX_REPLY_BYTES - len(envelope) + 1)
        response = _FakeResponse(200, [data[i : i + CHUNK] for i in range(0, len(data), CHUNK)])
        _install_requests(monkeypatch, response)

        error = _fail(_backend("ollama"))

        assert error.reason is BackendReason.EXIT
        assert error.detail.startswith(f"reply larger than {MAX_REPLY_BYTES} bytes")
        assert response.closed.wait(1)

    def test_http_backend_stops_reading_an_oversized_body_early(self, monkeypatch: pytest.MonkeyPatch) -> None:
        consumed: list[int] = []

        def oversized_body() -> Iterator[bytes]:
            for _ in range(3 * MAX_REPLY_BYTES // CHUNK):
                consumed.append(CHUNK)
                yield b" " * CHUNK

        _install_requests(monkeypatch, _FakeResponse(200, oversized_body()))

        error = _fail(_backend("ollama"))

        assert error.reason is BackendReason.EXIT
        assert sum(consumed) <= MAX_REPLY_BYTES + CHUNK


class TestHttpBackendDeadline:
    def test_http_deadline_releases_caller_while_post_blocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        release = threading.Event()
        yielded: list[int] = []

        def late_body() -> Iterator[bytes]:
            for _ in range(50):
                yielded.append(1)
                yield b" "

        late = _FakeResponse(200, late_body())

        def blocked_post() -> _FakeResponse:
            release.wait(5)
            return late

        _install_requests(monkeypatch, blocked_post)
        backend = _backend("ollama", endpoint="http://slow.test:11434")
        started = time.monotonic()
        try:
            with pytest.raises(BackendError) as info:
                backend.complete(LLMRequest(prompt="p"), _Verdict, timeout=0.1)
            elapsed = time.monotonic() - started
        finally:
            release.set()

        assert elapsed < 0.1 + 0.3
        assert info.value.reason is BackendReason.TIMEOUT
        assert info.value.detail.startswith("no complete reply from http://slow.test:11434/api/chat within 0.1s")
        assert late.closed.wait(2)
        assert len(yielded) <= 1

    def test_http_deadline_waits_for_a_slow_reply_within_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        release = threading.Event()

        def slow_post() -> _FakeResponse:
            release.wait(0.3)
            return _ok("openai", '{"label": "slow", "score": 4}')

        _install_requests(monkeypatch, slow_post)
        try:
            result = _backend("openai").complete(LLMRequest(prompt="p"), _Verdict, timeout=2.0)
        finally:
            release.set()

        assert result == _Verdict(label="slow", score=4)

    def test_http_deadline_releases_caller_on_trickling_body_and_worker_stops(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        release = threading.Event()
        yielded: list[int] = []

        def trickle() -> Iterator[bytes]:
            yielded.append(1)
            yield b'{"choices": '
            release.wait(5)
            for _ in range(50):
                yielded.append(1)
                yield b" "

        response = _FakeResponse(200, trickle())
        _install_requests(monkeypatch, response)
        started = time.monotonic()
        try:
            error = _fail(_backend("llamacpp"), timeout=0.15)
            elapsed = time.monotonic() - started
        finally:
            release.set()

        assert elapsed < 0.15 + 0.3
        assert error.reason is BackendReason.TIMEOUT
        assert error.detail.startswith(f"no complete reply from {_url('llamacpp')} within 0.15s")
        assert response.closed.wait(2)
        assert len(yielded) <= 3


class TestHttpBackendRegistry:
    @pytest.mark.parametrize("kind", ["ollama", "llamacpp", "openai"])
    def test_http_build_backend_and_registry_create_http_backend(self, kind: Kind) -> None:
        settings = HttpBackendSettings(kind=kind, endpoint="http://llm.test:8080", model="m")

        built = build_backend(f"{kind}-one", settings)
        registered = build_registry({f"{kind}-two": settings}).get(f"{kind}-two", unattended=True)

        assert isinstance(built, HttpBackend)
        assert built.name == f"{kind}-one"
        assert isinstance(registered, HttpBackend)
        assert registered.name == f"{kind}-two"

    def test_http_registry_backend_posts_to_its_configured_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _install_requests(monkeypatch, _ok("openai", '{"label": "a", "score": 1}'))
        settings = HttpBackendSettings(kind="openai", endpoint="http://registry.test:7000", model="gpt-x")
        registry = build_registry({"remote": settings})

        result = registry.invoke("remote", LLMRequest(prompt="p"), _Verdict, timeout=3.0)

        assert result == _Verdict(label="a", score=1)
        assert calls[0][0] == "http://registry.test:7000/v1/chat/completions"
        assert calls[0][1]["json"]["model"] == "gpt-x"
        assert calls[0][1]["timeout"] == 3.0
