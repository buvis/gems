from __future__ import annotations

import json
import types

import pytest
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.llm import (
    DOC_REQUEST_TIMEOUT_SECONDS,
    LEGACY_DOC_BACKENDS,
    DocLLMTarget,
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

_LLAMACPP = ClassifierSettings(backend="llamacpp", endpoint="http://localhost:8002/")


class _RequestException(OSError):
    pass


class _FakeExceptions(types.ModuleType):
    RequestException = _RequestException
    Timeout = type("Timeout", (_RequestException,), {})
    ConnectionError = type("ConnectionError", (_RequestException,), {})
    HTTPError = type("HTTPError", (_RequestException,), {})


class _MockResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.status_code = 200

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int = 1) -> list[bytes]:
        return [json.dumps(self._payload).encode()]

    def close(self) -> None:
        pass


def _openai_reply(content: dict[str, object]) -> _MockResponse:
    return _MockResponse({"choices": [{"message": {"role": "assistant", "content": json.dumps(content)}}]})


def _fake_requests(mocker: MockerFixture, response: _MockResponse) -> object:
    fake = mocker.MagicMock()
    fake.exceptions = _FakeExceptions("requests.exceptions")
    fake.post.return_value = response
    mocker.patch.dict("sys.modules", {"requests": fake, "requests.exceptions": fake.exceptions}, clear=False)
    return fake


_FAST = HttpBackendSettings(kind="ollama", endpoint="http://gpu-box:11434", model="qwen3:8b")
_SMART = ClaudeBackendSettings(kind="claude", model="opus")
_CLI = CommandBackendSettings(kind="command", argv=["codex", "exec"])
_NAMED = {"fast": _FAST, "smart": _SMART, "cli": _CLI}


def _assert_target(target: DocLLMTarget, backend: str, model: str | None, key: str) -> None:
    # Field by field: DocLLMTarget.__eq__ belongs to the type under test.
    assert type(target) is DocLLMTarget
    assert (target.backend, target.model, target.key) == (backend, model, key)


class TestDocRouteConstants:
    def test_legacy_backends_are_ollama_and_llamacpp(self) -> None:
        assert LEGACY_DOC_BACKENDS == frozenset({"ollama", "llamacpp"})
        assert isinstance(LEGACY_DOC_BACKENDS, frozenset)

    def test_request_timeout_is_sixty_seconds(self) -> None:
        assert DOC_REQUEST_TIMEOUT_SECONDS == 60


class TestResolveDocRouteLegacy:
    def test_defaults_keep_the_original_ollama_endpoint_and_models(self) -> None:
        route = resolve_doc_route(ClassifierSettings(), {})

        assert route.legacy is True
        assert route.primary == DocLLMTarget(backend="ollama", model="qwen3:30b-a3b", key="qwen3:30b-a3b")
        assert route.fallback == DocLLMTarget(backend="ollama", model="qwen3:14b", key="qwen3:14b")
        _assert_target(route.primary, "ollama", "qwen3:30b-a3b", "qwen3:30b-a3b")
        _assert_target(route.fallback, "ollama", "qwen3:14b", "qwen3:14b")
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
        _assert_target(route.primary, "llamacpp", "gemma-27b", "gemma-27b")
        _assert_target(route.fallback, "llamacpp", "gemma-4b", "gemma-4b")
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

    def test_rejects_fallback_in_legacy_mode_even_when_the_llm_map_holds_it(self) -> None:
        with pytest.raises(LLMConfigError, match="doc.classifier.fallback needs doc.classifier.backend"):
            resolve_doc_route(ClassifierSettings(backend="ollama", fallback="fast"), {"fast": _FAST})

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
        _assert_target(route.primary, "smart", None, "smart")
        _assert_target(route.fallback, "fast", None, "fast")
        assert dict(route.backends) == _NAMED

    def test_named_without_fallback_reuses_the_primary(self) -> None:
        route = resolve_doc_route(ClassifierSettings(backend="cli"), _NAMED)

        assert route.primary == DocLLMTarget(backend="cli", model=None, key="cli")
        assert route.fallback == DocLLMTarget(backend="cli", model=None, key="cli")
        _assert_target(route.primary, "cli", None, "cli")
        _assert_target(route.fallback, "cli", None, "cli")

    def test_named_entry_wins_over_the_legacy_word(self) -> None:
        remote = HttpBackendSettings(kind="openai", endpoint="http://remote:9000/v1")

        route = resolve_doc_route(ClassifierSettings(backend="ollama"), {"ollama": remote})

        assert route.legacy is False
        assert route.primary == DocLLMTarget(backend="ollama", model=None, key="ollama")
        _assert_target(route.primary, "ollama", None, "ollama")
        _assert_target(route.fallback, "ollama", None, "ollama")
        assert dict(route.backends) == {"ollama": remote}

    @pytest.mark.parametrize("fallback", ["fas", "fast2", "ollama"])
    def test_rejects_a_fallback_that_is_not_an_llm_entry(self, fallback: str) -> None:
        with pytest.raises(LLMConfigError) as excinfo:
            resolve_doc_route(ClassifierSettings(backend="smart", fallback=fallback), _NAMED)

        assert str(excinfo.value) == f"doc.classifier.fallback {fallback!r} is not an llm entry"

    def test_fallback_name_matches_llm_entries_case_sensitively(self) -> None:
        with pytest.raises(LLMConfigError) as excinfo:
            resolve_doc_route(ClassifierSettings(backend="fast", fallback="Fast"), {"fast": _FAST})

        assert str(excinfo.value) == "doc.classifier.fallback 'Fast' is not an llm entry"


class TestDocRouteTarget:
    def test_legacy_keys_map_to_primary_and_fallback(self) -> None:
        route = resolve_doc_route(ClassifierSettings(), {})

        assert route.target("qwen3:30b-a3b") == route.primary
        assert route.target("qwen3:14b") == route.fallback
        _assert_target(route.target("qwen3:30b-a3b"), "ollama", "qwen3:30b-a3b", "qwen3:30b-a3b")
        _assert_target(route.target("qwen3:14b"), "ollama", "qwen3:14b", "qwen3:14b")

    @pytest.mark.parametrize(("backend", "key"), [("ollama", "llama3:70b"), ("llamacpp", "qwen3:30b")])
    def test_legacy_unknown_key_reaches_the_same_backend_as_a_model(self, backend: str, key: str) -> None:
        route = resolve_doc_route(ClassifierSettings(backend=backend), {})

        assert route.target(key) == DocLLMTarget(backend=backend, model=key, key=key)
        _assert_target(route.target(key), backend, key, key)

    def test_named_keys_map_to_primary_and_fallback(self) -> None:
        route = resolve_doc_route(ClassifierSettings(backend="smart", fallback="fast"), _NAMED)

        assert route.target("smart") == DocLLMTarget(backend="smart", model=None, key="smart")
        assert route.target("fast") == DocLLMTarget(backend="fast", model=None, key="fast")
        _assert_target(route.target("smart"), "smart", None, "smart")
        _assert_target(route.target("fast"), "fast", None, "fast")

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
