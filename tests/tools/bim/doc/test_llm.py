from __future__ import annotations

import json

import pytest
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.llm import (
    DOC_REQUEST_TIMEOUT_SECONDS,
    LEGACY_DOC_BACKENDS,
    DocLLMTarget,
    chat_content,
    chat_request,
    resolve_doc_route,
)
from bim.commands.doc.shared.naming import DOC_TYPES
from bim.commands.doc.shared.rules.models import SourceMetadata
from bim.commands.doc.shared.settings_models import ClassifierSettings
from bim.shared.llm import (
    ClaudeBackendSettings,
    CommandBackendSettings,
    HttpBackendSettings,
    LLMConfigError,
)
from pytest_mock import MockerFixture

_MESSAGES = [{"role": "user", "content": "hi"}]
_LLAMACPP = ClassifierSettings(backend="llamacpp", endpoint="http://localhost:8002/")


class _MockResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.status_code = 200

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        return None


def _openai_reply(content: dict[str, object]) -> _MockResponse:
    return _MockResponse({"choices": [{"message": {"role": "assistant", "content": json.dumps(content)}}]})


def _fake_requests(mocker: MockerFixture, response: _MockResponse) -> object:
    fake = mocker.MagicMock()
    fake.exceptions.Timeout = type("Timeout", (Exception,), {})
    fake.post.return_value = response
    mocker.patch.dict("sys.modules", {"requests": fake}, clear=False)
    return fake


class TestChatRequest:
    def test_ollama_default_keeps_native_api_chat_shape(self) -> None:
        url, body = chat_request(ClassifierSettings(), "qwen3:14b", _MESSAGES)

        assert url == "http://localhost:11434/api/chat"
        assert body == {"model": "qwen3:14b", "messages": _MESSAGES, "format": "json", "stream": False}

    def test_llamacpp_enforces_json_with_a_schema_grammar(self) -> None:
        # llama-server ignores {"type": "json_object"} (live: the model wrapped
        # its reply in a ```json fence); only a json_schema compiles a grammar.
        url, body = chat_request(_LLAMACPP, "any", _MESSAGES)

        assert url == "http://localhost:8002/v1/chat/completions"
        assert body["response_format"] == {
            "type": "json_schema",
            "json_schema": {"name": "reply", "schema": {"type": "object"}},
        }
        assert body["stream"] is False
        assert "format" not in body

    def test_llamacpp_disables_thinking(self) -> None:
        _, body = chat_request(_LLAMACPP, "any", _MESSAGES)

        assert body["chat_template_kwargs"] == {"enable_thinking": False}


class TestChatContent:
    def test_ollama_reads_message_content(self) -> None:
        assert chat_content(ClassifierSettings(), {"message": {"content": "{}"}}) == "{}"

    def test_llamacpp_reads_first_choice(self) -> None:
        assert chat_content(_LLAMACPP, {"choices": [{"message": {"content": "{}"}}]}) == "{}"

    def test_llamacpp_empty_choices_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            chat_content(_LLAMACPP, {"choices": []})

    def test_llamacpp_rejects_ollama_shaped_reply(self) -> None:
        with pytest.raises(KeyError):
            chat_content(_LLAMACPP, {"message": {"content": "{}"}})


_FAST = HttpBackendSettings(kind="ollama", endpoint="http://gpu-box:11434", model="qwen3:8b")
_SMART = ClaudeBackendSettings(kind="claude", model="opus")
_CLI = CommandBackendSettings(kind="command", argv=["codex", "exec"])
_NAMED = {"fast": _FAST, "smart": _SMART, "cli": _CLI}


class TestDocRouteConstants:
    def test_legacy_backends_are_ollama_and_llamacpp(self) -> None:
        assert LEGACY_DOC_BACKENDS == frozenset({"ollama", "llamacpp"})

    def test_request_timeout_is_sixty_seconds(self) -> None:
        assert DOC_REQUEST_TIMEOUT_SECONDS == 60


class TestResolveDocRouteLegacy:
    def test_defaults_keep_the_original_ollama_endpoint_and_models(self) -> None:
        route = resolve_doc_route(ClassifierSettings(), {})

        assert route.legacy is True
        assert route.primary == DocLLMTarget(backend="ollama", model="qwen3:30b-a3b", key="qwen3:30b-a3b")
        assert route.fallback == DocLLMTarget(backend="ollama", model="qwen3:14b", key="qwen3:14b")
        assert dict(route.backends) == {"ollama": HttpBackendSettings(kind="ollama", endpoint="http://localhost:11434")}

    def test_llamacpp_section_keeps_its_endpoint_and_models(self) -> None:
        classifier = ClassifierSettings(
            backend="llamacpp",
            endpoint="http://localhost:8002/",
            primary_model="gemma-27b",
            fallback_model="gemma-4b",
        )

        route = resolve_doc_route(classifier, {})

        assert route.legacy is True
        assert route.primary == DocLLMTarget(backend="llamacpp", model="gemma-27b", key="gemma-27b")
        assert route.fallback == DocLLMTarget(backend="llamacpp", model="gemma-4b", key="gemma-4b")
        assert dict(route.backends) == {
            "llamacpp": HttpBackendSettings(kind="llamacpp", endpoint="http://localhost:8002/")
        }

    def test_unrelated_llm_entries_stay_out_of_a_legacy_route(self) -> None:
        route = resolve_doc_route(ClassifierSettings(endpoint="http://nas:11434"), _NAMED)

        assert route.legacy is True
        assert dict(route.backends) == {"ollama": HttpBackendSettings(kind="ollama", endpoint="http://nas:11434")}

    def test_rejects_fallback_in_legacy_mode(self) -> None:
        with pytest.raises(LLMConfigError, match="doc.classifier.fallback needs doc.classifier.backend"):
            resolve_doc_route(ClassifierSettings(backend="ollama", fallback="fast"), {})

    @pytest.mark.parametrize("backend", ["vllm", "ollama-big", "Ollama"])
    def test_rejects_a_name_that_is_neither_an_entry_nor_legacy(self, backend: str) -> None:
        with pytest.raises(LLMConfigError) as excinfo:
            resolve_doc_route(ClassifierSettings(backend=backend), _NAMED)

        assert str(excinfo.value) == (
            f"doc.classifier.backend {backend!r} is neither an llm entry nor one of ['llamacpp', 'ollama']"
        )

    def test_config_error_is_a_value_error(self) -> None:
        with pytest.raises(ValueError, match="'vllm'"):
            resolve_doc_route(ClassifierSettings(backend="vllm"), {})


class TestResolveDocRouteNamed:
    def test_named_primary_and_fallback_ignore_legacy_fields(self) -> None:
        classifier = ClassifierSettings(
            backend="smart",
            fallback="fast",
            endpoint="http://ignored:1",
            primary_model="ignored-primary",
            fallback_model="ignored-fallback",
        )

        route = resolve_doc_route(classifier, _NAMED)

        assert route.legacy is False
        assert route.primary == DocLLMTarget(backend="smart", model=None, key="smart")
        assert route.fallback == DocLLMTarget(backend="fast", model=None, key="fast")
        assert dict(route.backends) == _NAMED

    def test_named_without_fallback_reuses_the_primary(self) -> None:
        route = resolve_doc_route(ClassifierSettings(backend="cli"), _NAMED)

        assert route.primary == DocLLMTarget(backend="cli", model=None, key="cli")
        assert route.fallback == DocLLMTarget(backend="cli", model=None, key="cli")

    def test_named_entry_wins_over_the_legacy_word(self) -> None:
        remote = HttpBackendSettings(kind="openai", endpoint="http://remote:9000/v1")

        route = resolve_doc_route(ClassifierSettings(backend="ollama"), {"ollama": remote})

        assert route.legacy is False
        assert route.primary == DocLLMTarget(backend="ollama", model=None, key="ollama")
        assert dict(route.backends) == {"ollama": remote}

    @pytest.mark.parametrize("fallback", ["fas", "fast2", "ollama"])
    def test_rejects_a_fallback_that_is_not_an_llm_entry(self, fallback: str) -> None:
        with pytest.raises(LLMConfigError) as excinfo:
            resolve_doc_route(ClassifierSettings(backend="smart", fallback=fallback), _NAMED)

        assert str(excinfo.value) == f"doc.classifier.fallback {fallback!r} is not an llm entry"


class TestDocRouteTarget:
    def test_legacy_keys_map_to_primary_and_fallback(self) -> None:
        route = resolve_doc_route(ClassifierSettings(), {})

        assert route.target("qwen3:30b-a3b") == route.primary
        assert route.target("qwen3:14b") == route.fallback

    @pytest.mark.parametrize(("backend", "key"), [("ollama", "llama3:70b"), ("llamacpp", "qwen3:30b")])
    def test_legacy_unknown_key_reaches_the_same_backend_as_a_model(self, backend: str, key: str) -> None:
        route = resolve_doc_route(ClassifierSettings(backend=backend), {})

        assert route.target(key) == DocLLMTarget(backend=backend, model=key, key=key)

    def test_named_keys_map_to_primary_and_fallback(self) -> None:
        route = resolve_doc_route(ClassifierSettings(backend="smart", fallback="fast"), _NAMED)

        assert route.target("smart") == DocLLMTarget(backend="smart", model=None, key="smart")
        assert route.target("fast") == DocLLMTarget(backend="fast", model=None, key="fast")

    @pytest.mark.parametrize("key", ["smar", "cli", "", "qwen3:30b-a3b"])
    def test_named_unknown_key_raises(self, key: str) -> None:
        route = resolve_doc_route(ClassifierSettings(backend="smart", fallback="fast"), _NAMED)

        with pytest.raises(LLMConfigError):
            route.target(key)


class TestBackendsEndToEnd:
    def test_classifier_parses_llamacpp_reply(self, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        registry = IssuerRegistry.model_validate(
            {
                "version": 1,
                "doc_types": list(DOC_TYPES),
                "reserved_slugs": ["unknown"],
                "issuers": {"philips": {"slug": "philips", "display_name": "Philips"}},
            }
        )
        fake = _fake_requests(
            mocker,
            _openai_reply({"issuer_slug": "philips", "doc_type": "invoice", "language": "cs", "confidence": 0.9}),
        )

        result = Classifier(_LLAMACPP).classify(
            "Faktura", SourceMetadata(source_kind="download", original_filename=None), registry
        )

        assert result.issuer_slug == "philips"
        assert result.doc_type == "invoice"
        assert fake.post.call_args.args[0] == "http://localhost:8002/v1/chat/completions"

    def test_extractor_parses_llamacpp_reply(self, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        _fake_requests(
            mocker,
            _openai_reply(
                {
                    "number": "1059707807",
                    "date": "2026-01-19",
                    "amount": 1699.15,
                    "currency": "CZK",
                    "summary": "Philips invoice.",
                }
            ),
        )

        result = Extractor(_LLAMACPP).extract("Faktura", "invoice")

        assert result.number == "1059707807"
        assert result.amount == 1699.15
