from __future__ import annotations

import json
from pathlib import Path

import pytest
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.naming import DOC_TYPES
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


def _system_messages(call_kwargs: dict[str, object]) -> list[str]:
    body = call_kwargs["json"]
    assert isinstance(body, dict)
    messages = body["messages"]
    assert isinstance(messages, list)
    return [m["content"] for m in messages if m.get("role") == "system"]


def _all_message_contents(call_kwargs: dict[str, object]) -> list[str]:
    body = call_kwargs["json"]
    assert isinstance(body, dict)
    messages = body["messages"]
    assert isinstance(messages, list)
    return [m["content"] for m in messages]


class TestClassifier:
    def test_alias_mapping_resolves_to_canonical_slug(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        ocr_text = (FIXTURES / "cez_invoice.txt").read_text(encoding="utf-8")
        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "issuer_slug": "cez",
                    "doc_type": "invoice",
                    "language": "cs",
                    "confidence": 0.94,
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Classifier(settings).classify(ocr_text, {}, registry)

        assert result.issuer_slug == "cez-as"
        assert result.issuer_display == "ČEZ a.s."
        assert result.doc_type == "invoice"
        assert result.language == "cs"
        assert result.confidence == 0.94

    def test_unknown_issuer_returns_none_slug_and_display(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        ocr_text = (FIXTURES / "unknown_issuer_invoice.txt").read_text(encoding="utf-8")
        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "issuer_slug": "totally-unknown-llc",
                    "doc_type": "invoice",
                    "language": "cs",
                    "confidence": 0.55,
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Classifier(settings).classify(ocr_text, {}, registry)

        assert result.issuer_slug is None
        assert result.issuer_display is None
        assert result.doc_type == "invoice"

    def test_doc_type_only_omits_issuer_from_prompt(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "doc_type": "statement",
                    "language": "cs",
                    "confidence": 0.88,
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Classifier(settings).classify("some text", {}, registry, doc_type_only=True)

        assert fake_requests.post.call_count == 1
        _, kwargs = fake_requests.post.call_args
        all_contents = _all_message_contents(kwargs)
        joined = "\n".join(all_contents)
        assert "issuer" not in joined.lower()
        assert "cez-as" not in joined
        assert "o2-czech" not in joined

        assert result.doc_type == "statement"
        assert result.issuer_slug is None
        assert result.issuer_display is None
        assert result.language == "cs"

    def test_two_shot_examples_present_in_system_prompt_for_full_classify(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "issuer_slug": "cez",
                    "doc_type": "invoice",
                    "language": "cs",
                    "confidence": 0.9,
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        Classifier(settings).classify("text", {}, registry, doc_type_only=False)

        _, kwargs = fake_requests.post.call_args
        system_msgs = _system_messages(kwargs)
        joined_system = "\n".join(system_msgs)
        assert "Faktura" in joined_system
        assert "Vyúčtování" in joined_system

    def test_request_body_shape(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "issuer_slug": "cez",
                    "doc_type": "invoice",
                    "language": "cs",
                    "confidence": 0.9,
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        Classifier(settings).classify("text", {}, registry)

        args, kwargs = fake_requests.post.call_args
        url = args[0] if args else kwargs.get("url")
        assert url == f"{settings.endpoint.rstrip('/')}/api/chat"

        body = kwargs["json"]
        assert body["model"] == settings.primary_model
        assert body["format"] == "json"
        assert body["stream"] is False
        assert isinstance(body["messages"], list)
        assert len(body["messages"]) >= 2

        roles = [m.get("role") for m in body["messages"]]
        assert "system" in roles
        assert "user" in roles

    def test_json_parse_failure_raises_classifier_error(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier, ClassifierError

        fake_requests = _build_fake_requests(
            mocker,
            _raw_content_response("sorry, I cannot answer in JSON"),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(ClassifierError):
            Classifier(settings).classify("text", {}, registry)

    def test_http_error_raises_classifier_error(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier, ClassifierError

        fake_requests = _build_fake_requests(
            mocker,
            _MockResponse({"message": {"content": "{}"}}, status_code=500),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(ClassifierError):
            Classifier(settings).classify("text", {}, registry)

    def test_timeout_propagates_unwrapped(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(mocker)
        fake_requests.post.side_effect = fake_requests.exceptions.Timeout("read timeout")
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(fake_requests.exceptions.Timeout):
            Classifier(settings).classify("text", {}, registry)

    def test_classifier_missing_doc_type_raises_classifier_error(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier, ClassifierError

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "issuer_slug": "cez",
                    "language": "cs",
                    "confidence": 0.9,
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(ClassifierError) as exc_info:
            Classifier(settings).classify("text", {}, registry)
        assert "doc_type" in str(exc_info.value)

    def test_classifier_missing_confidence_raises_classifier_error(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier, ClassifierError

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "issuer_slug": "cez",
                    "doc_type": "invoice",
                    "language": "cs",
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(ClassifierError) as exc_info:
            Classifier(settings).classify("text", {}, registry)
        assert "confidence" in str(exc_info.value)

    def test_alias_list_included_in_system_prompt_for_full_classify(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(
            mocker,
            _content_response(
                {
                    "issuer_slug": "cez",
                    "doc_type": "invoice",
                    "language": "cs",
                    "confidence": 0.9,
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        Classifier(settings).classify("text", {}, registry, doc_type_only=False)

        _, kwargs = fake_requests.post.call_args
        system_joined = "\n".join(_system_messages(kwargs))
        assert "cez-as" in system_joined
        assert "o2-czech" in system_joined


class TestLazyImport:
    def test_module_imports_without_requests_at_module_load(self, mocker: MockerFixture) -> None:
        import builtins
        import importlib
        import sys

        for mod in list(sys.modules):
            if mod == "bim.commands.doc.shared.classifier":
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
        importlib.import_module("bim.commands.doc.shared.classifier")
