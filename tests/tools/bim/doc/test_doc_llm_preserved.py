"""Extractor domain rules the shared-transport cutover must keep (legacy settings route).

Sibling of ``test_extractor.py``, which is at its size limit.
"""

from __future__ import annotations

import datetime
import json
import types

import pytest
from bim.commands.doc.shared.settings_models import ClassifierSettings
from pytest_mock import MockerFixture


class _RequestException(OSError):
    pass


class _FakeExceptions(types.ModuleType):
    RequestException = _RequestException
    Timeout = type("Timeout", (_RequestException,), {})
    ConnectionError = type("ConnectionError", (_RequestException,), {})
    HTTPError = type("HTTPError", (_RequestException,), {})


class _MockResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise _FakeExceptions.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int = 1) -> list[bytes]:
        return [json.dumps(self._payload).encode()]

    def close(self) -> None:
        pass


def _install_fake_requests(mocker: MockerFixture, content_obj: dict[str, object]):
    fake_requests = mocker.MagicMock()
    fake_requests.exceptions = _FakeExceptions("requests.exceptions")
    fake_requests.post.return_value = _MockResponse({"message": {"content": json.dumps(content_obj)}})
    mocker.patch.dict(
        "sys.modules", {"requests": fake_requests, "requests.exceptions": fake_requests.exceptions}, clear=False
    )
    return fake_requests


def _invoice(extra: dict[str, object] | None = None) -> dict[str, object]:
    return {"number": "9999999999", "date": "2024-04-15", "amount": 1218.0, "currency": "CZK", **(extra or {})}


@pytest.fixture
def settings() -> ClassifierSettings:
    return ClassifierSettings()


class TestLegacyExtractorModelChoice:
    def test_extract_with_model_posts_the_supplied_fallback_model(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        fake_requests = _install_fake_requests(mocker, _invoice())

        result = Extractor(settings).extract_with_model("ocr", "invoice", model=settings.fallback_model)

        assert fake_requests.post.call_count == 1
        body = fake_requests.post.call_args.kwargs["json"]
        assert body["model"] == settings.fallback_model
        assert body["model"] != settings.primary_model
        assert result.number == "9999999999"


class TestPreservedSummaryRules:
    def test_long_summary_without_sentence_break_is_cut_at_a_word_boundary(
        self, settings: ClassifierSettings, mocker: MockerFixture
    ) -> None:
        from bim.commands.doc.shared.extractor import Extractor

        _install_fake_requests(mocker, _invoice({"summary": "word " * 200}))

        result = Extractor(settings).extract("ocr", "invoice")

        assert result.summary is not None
        assert len(result.summary) <= 600
        assert result.summary.endswith("word")
        assert set(result.summary.split(" ")) == {"word"}

    def test_partial_extraction_keeps_the_summary(self, settings: ClassifierSettings, mocker: MockerFixture) -> None:
        from bim.commands.doc.shared.extractor import Extractor, IncompleteExtraction

        _install_fake_requests(
            mocker, {"date": "2024-04-15", "amount": 1218.0, "currency": "CZK", "summary": "Some summary."}
        )

        with pytest.raises(IncompleteExtraction) as exc_info:
            Extractor(settings).extract("invoice text", "invoice")

        partial = exc_info.value.partial
        assert partial is not None
        assert partial.summary == "Some summary."
        assert partial.date == datetime.date(2024, 4, 15)
        assert partial.number is None
