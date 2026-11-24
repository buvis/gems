"""Named-mode doc LLM calls: Classifier and Extractor go through the shared registry.

``doc.classifier.backend`` and ``fallback`` name entries of the ``llm:`` map.
The fakes below stand in for those entries, so the tests see which entry each
call reached, with which request, timeout and model.
"""

from __future__ import annotations

import json

import pytest
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.llm import DOC_REQUEST_TIMEOUT_SECONDS, resolve_doc_route
from bim.commands.doc.shared.naming import DOC_TYPES
from bim.commands.doc.shared.rules.models import SourceMetadata
from bim.commands.doc.shared.settings_models import ClassifierSettings
from bim.shared.llm import (
    BackendError,
    BackendReason,
    CommandBackendSettings,
    HttpBackendSettings,
    JsonObject,
    LLMConfigError,
    LLMRegistry,
    LLMRequest,
)

_LLM = {
    "fast": HttpBackendSettings(kind="ollama", endpoint="http://gpu-box:11434", model="qwen3:8b"),
    "slow": CommandBackendSettings(kind="command", argv=["codex", "exec"]),
    "spare": HttpBackendSettings(kind="ollama", endpoint="http://spare:11434", model="qwen3:4b"),
}
_PRIMARY_MODEL = "qwen3:14b"
_OCR = "Faktura 2024-0042 od ČEZ"


class _FakeBackend:
    """A registry entry that records each call and returns a fixed object reply."""

    def __init__(self, name: str, reply: dict[str, object] | None = None, error: BackendError | None = None) -> None:
        self.name = name
        self.unattended_safe = True
        self.calls: list[tuple[LLMRequest, type, float, str | None]] = []
        self._reply = reply or {}
        self._error = error

    def complete(self, request: LLMRequest, schema: type, *, timeout: float, model: str | None = None) -> JsonObject:
        self.calls.append((request, schema, timeout, model))
        if self._error is not None:
            raise self._error
        return JsonObject(self._reply)


class _CommandStyleBackend(_FakeBackend):
    """Like a CLI backend: not unattended-safe, reads the request as one text, replies with JSON text."""

    def __init__(self, name: str, reply_text: str) -> None:
        super().__init__(name)
        self.unattended_safe = False
        self.stdin: list[str] = []
        self._reply_text = reply_text

    def complete(self, request: LLMRequest, schema: type, *, timeout: float, model: str | None = None) -> JsonObject:
        self.calls.append((request, schema, timeout, model))
        self.stdin.append(request.as_text())
        return JsonObject.model_validate_json(self._reply_text)


def _settings() -> ClassifierSettings:
    return ClassifierSettings(backend="fast", fallback="slow", primary_model=_PRIMARY_MODEL)


def _metadata() -> SourceMetadata:
    return SourceMetadata(source_kind="download", original_filename=None)


@pytest.fixture
def issuers() -> IssuerRegistry:
    return IssuerRegistry.model_validate(
        {
            "version": 1,
            "doc_types": list(DOC_TYPES),
            "reserved_slugs": ["unknown"],
            "issuers": {
                "cez-as": {"slug": "cez-as", "display_name": "ČEZ a.s.", "aliases": ["cez"]},
                "o2-czech": {"slug": "o2-czech", "display_name": "O2 Czech Republic a.s.", "aliases": ["o2"]},
            },
        }
    )


def _classifier(backends: dict[str, _FakeBackend]):
    from bim.commands.doc.shared.classifier import Classifier

    settings = _settings()
    return Classifier(settings, route=resolve_doc_route(settings, _LLM), registry=LLMRegistry(backends))


def _extractor(backends: dict[str, _FakeBackend]):
    from bim.commands.doc.shared.extractor import Extractor

    settings = _settings()
    return Extractor(settings, route=resolve_doc_route(settings, _LLM), registry=LLMRegistry(backends))


def _classify_reply(slug: str, doc_type: str) -> dict[str, object]:
    return {"issuer_slug": slug, "doc_type": doc_type, "language": "cs", "confidence": 0.9}


def _invoice_reply(number: str) -> dict[str, object]:
    return {"number": number, "date": "2024-04-15", "amount": 100.0, "currency": "CZK"}


def _assert_one_doc_call(backend: _FakeBackend) -> LLMRequest:
    assert len(backend.calls) == 1
    request, schema, timeout, model = backend.calls[0]
    assert schema is JsonObject
    assert timeout == DOC_REQUEST_TIMEOUT_SECONDS
    assert model is None
    assert request.system
    assert _OCR in request.prompt
    assert request.system != request.prompt
    return request


class TestNamedClassifierRouting:
    def test_classify_shim_calls_the_primary_entry_not_primary_model(self, issuers: IssuerRegistry) -> None:
        fast = _FakeBackend("fast", _classify_reply("cez", "invoice"))
        slow = _FakeBackend("slow", _classify_reply("o2", "statement"))
        spare = _FakeBackend("spare", _classify_reply("o2", "contract"))

        result = _classifier({"fast": fast, "slow": slow, "spare": spare}).classify(_OCR, _metadata(), issuers)

        _assert_one_doc_call(fast)
        assert slow.calls == []
        assert spare.calls == []
        assert result.issuer_slug == "cez-as"
        assert result.doc_type == "invoice"

    def test_classify_with_model_fallback_key_calls_the_fallback_entry(self, issuers: IssuerRegistry) -> None:
        fast = _FakeBackend("fast", _classify_reply("cez", "invoice"))
        slow = _FakeBackend("slow", _classify_reply("o2", "statement"))
        spare = _FakeBackend("spare", _classify_reply("cez", "contract"))

        result = _classifier({"fast": fast, "slow": slow, "spare": spare}).classify_with_model(
            _OCR, _metadata(), issuers, model="slow"
        )

        _assert_one_doc_call(slow)
        assert fast.calls == []
        assert spare.calls == []
        assert result.issuer_slug == "o2-czech"
        assert result.doc_type == "statement"

    @pytest.mark.parametrize("key", [_PRIMARY_MODEL, "spare", "slo", "fast "])
    def test_key_outside_the_route_raises_config_error_without_a_call(self, issuers: IssuerRegistry, key: str) -> None:
        fast = _FakeBackend("fast", _classify_reply("cez", "invoice"))
        spare = _FakeBackend("spare", _classify_reply("cez", "invoice"))

        with pytest.raises(LLMConfigError):
            _classifier({"fast": fast, "spare": spare}).classify_with_model(_OCR, _metadata(), issuers, model=key)
        assert fast.calls == []
        assert spare.calls == []

    def test_llm_map_alone_resolves_the_named_route(self, issuers: IssuerRegistry) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fast = _FakeBackend("fast", _classify_reply("o2", "invoice"))
        slow = _FakeBackend("slow", _classify_reply("cez", "invoice"))

        result = Classifier(_settings(), llm=_LLM, registry=LLMRegistry({"fast": fast, "slow": slow})).classify(
            _OCR, _metadata(), issuers
        )

        _assert_one_doc_call(fast)
        assert slow.calls == []
        assert result.issuer_slug == "o2-czech"

    def test_command_style_backend_with_json_text_works_as_classifier(self, issuers: IssuerRegistry) -> None:
        fast = _FakeBackend("fast", _classify_reply("cez", "invoice"))
        slow = _CommandStyleBackend("slow", json.dumps(_classify_reply("o2", "contract")))

        result = _classifier({"fast": fast, "slow": slow}).classify_with_model(_OCR, _metadata(), issuers, model="slow")

        request = _assert_one_doc_call(slow)
        assert slow.stdin == [request.as_text()]
        assert fast.calls == []
        assert result.issuer_slug == "o2-czech"
        assert result.doc_type == "contract"


class TestNamedExtractorRouting:
    def test_extract_shim_calls_the_primary_entry_not_primary_model(self) -> None:
        fast = _FakeBackend("fast", _invoice_reply("FAST-1"))
        slow = _FakeBackend("slow", _invoice_reply("SLOW-2"))
        spare = _FakeBackend("spare", _invoice_reply("SPARE-3"))

        result = _extractor({"fast": fast, "slow": slow, "spare": spare}).extract(_OCR, "invoice")

        _assert_one_doc_call(fast)
        assert slow.calls == []
        assert spare.calls == []
        assert result.number == "FAST-1"

    def test_extract_with_model_fallback_key_calls_the_fallback_entry(self) -> None:
        fast = _FakeBackend("fast", _invoice_reply("FAST-1"))
        slow = _FakeBackend("slow", _invoice_reply("SLOW-2"))
        spare = _FakeBackend("spare", _invoice_reply("SPARE-3"))

        result = _extractor({"fast": fast, "slow": slow, "spare": spare}).extract_with_model(
            _OCR, "invoice", model="slow"
        )

        _assert_one_doc_call(slow)
        assert fast.calls == []
        assert spare.calls == []
        assert result.number == "SLOW-2"

    def test_extract_with_model_unknown_key_raises_config_error(self) -> None:
        fast = _FakeBackend("fast", _invoice_reply("FAST-1"))

        with pytest.raises(LLMConfigError):
            _extractor({"fast": fast}).extract_with_model(_OCR, "invoice", model=_PRIMARY_MODEL)
        assert fast.calls == []


def _failing(reason: BackendReason, detail: str) -> dict[str, _FakeBackend]:
    error = BackendError(reason, detail, backend="slow")
    return {"fast": _FakeBackend("fast", _classify_reply("cez", "invoice")), "slow": _FakeBackend("slow", error=error)}


class TestNamedClassifierErrors:
    @pytest.mark.parametrize(
        ("reason", "detail", "message", "transient"),
        [
            (BackendReason.EXIT, "connection refused", "HTTP error calling slow: connection refused", True),
            (BackendReason.EXIT, "exited with code 2", "HTTP error calling slow: exited with code 2", True),
            (BackendReason.PARSE, "bad text", "Could not parse classifier JSON response: bad text", False),
            (BackendReason.SCHEMA, "reply is a list", "classifier response is not a JSON object", False),
        ],
    )
    def test_backend_error_maps_to_classifier_error(
        self, issuers: IssuerRegistry, reason: BackendReason, detail: str, message: str, transient: bool
    ) -> None:
        from bim.commands.doc.shared.classifier import ClassifierError

        with pytest.raises(ClassifierError) as exc_info:
            _classifier(_failing(reason, detail)).classify_with_model(_OCR, _metadata(), issuers, model="slow")
        assert str(exc_info.value) == message
        assert exc_info.value.transient is transient

    def test_timeout_is_reraised_unwrapped(self, issuers: IssuerRegistry) -> None:
        backends = _failing(BackendReason.TIMEOUT, "no reply within 60 seconds")

        with pytest.raises(BackendError) as exc_info:
            _classifier(backends).classify_with_model(_OCR, _metadata(), issuers, model="slow")
        assert exc_info.value.reason == BackendReason.TIMEOUT
        assert exc_info.value.backend == "slow"
        assert exc_info.value.detail == "no reply within 60 seconds"


class TestNamedExtractorErrors:
    @pytest.mark.parametrize(
        ("reason", "detail", "reasons", "transient"),
        [
            (BackendReason.EXIT, "connection refused", ["HTTP error: connection refused"], True),
            (BackendReason.EXIT, "exited with code 2", ["HTTP error: exited with code 2"], True),
            (BackendReason.PARSE, "bad text", ["could not parse model response as JSON: bad text"], False),
            (BackendReason.SCHEMA, "reply is a list", ["could not parse model response as JSON: not an object"], False),
        ],
    )
    def test_backend_error_maps_to_incomplete_extraction(
        self, reason: BackendReason, detail: str, reasons: list[str], transient: bool
    ) -> None:
        from bim.commands.doc.shared.extractor import IncompleteExtraction

        with pytest.raises(IncompleteExtraction) as exc_info:
            _extractor(_failing(reason, detail)).extract_with_model(_OCR, "invoice", model="slow")
        assert exc_info.value.reasons == reasons
        assert exc_info.value.transient is transient

    def test_timeout_is_reraised_unwrapped(self) -> None:
        raised = BackendError(BackendReason.TIMEOUT, "no reply within 60 seconds", backend="slow")
        backends = {"fast": _FakeBackend("fast", _invoice_reply("FAST-1")), "slow": _FakeBackend("slow", error=raised)}

        with pytest.raises(BackendError) as exc_info:
            _extractor(backends).extract_with_model(_OCR, "invoice", model="slow")
        assert exc_info.value is raised
        assert exc_info.value.reason == BackendReason.TIMEOUT
        assert exc_info.value.backend == "slow"


class TestNamedPinnedRouting:
    def test_classify_with_pinned_calls_only_the_named_entry(self, issuers: IssuerRegistry) -> None:
        fast = _FakeBackend("fast", _classify_reply("cez", "invoice"))
        slow = _FakeBackend("slow", {"doc_type": "statement", "language": "cs", "confidence": 0.7})
        spare = _FakeBackend("spare", _classify_reply("cez", "contract"))

        result = _classifier({"fast": fast, "slow": slow, "spare": spare}).classify_with_pinned(
            _OCR, _metadata(), issuers, {"issuer_slug": "o2-czech"}, model="slow"
        )

        _assert_one_doc_call(slow)
        assert fast.calls == []
        assert spare.calls == []
        assert result.issuer_slug == "o2-czech"
        assert result.doc_type == "statement"

    def test_extract_with_pinned_calls_only_the_named_entry(self) -> None:
        fast = _FakeBackend("fast", _invoice_reply("FAST-1"))
        slow = _FakeBackend("slow", {"date": "2024-04-15", "amount": 100.0, "currency": "CZK"})
        spare = _FakeBackend("spare", _invoice_reply("SPARE-3"))

        result = _extractor({"fast": fast, "slow": slow, "spare": spare}).extract_with_pinned(
            _OCR, "invoice", {"number": "PINNED-9"}, model="slow"
        )

        _assert_one_doc_call(slow)
        assert fast.calls == []
        assert spare.calls == []
        assert result.number == "PINNED-9"
        assert result.currency == "CZK"
