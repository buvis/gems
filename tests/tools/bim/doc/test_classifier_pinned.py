"""Tests for ``Classifier.classify_with_pinned``.

These tests assume the rule engine pre-pins some of {issuer_slug, doc_type,
language} and the classifier should:

  * skip the LLM call entirely when all three are pinned, and
  * build a reduced prompt asking only for un-pinned fields otherwise.

Canonical key naming: the classifier's internal field is ``language``, but the
rule engine's extract spec uses ``doc_language``. These tests assume
``classify_with_pinned`` accepts EITHER key for the language field. The
implementation is expected to treat ``doc_language`` as a synonym for
``language`` when reading the ``pinned`` mapping.
"""

from __future__ import annotations

import json

import pytest
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.naming import DOC_TYPES
from bim.commands.doc.shared.settings_models import ClassifierSettings
from pytest_mock import MockerFixture


class _MockResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _content_response(content_obj: dict[str, object]) -> _MockResponse:
    return _MockResponse({"message": {"content": json.dumps(content_obj)}})


def _build_fake_requests(mocker: MockerFixture, response: _MockResponse | None = None):
    fake_requests = mocker.MagicMock()
    fake_requests.exceptions = mocker.MagicMock()
    fake_requests.exceptions.Timeout = type("Timeout", (Exception,), {})
    if response is not None:
        fake_requests.post.return_value = response
    return fake_requests


def _all_message_contents(call_kwargs: dict[str, object]) -> list[str]:
    body = call_kwargs["json"]
    assert isinstance(body, dict)
    messages = body["messages"]
    assert isinstance(messages, list)
    return [m["content"] for m in messages]


@pytest.fixture
def registry() -> IssuerRegistry:
    return IssuerRegistry.model_validate(
        {
            "version": 1,
            "doc_types": list(DOC_TYPES),
            "reserved_slugs": ["unknown"],
            "issuers": {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "ČEZ a.s.",
                    "aliases": ["ČEZ", "ČEZ Prodej", "cez", "cez.cz"],
                },
                "o2-czech": {
                    "slug": "o2-czech",
                    "display_name": "O2 Czech Republic a.s.",
                    "aliases": ["O2", "o2.cz"],
                },
            },
        }
    )


@pytest.fixture
def settings() -> ClassifierSettings:
    return ClassifierSettings()


class TestClassifyWithPinnedFullSkip:
    """When all 3 fields are pinned the LLM is bypassed entirely."""

    def test_all_three_pinned_skips_http_call(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(mocker)
        fake_requests.post.side_effect = AssertionError(
            "classify_with_pinned must skip HTTP when all required fields are pinned"
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Classifier(settings).classify_with_pinned(
            "ocr text",
            {},
            registry,
            {"issuer_slug": "cez-as", "doc_type": "invoice", "language": "cs"},
            model=settings.primary_model,
        )

        assert result.issuer_slug == "cez-as"
        assert result.issuer_display == "ČEZ a.s."
        assert result.doc_type == "invoice"
        assert result.language == "cs"
        assert result.confidence == 1.0
        assert result.issuer_guess is None

    def test_all_three_pinned_with_doc_language_alias_also_skips(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        """The rule engine extract spec uses ``doc_language``; classifier uses
        ``language`` internally. Either key in ``pinned`` should mean fully
        pinned -> no LLM call."""
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(mocker)
        fake_requests.post.side_effect = AssertionError(
            "classify_with_pinned must skip HTTP when all required fields are pinned"
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Classifier(settings).classify_with_pinned(
            "ocr text",
            {},
            registry,
            {"issuer_slug": "cez-as", "doc_type": "invoice", "doc_language": "cs"},
            model=settings.primary_model,
        )

        assert result.issuer_slug == "cez-as"
        assert result.language == "cs"
        assert result.doc_type == "invoice"
        assert result.confidence == 1.0

    def test_all_three_pinned_with_explicit_issuer_display(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        """When ``pinned`` includes ``issuer_display``, use it directly."""
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(mocker)
        fake_requests.post.side_effect = AssertionError(
            "classify_with_pinned must skip HTTP when all required fields are pinned"
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Classifier(settings).classify_with_pinned(
            "ocr text",
            {},
            registry,
            {
                "issuer_slug": "cez-as",
                "issuer_display": "ČEZ a.s.",
                "doc_type": "invoice",
                "language": "cs",
            },
            model=settings.primary_model,
        )

        assert result.issuer_slug == "cez-as"
        assert result.issuer_display == "ČEZ a.s."

    def test_pinned_issuer_slug_not_in_registry_synthesises_result(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        """When the rule engine pins an unknown slug we trust it; we don't
        fall through to the LLM. ``issuer_display`` collapses to None (or the
        same string) and ``issuer_guess`` is None."""
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(mocker)
        fake_requests.post.side_effect = AssertionError(
            "classify_with_pinned must skip HTTP when all required fields are pinned"
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Classifier(settings).classify_with_pinned(
            "ocr text",
            {},
            registry,
            {"issuer_slug": "unknown-issuer", "doc_type": "invoice", "language": "cs"},
            model=settings.primary_model,
        )

        assert result.issuer_slug == "unknown-issuer"
        # The implementation may return None or echo the slug back; both are
        # acceptable since no registry entry exists.
        assert result.issuer_display in (None, "unknown-issuer")
        assert result.issuer_guess is None
        assert result.doc_type == "invoice"
        assert result.language == "cs"
        assert result.confidence == 1.0


class TestClassifyWithPinnedPartialIssuer:
    """Issuer pre-pinned, doc_type+language still need the model."""

    def test_issuer_pinned_prompt_omits_issuer_request(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(
            mocker,
            _content_response({"doc_type": "invoice", "language": "cs", "confidence": 0.9}),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Classifier(settings).classify_with_pinned(
            "ocr text",
            {},
            registry,
            {"issuer_slug": "cez-as"},
            model=settings.primary_model,
        )

        assert fake_requests.post.call_count == 1
        _, kwargs = fake_requests.post.call_args
        joined = "\n".join(_all_message_contents(kwargs))
        # Reduced prompt must NOT ask for issuer_slug.
        assert "issuer_slug" not in joined.lower()
        # ...but must instruct the model to return the un-pinned fields.
        assert "doc_type" in joined.lower()
        assert "language" in joined.lower()
        assert "confidence" in joined.lower()

        # Result merges pinned issuer with model-provided fields.
        assert result.issuer_slug == "cez-as"
        assert result.issuer_display == "ČEZ a.s."
        assert result.doc_type == "invoice"
        assert result.language == "cs"
        assert result.confidence == 0.9
        assert result.issuer_guess is None


class TestClassifyWithPinnedPartialDocType:
    """doc_type pre-pinned (e.g. partial fingerprint), issuer+language unknown."""

    def test_doc_type_pinned_prompt_omits_doc_type_request(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(
            mocker,
            _content_response({"issuer_slug": "cez", "language": "cs", "confidence": 0.85}),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Classifier(settings).classify_with_pinned(
            "ocr text",
            {},
            registry,
            {"doc_type": "invoice"},
            model=settings.primary_model,
        )

        assert fake_requests.post.call_count == 1
        _, kwargs = fake_requests.post.call_args
        joined = "\n".join(_all_message_contents(kwargs))
        # Reduced prompt must NOT ask for doc_type.
        assert "doc_type" not in joined.lower()
        # ...but should ask for issuer_slug, language, and confidence.
        assert "issuer_slug" in joined.lower()
        assert "language" in joined.lower()
        assert "confidence" in joined.lower()

        # Pinned doc_type wins; other fields come from the model (via alias resolution).
        assert result.doc_type == "invoice"
        assert result.issuer_slug == "cez-as"
        assert result.issuer_display == "ČEZ a.s."
        assert result.language == "cs"
        assert result.confidence == 0.85


class TestClassifyWithPinnedModelOverride:
    """``model`` keyword routes to the requested Ollama model on partial pins."""

    def test_model_kwarg_used_in_request_body(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(
            mocker,
            _content_response({"doc_type": "invoice", "language": "cs", "confidence": 0.9}),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        Classifier(settings).classify_with_pinned(
            "ocr text",
            {},
            registry,
            {"issuer_slug": "cez-as"},
            model="custom-fallback-model",
        )

        _, kwargs = fake_requests.post.call_args
        body = kwargs["json"]
        assert body["model"] == "custom-fallback-model"
