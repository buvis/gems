"""Tests for ``Extractor.extract_with_pinned``.

These tests assume the rule engine pre-pins some of the extractor's required
fields (number, date, amount, currency, ...) and the extractor should:

  * skip the LLM call entirely when all required fields for ``doc_type`` are
    pinned, and
  * build a reduced prompt asking only for the un-pinned required fields
    otherwise.

Canonical key naming: the rule engine emits canonical "doc_*" prefixed names
(``doc_number``, ``doc_date``, ``doc_amount``, ``doc_currency``) but bare
field names (``number``, ``date``, ``amount``, ``currency``) MUST also be
accepted - the implementation treats them as synonyms when reading the
``pinned`` mapping.

Non-extractor pinned keys (``issuer_slug``, ``issuer_display``,
``doc_language``) are silently ignored at the extractor level - they belong
to the classifier or the writer, not here.

Pinned values WIN on disagreement with the LLM: when the same field is both
pinned and returned by the model, the pinned value lands on the result.
"""

from __future__ import annotations

import datetime
import json

import pytest
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


def _system_messages(call_kwargs: dict[str, object]) -> list[str]:
    body = call_kwargs["json"]
    assert isinstance(body, dict)
    messages = body["messages"]
    assert isinstance(messages, list)
    return [m["content"] for m in messages if m.get("role") == "system"]


@pytest.fixture
def settings() -> ClassifierSettings:
    return ClassifierSettings()


class TestExtractorPinnedFullSkip:
    """When every required field is pinned, the LLM call must be skipped."""

    def test_invoice_full_pin_doc_prefixed_skips_llm(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(mocker)
        fake_requests.post.side_effect = AssertionError(
            "extract_with_pinned must skip HTTP when all required fields for doc_type are pinned"
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract_with_pinned(
            "ocr text",
            "invoice",
            {
                "doc_number": "INV-1",
                "doc_date": "2024-11-15",
                "doc_amount": "4218",
                "doc_currency": "CZK",
            },
            model=settings.primary_model,
        )

        assert result.doc_type == "invoice"
        assert result.number == "INV-1"
        assert result.date == datetime.date(2024, 11, 15)
        assert result.amount == 4218.0
        assert isinstance(result.amount, float)
        assert result.currency == "CZK"
        # Non-required invoice fields default to None.
        assert result.period is None
        assert result.payment_due_date is None

    def test_invoice_full_pin_bare_keys_skips_llm(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        # Defense in depth: the rule engine emits doc_-prefixed keys, but the
        # extractor should also accept bare keys (``number``, ``date``, ...)
        # as synonyms - the result is identical.
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(mocker)
        fake_requests.post.side_effect = AssertionError(
            "extract_with_pinned must skip HTTP when all required fields for doc_type are pinned"
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract_with_pinned(
            "ocr text",
            "invoice",
            {
                "number": "INV-1",
                "date": "2024-11-15",
                "amount": 4218,
                "currency": "CZK",
            },
            model=settings.primary_model,
        )

        assert result.doc_type == "invoice"
        assert result.number == "INV-1"
        assert result.date == datetime.date(2024, 11, 15)
        assert result.amount == 4218.0
        assert result.currency == "CZK"

    def test_invoice_full_pin_pre_coerced_values_skips_llm(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        # The rule engine's ``apply_extract`` may have already applied
        # transforms like ``strip_whitespace_to_int`` so pinned values arrive
        # already-typed. The extractor must accept them as-is without
        # re-coercing or rejecting them.
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(mocker)
        fake_requests.post.side_effect = AssertionError(
            "extract_with_pinned must skip HTTP when all required fields for doc_type are pinned"
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract_with_pinned(
            "ocr text",
            "invoice",
            {
                "doc_number": "INV-1",
                "doc_date": datetime.date(2024, 11, 15),
                "doc_amount": 4218,
                "doc_currency": "CZK",
            },
            model=settings.primary_model,
        )

        assert result.doc_type == "invoice"
        assert result.number == "INV-1"
        assert result.date == datetime.date(2024, 11, 15)
        assert result.amount == 4218.0
        assert result.currency == "CZK"

    def test_invoice_full_pin_decimal_amount_skips_llm(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        # The rule engine's ``strip_whitespace_to_decimal`` transform returns a
        # ``Decimal``. ``extract_with_pinned`` must coerce it to ``float`` like
        # the LLM-path does for numeric strings, not reject it as a non-coercible
        # type. The PRD's ``cez-invoice-2024-template`` example pins
        # ``doc_amount`` exactly this way.
        from decimal import Decimal

        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(mocker)
        fake_requests.post.side_effect = AssertionError(
            "extract_with_pinned must skip HTTP when all required fields for doc_type are pinned"
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract_with_pinned(
            "ocr text",
            "invoice",
            {
                "doc_number": "INV-1",
                "doc_date": datetime.date(2024, 11, 15),
                "doc_amount": Decimal("4218.50"),
                "doc_currency": "CZK",
            },
            model=settings.primary_model,
        )

        assert result.doc_type == "invoice"
        assert result.number == "INV-1"
        assert result.date == datetime.date(2024, 11, 15)
        assert result.amount == 4218.5
        assert isinstance(result.amount, float)
        assert result.currency == "CZK"

    def test_non_extractor_pinned_keys_are_ignored(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        # ``issuer_slug``, ``issuer_display`` and ``doc_language`` belong to
        # the classifier / writer, not the extractor. They must not satisfy
        # any required field, so the LLM call still happens for the un-pinned
        # ones.
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "INV-1",
                    "date": "2024-11-15",
                    "amount": 4218.0,
                },
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract_with_pinned(
            "ocr text",
            "invoice",
            {
                "issuer_slug": "cez-as",
                "issuer_display": "ČEZ a.s.",
                "doc_language": "cs",
                "doc_currency": "CZK",
            },
            model=settings.primary_model,
        )

        assert fake_requests.post.call_count == 1
        assert result.doc_type == "invoice"
        assert result.number == "INV-1"
        assert result.date == datetime.date(2024, 11, 15)
        assert result.amount == 4218.0
        assert result.currency == "CZK"


class TestExtractorPinnedReducedPrompt:
    """When some fields are pinned, the prompt should ask only for the rest."""

    def test_partial_pin_reduces_required_fields_in_prompt(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "INV-1",
                    "date": "2024-11-15",
                    "amount": 4218,
                },
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract_with_pinned(
            "ocr text",
            "invoice",
            {"doc_currency": "CZK"},
            model=settings.primary_model,
        )

        assert fake_requests.post.call_count == 1
        _, kwargs = fake_requests.post.call_args
        system_joined = "\n".join(_system_messages(kwargs))
        # Find the "Required fields:" line and assert currency is absent.
        required_lines = [line for line in system_joined.splitlines() if "Required fields" in line]
        assert required_lines, f"system prompt missing 'Required fields' line: {system_joined!r}"
        required_line = required_lines[0].lower()
        assert "currency" not in required_line
        # The other three are still required.
        assert "number" in required_line
        assert "date" in required_line
        assert "amount" in required_line

        # Final result merges pinned currency in.
        assert result.doc_type == "invoice"
        assert result.number == "INV-1"
        assert result.date == datetime.date(2024, 11, 15)
        assert result.amount == 4218.0
        assert result.currency == "CZK"

    def test_partial_pin_bare_keys_also_reduce_prompt(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "INV-1",
                    "date": "2024-11-15",
                    "amount": 4218,
                },
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract_with_pinned(
            "ocr text",
            "invoice",
            {"currency": "CZK"},
            model=settings.primary_model,
        )

        assert fake_requests.post.call_count == 1
        _, kwargs = fake_requests.post.call_args
        system_joined = "\n".join(_system_messages(kwargs))
        required_lines = [line for line in system_joined.splitlines() if "Required fields" in line]
        assert required_lines
        assert "currency" not in required_lines[0].lower()
        assert result.currency == "CZK"


class TestExtractorPinnedWinsOnDisagreement:
    """Pinned values must win when the LLM returns a different value."""

    def test_pinned_currency_overrides_llm_currency(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "INV-1",
                    "date": "2024-11-15",
                    "amount": 4218,
                    "currency": "EUR",
                },
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract_with_pinned(
            "ocr text",
            "invoice",
            {"doc_currency": "CZK"},
            model=settings.primary_model,
        )

        assert fake_requests.post.call_count == 1
        # Pinned wins: CZK, not EUR.
        assert result.currency == "CZK"
        assert result.number == "INV-1"
        assert result.date == datetime.date(2024, 11, 15)
        assert result.amount == 4218.0


class TestExtractorPinnedModel:
    """The ``model`` kwarg must reach the request body verbatim."""

    def test_empty_pinned_falls_through_to_llm_with_supplied_model(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "INV-1",
                    "date": "2024-11-15",
                    "amount": 4218,
                    "currency": "CZK",
                },
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract_with_pinned(
            "ocr text",
            "invoice",
            {},
            model="some-other-model:latest",
        )

        assert fake_requests.post.call_count == 1
        _, kwargs = fake_requests.post.call_args
        body = kwargs["json"]
        assert isinstance(body, dict)
        assert body["model"] == "some-other-model:latest"
        assert result.doc_type == "invoice"
        assert result.number == "INV-1"
        assert result.currency == "CZK"
