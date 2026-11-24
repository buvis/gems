from __future__ import annotations

import json
import types
from pathlib import Path

import pytest
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.llm import DOC_REQUEST_TIMEOUT_SECONDS
from bim.commands.doc.shared.naming import DOC_TYPES
from bim.commands.doc.shared.rules.models import SourceMetadata
from bim.commands.doc.shared.settings_models import ClassifierSettings
from bim.shared.llm import BackendError, BackendReason
from pytest_mock import MockerFixture

FIXTURES = Path(__file__).parent / "fixtures" / "ocr_text"


def _metadata(source_kind: str = "email", filename: str | None = None) -> SourceMetadata:
    """SourceMetadata stub for classifier tests that don't exercise the prompt's metadata payload."""
    return SourceMetadata(source_kind=source_kind, original_filename=filename)


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


class _MockResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise _HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int = 1) -> list[bytes]:
        return [json.dumps(self._payload).encode()]

    def close(self) -> None:
        pass


def _content_response(content_obj: dict[str, object]) -> _MockResponse:
    return _MockResponse({"message": {"content": json.dumps(content_obj)}})


def _raw_content_response(raw: str) -> _MockResponse:
    return _MockResponse({"message": {"content": raw}})


def _build_fake_requests(mocker: MockerFixture, response: _MockResponse | None = None):
    fake_requests = mocker.MagicMock()
    fake_requests.exceptions = _FakeExceptions("requests.exceptions")
    mocker.patch.dict("sys.modules", {"requests.exceptions": fake_requests.exceptions}, clear=False)
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


def _user_messages(call_kwargs: dict[str, object]) -> list[str]:
    body = call_kwargs["json"]
    assert isinstance(body, dict)
    messages = body["messages"]
    assert isinstance(messages, list)
    return [m["content"] for m in messages if m.get("role") == "user"]


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

        result = Classifier(settings).classify(ocr_text, _metadata(), registry)

        assert result.issuer_slug == "cez-as"
        assert result.issuer_display == "ČEZ a.s."
        assert result.doc_type == "invoice"
        assert result.language == "cs"
        assert result.confidence == 0.94

    def test_unknown_issuer_preserves_guess_with_none_canonical(
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
                    "issuer_slug": "Totally Unknown LLC",
                    "doc_type": "invoice",
                    "language": "cs",
                    "confidence": 0.55,
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Classifier(settings).classify(ocr_text, _metadata(), registry)

        # Canonical fields stay None so the pipeline still triages.
        assert result.issuer_slug is None
        assert result.issuer_display is None
        # ...but the model's raw suggestion is preserved as a slugified guess
        # so triage can pre-fill the proposal instead of leaving it blank.
        assert result.issuer_guess == "totally-unknown-llc"
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
                    # A known alias in the reply must still be ignored in doc-type-only mode.
                    "issuer_slug": "cez",
                    "doc_type": "statement",
                    "language": "cs",
                    "confidence": 0.88,
                }
            ),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Classifier(settings).classify("some text", _metadata(), registry, doc_type_only=True)

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
        assert result.issuer_guess is None
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

        Classifier(settings).classify("text", _metadata(), registry, doc_type_only=False)

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

        Classifier(settings).classify("text", _metadata(), registry)

        args, kwargs = fake_requests.post.call_args
        url = args[0] if args else kwargs.get("url")
        assert url == f"{settings.endpoint.rstrip('/')}/api/chat"
        assert kwargs["timeout"] == DOC_REQUEST_TIMEOUT_SECONDS

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

        with pytest.raises(ClassifierError) as exc_info:
            Classifier(settings).classify("text", _metadata(), registry)
        assert str(exc_info.value).startswith("Could not parse classifier JSON response: ")
        assert exc_info.value.transient is False

    def test_non_object_json_reply_raises_non_transient_classifier_error(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier, ClassifierError

        fake_requests = _build_fake_requests(mocker, _raw_content_response('["cez", "invoice"]'))
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(ClassifierError) as exc_info:
            Classifier(settings).classify("text", _metadata(), registry)
        assert str(exc_info.value) == "classifier response is not a JSON object"
        assert exc_info.value.transient is False

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

        with pytest.raises(ClassifierError) as exc_info:
            Classifier(settings).classify("text", _metadata(), registry)
        assert str(exc_info.value).startswith(f"HTTP error calling {settings.backend}: ")
        assert exc_info.value.transient is True

    def test_timeout_propagates_unwrapped(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(mocker)
        fake_requests.post.side_effect = _Timeout("read timeout")
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        with pytest.raises(BackendError) as exc_info:
            Classifier(settings).classify("text", _metadata(), registry)
        assert exc_info.value.reason == BackendReason.TIMEOUT

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
            Classifier(settings).classify("text", _metadata(), registry)
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
            Classifier(settings).classify("text", _metadata(), registry)
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

        Classifier(settings).classify("text", _metadata(), registry, doc_type_only=False)

        _, kwargs = fake_requests.post.call_args
        system_joined = "\n".join(_system_messages(kwargs))
        assert "cez-as" in system_joined
        assert "o2-czech" in system_joined
        for display_or_alias in ("ČEZ a.s.", "O2 Czech Republic a.s.", "ČEZ Prodej", "cez.cz", "o2.cz"):
            assert display_or_alias in system_joined

    def test_user_prompt_carries_source_metadata_except_in_doc_type_only_mode(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(
            mocker,
            _content_response({"issuer_slug": "cez", "doc_type": "invoice", "language": "cs", "confidence": 0.9}),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)
        metadata = SourceMetadata(source_kind="email", original_filename="x.pdf", email_subject="Invoice April")

        Classifier(settings).classify("text", metadata, registry)
        Classifier(settings).classify("text", metadata, registry, doc_type_only=True)

        full_call, doc_type_only_call = fake_requests.post.call_args_list
        full_user = "\n".join(_user_messages(full_call.kwargs))
        assert "x.pdf" in full_user
        assert "Invoice April" in full_user
        doc_type_only_user = "\n".join(_user_messages(doc_type_only_call.kwargs))
        assert "x.pdf" not in doc_type_only_user
        assert "Invoice April" not in doc_type_only_user

    def test_classify_with_model_posts_the_supplied_fallback_model(
        self,
        settings: ClassifierSettings,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import Classifier

        fake_requests = _build_fake_requests(
            mocker,
            _content_response({"issuer_slug": "o2", "doc_type": "statement", "language": "cs", "confidence": 0.8}),
        )
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)

        result = Classifier(settings).classify_with_model("text", _metadata(), registry, model=settings.fallback_model)

        assert fake_requests.post.call_count == 1
        body = fake_requests.post.call_args.kwargs["json"]
        assert body["model"] == settings.fallback_model
        assert body["model"] != settings.primary_model
        assert result.issuer_slug == "o2-czech"


class TestLazyImport:
    def test_module_imports_without_requests_at_module_load(self, mocker: MockerFixture) -> None:
        import builtins
        import importlib
        import sys

        # Save original so we can restore after; otherwise the reloaded
        # module's Classifier class diverges from the one imported at the top
        # of test_dependencies.py, breaking isinstance() checks later.
        original_module = sys.modules.get("bim.commands.doc.shared.classifier")

        try:
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
        finally:
            if original_module is not None:
                sys.modules["bim.commands.doc.shared.classifier"] = original_module
