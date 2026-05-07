from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
from bim.commands.doc.shared.settings_models import ClassifierSettings
from pytest_mock import MockerFixture

FIXTURES = Path(__file__).parent / "fixtures" / "ocr_text"


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


def _raw_content_response(raw: str) -> _MockResponse:
    return _MockResponse({"message": {"content": raw}})


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


class TestExtractor:
    def test_invoice_happy_path(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        ocr_text = (FIXTURES / "cez_invoice.txt").read_text(encoding="utf-8")
        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "9999999999",
                    "date": "2024-04-15",
                    "amount": 1218.0,
                    "currency": "CZK",
                    "period": "2024-04",
                    "payment_due_date": "2024-04-30",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract(ocr_text, "invoice")

        assert result.doc_type == "invoice"
        assert result.number == "9999999999"
        assert result.date == datetime.date(2024, 4, 15)
        assert result.amount == 1218.0
        assert result.currency == "CZK"
        assert result.period == "2024-04"
        assert result.payment_due_date == datetime.date(2024, 4, 30)

    def test_statement_happy_path(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "period_start": "2024-03-01",
                    "period_end": "2024-03-31",
                    "balance": 383.0,
                    "currency": "CZK",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract("some statement text", "statement")

        assert result.doc_type == "statement"
        assert result.period_start == datetime.date(2024, 3, 1)
        assert result.period_end == datetime.date(2024, 3, 31)
        assert result.balance == 383.0
        assert result.currency == "CZK"

    def test_contract_happy_path(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "counterparty": "Acme s.r.o.",
                    "effective_date": "2024-01-01",
                    "term": "12 months",
                    "signed_date": "2023-12-15",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract("some contract text", "contract")

        assert result.doc_type == "contract"
        assert result.counterparty == "Acme s.r.o."
        assert result.effective_date == datetime.date(2024, 1, 1)
        assert result.term == "12 months"
        assert result.signed_date == datetime.date(2023, 12, 15)

    def test_receipt_happy_path(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "vendor": "Albert",
                    "date": "2024-04-10",
                    "amount": 234.50,
                    "currency": "CZK",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract("receipt text", "receipt")

        assert result.doc_type == "receipt"
        assert result.vendor == "Albert"
        assert result.date == datetime.date(2024, 4, 10)
        assert result.amount == 234.50
        assert result.currency == "CZK"

    def test_certificate_happy_path(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "subject": "TLS cert for example.com",
                    "issued_date": "2024-01-01",
                    "expires_date": "2025-01-01",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract("certificate text", "certificate")

        assert result.doc_type == "certificate"
        assert result.subject == "TLS cert for example.com"
        assert result.issued_date == datetime.date(2024, 1, 1)
        assert result.expires_date == datetime.date(2025, 1, 1)

    def test_correspondence_happy_path(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "subject": "Žádost o vyjádření",
                    "date": "2024-04-15",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract("correspondence text", "correspondence")

        assert result.doc_type == "correspondence"
        assert result.subject == "Žádost o vyjádření"
        assert result.date == datetime.date(2024, 4, 15)

    def test_reminder_happy_path(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "subject": "Upomínka č. 1",
                    "date": "2024-05-01",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract("reminder text", "reminder")

        assert result.doc_type == "reminder"
        assert result.subject == "Upomínka č. 1"
        assert result.date == datetime.date(2024, 5, 1)

    def test_other_happy_path(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "title": "Záznam ze schůze",
                    "date": "2024-06-10",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract("other text", "other")

        assert result.doc_type == "other"
        assert result.title == "Záznam ze schůze"
        assert result.date == datetime.date(2024, 6, 10)


class TestExtractorErrors:
    def test_invoice_missing_number_raises_incomplete(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        from bim.commands.doc.shared.extractor import Extractor, IncompleteExtraction

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "date": "2024-04-15",
                    "amount": 1218.0,
                    "currency": "CZK",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(IncompleteExtraction) as exc_info:
            Extractor(settings).extract("invoice text", "invoice")

        reasons = exc_info.value.reasons
        assert isinstance(reasons, list)
        assert any("number" in r for r in reasons)

    def test_unknown_doc_type_raises_value_error(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(mocker)
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(ValueError):
            Extractor(settings).extract("text", "totally-not-a-type")

        assert fake_requests.post.call_count == 0

    def test_iso_date_coercion(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "1",
                    "date": "2024-11-15",
                    "amount": 100.0,
                    "currency": "CZK",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract("text", "invoice")

        assert result.date == datetime.date(2024, 11, 15)

    def test_non_iso_date_string_raises_incomplete(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor, IncompleteExtraction

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "1",
                    "date": "15.11.2024",
                    "amount": 100.0,
                    "currency": "CZK",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(IncompleteExtraction) as exc_info:
            Extractor(settings).extract("text", "invoice")

        reasons = exc_info.value.reasons
        assert isinstance(reasons, list)
        assert any("date" in r for r in reasons)

    def test_json_parse_failure_raises_incomplete(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor, IncompleteExtraction

        fake_requests = _build_fake_requests(
            mocker,
            _raw_content_response("not valid json"),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(IncompleteExtraction):
            Extractor(settings).extract("text", "invoice")

    def test_invoice_amount_coercion_from_int(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "1",
                    "date": "2024-04-15",
                    "amount": 1218,
                    "currency": "CZK",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Extractor(settings).extract("text", "invoice")

        assert result.amount == 1218.0
        assert isinstance(result.amount, float)

    def test_invoice_amount_bool_value_raises_incomplete(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        from bim.commands.doc.shared.extractor import Extractor, IncompleteExtraction

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "1",
                    "date": "2024-04-15",
                    "amount": True,
                    "currency": "CZK",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(IncompleteExtraction) as exc_info:
            Extractor(settings).extract("text", "invoice")
        assert any("amount" in r for r in exc_info.value.reasons)

    def test_invoice_amount_unconvertible_string_raises_incomplete(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        from bim.commands.doc.shared.extractor import Extractor, IncompleteExtraction

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "1",
                    "date": "2024-04-15",
                    "amount": "abc",
                    "currency": "CZK",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(IncompleteExtraction) as exc_info:
            Extractor(settings).extract("text", "invoice")
        assert any("amount" in r for r in exc_info.value.reasons)

    def test_non_dict_json_response_raises_incomplete(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        from bim.commands.doc.shared.extractor import Extractor, IncompleteExtraction

        fake_requests = _build_fake_requests(
            mocker,
            _raw_content_response("[1, 2, 3]"),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(IncompleteExtraction):
            Extractor(settings).extract("text", "invoice")

    def test_lazy_import_no_requests_at_module_load(self, mocker: MockerFixture) -> None:
        import builtins
        import importlib
        import sys

        # Save original so we can restore it after; otherwise the reloaded
        # module's Extractor class diverges from the one imported at the top
        # of test_dependencies.py, breaking isinstance() checks later.
        original_module = sys.modules.get("bim.commands.doc.shared.extractor")

        try:
            for mod in list(sys.modules):
                if mod == "bim.commands.doc.shared.extractor":
                    del sys.modules[mod]

            real_import = builtins.__import__

            def fake_import(
                name: str,
                globals_: object = None,
                locals_: object = None,
                fromlist: tuple[str, ...] = (),
                level: int = 0,
            ) -> object:
                if name == "requests":
                    raise ModuleNotFoundError("requests pretend-missing")
                return real_import(name, globals_, locals_, fromlist, level)

            mocker.patch("builtins.__import__", side_effect=fake_import)
            importlib.import_module("bim.commands.doc.shared.extractor")
        finally:
            if original_module is not None:
                sys.modules["bim.commands.doc.shared.extractor"] = original_module

    def test_timeout_propagates_unwrapped(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(mocker)
        fake_requests.post.side_effect = fake_requests.exceptions.Timeout("read timeout")
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(fake_requests.exceptions.Timeout):
            Extractor(settings).extract("text", "invoice")


class TestExtractorPromptShape:
    def test_invoice_prompt_mentions_invoice_required_fields(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "1",
                    "date": "2024-04-15",
                    "amount": 100.0,
                    "currency": "CZK",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        Extractor(settings).extract("text", "invoice")

        _, kwargs = fake_requests.post.call_args
        system_joined = "\n".join(_system_messages(kwargs)).lower()
        assert "number" in system_joined
        assert "date" in system_joined
        assert "amount" in system_joined


class TestIncompleteExtractionPartial:
    """IncompleteExtraction must carry whatever fields the model got right
    so the pipeline can surface them in triage proposals."""

    def test_missing_required_field_attaches_partial_with_coerced_fields(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        # Invoice with date, amount, currency but no number - the existing
        # behaviour raises IncompleteExtraction for the missing number, but
        # the previously-coerced fields must travel along on exc.partial so
        # the human reviewer doesn't lose them.
        from bim.commands.doc.shared.extractor import Extractor, IncompleteExtraction

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "date": "2024-04-15",
                    "amount": 1218.0,
                    "currency": "CZK",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(IncompleteExtraction) as exc_info:
            Extractor(settings).extract("invoice text", "invoice")

        partial = exc_info.value.partial
        assert partial is not None
        assert partial.doc_type == "invoice"
        assert partial.date == datetime.date(2024, 4, 15)
        assert partial.amount == 1218.0
        assert partial.currency == "CZK"
        # The missing required field (number) stays None on the partial.
        assert partial.number is None

    def test_bad_date_accumulates_with_other_coerced_fields(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        # A single bad field must not discard the others - the human reviewer
        # benefits from seeing every successfully-coerced field, plus a clear
        # reason naming the one that failed.
        from bim.commands.doc.shared.extractor import Extractor, IncompleteExtraction

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "number": "INV-1",
                    "date": "15.11.2024",  # non-ISO, will not coerce
                    "amount": 1218.0,
                    "currency": "CZK",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(IncompleteExtraction) as exc_info:
            Extractor(settings).extract("invoice text", "invoice")

        partial = exc_info.value.partial
        assert partial is not None
        assert partial.number == "INV-1"
        assert partial.amount == 1218.0
        assert partial.currency == "CZK"
        assert partial.date is None
        # Reasons name the bad date.
        reasons = exc_info.value.reasons
        assert any("date" in r for r in reasons)


class TestIncompleteExtractionTransient:
    """IncompleteExtraction surfaces transient flag for HTTP failures only."""

    def test_default_transient_false(self) -> None:
        from bim.commands.doc.shared.extractor import IncompleteExtraction

        exc = IncompleteExtraction(["missing field date"])
        assert exc.transient is False

    def test_explicit_transient_true(self) -> None:
        from bim.commands.doc.shared.extractor import IncompleteExtraction

        exc = IncompleteExtraction(["HTTP error: refused"], transient=True)
        assert exc.transient is True

    def test_http_failure_marks_transient(self, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor, IncompleteExtraction
        from bim.commands.doc.shared.settings_models import ClassifierSettings

        # Build a fake requests module with a real Timeout exception class so
        # ``except requests.exceptions.Timeout`` doesn't raise TypeError.
        class _FakeTimeout(Exception):
            pass

        fake_exceptions = mocker.MagicMock()
        fake_exceptions.Timeout = _FakeTimeout
        fake_requests = mocker.MagicMock()
        fake_requests.exceptions = fake_exceptions
        fake_requests.post.side_effect = ConnectionError("refused")
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        ext = Extractor(ClassifierSettings())
        with pytest.raises(IncompleteExtraction) as exc_info:
            ext.extract("ocr text", "invoice")
        assert exc_info.value.transient is True

    def test_missing_field_failure_is_not_transient(self, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor, IncompleteExtraction
        from bim.commands.doc.shared.settings_models import ClassifierSettings

        class _Resp:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                # All required invoice fields missing.
                return {"message": {"content": json.dumps({})}}

        class _FakeTimeout(Exception):
            pass

        fake_exceptions = mocker.MagicMock()
        fake_exceptions.Timeout = _FakeTimeout
        fake_requests = mocker.MagicMock()
        fake_requests.exceptions = fake_exceptions
        fake_requests.post.return_value = _Resp()
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        ext = Extractor(ClassifierSettings())
        with pytest.raises(IncompleteExtraction) as exc_info:
            ext.extract("ocr text", "invoice")
        assert exc_info.value.transient is False
