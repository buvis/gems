from __future__ import annotations

import json

import pytest
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.llm import chat_content, chat_request
from bim.commands.doc.shared.naming import DOC_TYPES
from bim.commands.doc.shared.rules.models import SourceMetadata
from bim.commands.doc.shared.settings_models import ClassifierSettings
from pydantic import ValidationError
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


class TestBackendSetting:
    def test_rejects_unknown_backend(self) -> None:
        with pytest.raises(ValidationError):
            ClassifierSettings(backend="vllm")


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
