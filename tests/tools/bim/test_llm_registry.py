from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from bim.shared.llm import (
    Backend,
    BackendError,
    BackendReason,
    ClaudeBackendSettings,
    CommandBackendSettings,
    HttpBackendSettings,
    JsonObject,
    LLMBackendSettings,
    LLMConfigError,
    LLMRegistry,
    LLMRequest,
    build_registry,
)
from bim.shared.llm.base import parse_json_text, require_strict_schema, validate_payload
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

_SETTINGS = TypeAdapter(LLMBackendSettings)


class _Tx(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: str
    currency: str


class _Loose(BaseModel):
    amount: str


class _LooseLine(BaseModel):
    text: str


class _StrictLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


class _InvoiceWithLooseList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[_LooseLine]


class _InvoiceWithLooseUnion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line: _LooseLine | None = None


class _InvoiceWithStrictLines(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[_StrictLine]
    tags: dict[str, str]


class _DocReply(JsonObject):
    pass


class _FakeBackend:
    """Test backend: parses a canned reply through the shared base helpers."""

    def __init__(self, name: str, reply: object, *, unattended_safe: bool = True) -> None:
        self.name = name
        self.unattended_safe = unattended_safe
        self.reply = reply
        self.calls: list[tuple[LLMRequest, type[BaseModel], float, str | None]] = []

    def complete(self, request: LLMRequest, schema: Any, *, timeout: float, model: str | None = None) -> Any:
        self.calls.append((request, schema, timeout, model))
        return validate_payload(schema, parse_json_text(self.reply, backend=self.name), backend=self.name)


def _two_backends() -> tuple[_FakeBackend, _FakeBackend, LLMRegistry]:
    local = _FakeBackend("local", '{"amount": "12.50", "currency": "CZK"}')
    remote = _FakeBackend("remote", '{"amount": "99.00", "currency": "EUR"}')
    return local, remote, LLMRegistry({"local": local, "remote": remote})


class TestRegistrySelection:
    def test_get_returns_the_backend_registered_under_each_name(self) -> None:
        local, remote, registry = _two_backends()

        assert registry.get("local") is local
        assert registry.get("remote") is remote
        assert registry.names() == frozenset({"local", "remote"})

    def test_fake_backends_satisfy_the_backend_protocol(self) -> None:
        local, _, _ = _two_backends()

        assert isinstance(local, Backend)

    def test_invoke_calls_only_the_named_backend_with_its_arguments(self) -> None:
        local, remote, registry = _two_backends()
        request = LLMRequest(prompt="parse this", system="be strict")

        result = registry.invoke("remote", request, _Tx, timeout=7.5, model="qwen3:14b")

        assert result == _Tx(amount="99.00", currency="EUR")
        assert remote.calls == [(request, _Tx, 7.5, "qwen3:14b")]
        assert local.calls == []

    def test_invoke_passes_default_model_none_and_other_timeout(self) -> None:
        local, remote, registry = _two_backends()
        request = LLMRequest(prompt="other")

        result = registry.invoke("local", request, _Tx, timeout=30.0)

        assert result == _Tx(amount="12.50", currency="CZK")
        assert local.calls == [(request, _Tx, 30.0, None)]
        assert remote.calls == []

    def test_unknown_name_lists_configured_names(self) -> None:
        _, _, registry = _two_backends()

        with pytest.raises(LLMConfigError) as exc:
            registry.get("loca")

        assert str(exc.value) == "unknown LLM backend 'loca'; configured: ['local', 'remote']"

    def test_unknown_name_through_invoke_calls_no_backend(self) -> None:
        local, remote, registry = _two_backends()

        with pytest.raises(LLMConfigError, match="unknown LLM backend 'remotes'"):
            registry.invoke("remotes", LLMRequest(prompt="x"), _Tx, timeout=1.0)

        assert local.calls == []
        assert remote.calls == []

    def test_empty_registry_has_no_names_and_rejects_every_name(self) -> None:
        registry = LLMRegistry({})

        assert registry.names() == frozenset()
        with pytest.raises(LLMConfigError) as exc:
            registry.get("local")
        assert str(exc.value) == "unknown LLM backend 'local'; configured: []"

    def test_llm_config_error_is_a_value_error(self) -> None:
        with pytest.raises(ValueError):
            LLMRegistry({}).get("x")


class TestUnattendedRefusal:
    def test_unsafe_backend_is_refused_when_unattended(self) -> None:
        unsafe = _FakeBackend("shell", "{}", unattended_safe=False)
        registry = LLMRegistry({"shell": unsafe})

        with pytest.raises(LLMConfigError) as exc:
            registry.get("shell", unattended=True)

        assert str(exc.value) == (
            "backend 'shell' cannot run unattended: a command backend cannot prove its tools are off; "
            "set llm.shell.unattended: true to accept that risk"
        )

    def test_unsafe_backend_is_returned_when_attended(self) -> None:
        unsafe = _FakeBackend("shell", "{}", unattended_safe=False)
        registry = LLMRegistry({"shell": unsafe})

        assert registry.get("shell") is unsafe
        assert registry.get("shell", unattended=False) is unsafe

    def test_safe_backend_is_returned_when_unattended(self) -> None:
        safe = _FakeBackend("claude", "{}")
        unsafe = _FakeBackend("shell", "{}", unattended_safe=False)
        registry = LLMRegistry({"claude": safe, "shell": unsafe})

        assert registry.get("claude", unattended=True) is safe

    def test_invoke_unattended_on_unsafe_backend_never_calls_it(self) -> None:
        unsafe = _FakeBackend("shell2", '{"amount": "1", "currency": "CZK"}', unattended_safe=False)
        registry = LLMRegistry({"shell2": unsafe})

        with pytest.raises(LLMConfigError, match="set llm.shell2.unattended: true"):
            registry.invoke("shell2", LLMRequest(prompt="x"), _Tx, timeout=1.0, unattended=True)

        assert unsafe.calls == []
        assert registry.invoke("shell2", LLMRequest(prompt="x"), _Tx, timeout=1.0) == _Tx(amount="1", currency="CZK")


class TestRequireStrictSchema:
    def test_rejects_a_model_without_extra_forbid(self) -> None:
        with pytest.raises(LLMConfigError) as exc:
            require_strict_schema(_Loose)

        message = str(exc.value)
        assert message.startswith("schema _Loose allows unexpected keys at ")
        assert message.endswith("; set extra='forbid'")

    def test_accepts_a_strict_model(self) -> None:
        backend = _FakeBackend("local", '{"amount": "3.10", "currency": "USD"}')
        registry = LLMRegistry({"local": backend})

        result = registry.invoke("local", LLMRequest(prompt="x"), _Tx, timeout=1.0)

        assert type(result) is _Tx
        assert result == _Tx(amount="3.10", currency="USD")
        assert len(backend.calls) == 1

    @pytest.mark.parametrize("schema", [_InvoiceWithLooseList, _InvoiceWithLooseUnion])
    def test_rejects_a_strict_parent_with_a_default_extra_child(self, schema: type[BaseModel]) -> None:
        with pytest.raises(LLMConfigError) as exc:
            require_strict_schema(schema)

        message = str(exc.value)
        assert message.startswith(f"schema {schema.__name__} allows unexpected keys at ")
        assert "_LooseLine" in message
        assert message.endswith("; set extra='forbid'")

    def test_accepts_strict_children_in_a_list_and_an_open_str_mapping(self) -> None:
        reply = '{"lines": [{"text": "bread"}, {"text": "milk"}], "tags": {"shop": "tesco", "city": "brno"}}'
        backend = _FakeBackend("local", reply)
        registry = LLMRegistry({"local": backend})

        result = registry.invoke("local", LLMRequest(prompt="x"), _InvoiceWithStrictLines, timeout=1.0)

        assert type(result) is _InvoiceWithStrictLines
        assert result == _InvoiceWithStrictLines(
            lines=[_StrictLine(text="bread"), _StrictLine(text="milk")],
            tags={"shop": "tesco", "city": "brno"},
        )
        assert len(backend.calls) == 1

    @pytest.mark.parametrize("schema", [JsonObject, _DocReply])
    def test_accepts_json_object_and_its_subclass(self, schema: type[BaseModel]) -> None:
        backend = _FakeBackend("doc", '{"issuer_slug": "philips", "pages": [1, 2]}')
        registry = LLMRegistry({"doc": backend})

        result = registry.invoke("doc", LLMRequest(prompt="x"), schema, timeout=1.0)

        assert type(result) is schema
        assert result.root == {"issuer_slug": "philips", "pages": [1, 2]}
        assert len(backend.calls) == 1

    def test_invoke_rejects_a_loose_schema_before_calling_the_backend(self) -> None:
        backend = _FakeBackend("local", '{"amount": "1"}')
        registry = LLMRegistry({"local": backend})

        with pytest.raises(LLMConfigError, match="schema _Loose allows unexpected keys"):
            registry.invoke("local", LLMRequest(prompt="x"), _Loose, timeout=1.0)

        assert backend.calls == []


class TestIndependentSchemas:
    def test_doc_and_tx_schemas_validate_through_one_registry(self) -> None:
        doc = _FakeBackend("doc", '{"issuer_slug": "philips", "confidence": 0.9, "extra": [1, 2]}')
        tx = _FakeBackend("tx", '{"amount": "12.50", "currency": "CZK"}')
        registry = LLMRegistry({"doc": doc, "tx": tx})

        doc_reply = registry.invoke("doc", LLMRequest(prompt="classify"), JsonObject, timeout=5.0)
        tx_reply = registry.invoke("tx", LLMRequest(prompt="extract"), _Tx, timeout=5.0)

        assert isinstance(doc_reply, JsonObject)
        assert doc_reply.root == {"issuer_slug": "philips", "confidence": 0.9, "extra": [1, 2]}
        assert tx_reply == _Tx(amount="12.50", currency="CZK")
        assert doc.calls[0][1] is JsonObject
        assert tx.calls[0][1] is _Tx

    def test_extra_key_in_a_strict_reply_is_a_schema_error(self) -> None:
        tx = _FakeBackend("tx", '{"amount": "12.50", "currency": "CZK", "note": "surprise"}')
        registry = LLMRegistry({"tx": tx})

        with pytest.raises(BackendError) as exc:
            registry.invoke("tx", LLMRequest(prompt="extract"), _Tx, timeout=5.0)

        assert exc.value.reason is BackendReason.SCHEMA
        assert exc.value.backend == "tx"
        assert exc.value.detail.startswith("reply does not match _Tx: ")

    def test_json_object_rejects_a_non_object_reply(self) -> None:
        with pytest.raises(BackendError) as exc:
            validate_payload(JsonObject, [1, 2], backend="doc")

        assert exc.value.reason is BackendReason.SCHEMA
        assert exc.value.detail.startswith("reply does not match JsonObject: ")


class TestBackendSettings:
    def test_parses_each_kind_into_its_settings_type(self) -> None:
        claude = _SETTINGS.validate_python({"kind": "claude", "model": "sonnet"})
        http = _SETTINGS.validate_python({"kind": "llamacpp", "endpoint": "http://localhost:8002/"})
        command = _SETTINGS.validate_python({"kind": "command", "argv": ["llm", "-m", "x"]})

        assert isinstance(claude, ClaudeBackendSettings)
        assert claude.model == "sonnet"
        assert isinstance(http, HttpBackendSettings)
        assert http.endpoint == "http://localhost:8002/"
        assert http.model is None
        assert isinstance(command, CommandBackendSettings)
        assert command.argv == ["llm", "-m", "x"]
        assert command.unattended is False

    @pytest.mark.parametrize("kind", ["ollama", "llamacpp", "openai"])
    def test_every_http_kind_is_accepted(self, kind: str) -> None:
        parsed = _SETTINGS.validate_python({"kind": kind, "endpoint": "http://h:1", "model": "m"})

        assert isinstance(parsed, HttpBackendSettings)
        assert parsed.kind == kind
        assert parsed.model == "m"

    @pytest.mark.parametrize("kind", ["vllm", "claudes", "stub", "fake", "test", ""])
    def test_rejects_unknown_kind_including_any_stub(self, kind: str) -> None:
        with pytest.raises(ValidationError):
            _SETTINGS.validate_python({"kind": kind, "endpoint": "http://h:1", "argv": ["x"]})

    @pytest.mark.parametrize(
        "entry",
        [
            {"kind": "claude", "argv": ["llm"]},
            {"kind": "claude", "endpoint": "http://h:1"},
            {"kind": "ollama", "endpoint": "http://h:1", "argv": ["llm"]},
            {"kind": "command", "argv": ["llm"], "endpoint": "http://h:1"},
            {"kind": "command", "argv": ["llm"], "model": "m"},
        ],
    )
    def test_rejects_a_key_that_belongs_to_another_kind(self, entry: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            _SETTINGS.validate_python(entry)

    @pytest.mark.parametrize("entry", [{"kind": "openai"}, {"kind": "command"}, {"model": "m"}])
    def test_rejects_a_missing_required_key(self, entry: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            _SETTINGS.validate_python(entry)

    @pytest.mark.parametrize("argv", [[], [""], ["llm", ""], ["", "llm"]])
    def test_rejects_empty_argv_and_empty_argv_elements(self, argv: list[str]) -> None:
        with pytest.raises(ValidationError):
            _SETTINGS.validate_python({"kind": "command", "argv": argv})

    def test_command_unattended_opt_in_is_kept(self) -> None:
        parsed = _SETTINGS.validate_python({"kind": "command", "argv": ["llm"], "unattended": True})

        assert isinstance(parsed, CommandBackendSettings)
        assert parsed.unattended is True

    def test_settings_are_frozen(self) -> None:
        parsed = _SETTINGS.validate_python({"kind": "claude"})

        with pytest.raises(ValidationError):
            setattr(parsed, "model", "opus")

    def test_empty_config_builds_an_empty_registry(self) -> None:
        assert build_registry({}).names() == frozenset()


class TestBackendError:
    def test_str_carries_reason_backend_and_detail(self) -> None:
        timeout = BackendError(BackendReason.TIMEOUT, "no reply in 5s", backend="local")
        parse = BackendError("parse", "bad token", backend="remote")

        assert str(timeout) == "[timeout] local: no reply in 5s"
        assert str(parse) == "[parse] remote: bad token"
        assert parse.reason is BackendReason.PARSE
        assert (parse.detail, parse.backend) == ("bad token", "remote")
        assert isinstance(timeout, RuntimeError)

    @pytest.mark.parametrize("reason", ["exit", "schema"])
    def test_known_reason_strings_become_enum_members(self, reason: str) -> None:
        assert BackendError(reason, "d", backend="b").reason is BackendReason(reason)

    @pytest.mark.parametrize("reason", ["timeouts", "TIMEOUT", "", "crash"])
    def test_unknown_reason_raises_value_error(self, reason: str) -> None:
        with pytest.raises(ValueError):
            BackendError(reason, "d", backend="b")


class TestParseJsonText:
    def test_parses_objects_and_arrays(self) -> None:
        assert parse_json_text('{"a": 1, "b": [true, null]}', backend="x") == {"a": 1, "b": [True, None]}
        assert parse_json_text("[1, 2]", backend="x") == [1, 2]
        assert parse_json_text("[]", backend="x") == []

    @pytest.mark.parametrize("text", [None, 42, ["{}"], {"a": 1}])
    def test_non_string_reply_is_a_parse_error(self, text: object) -> None:
        with pytest.raises(BackendError) as exc:
            parse_json_text(text, backend="remote")

        assert exc.value.reason is BackendReason.PARSE
        assert exc.value.backend == "remote"
        assert exc.value.detail.startswith("reply is not valid JSON: ")

    @pytest.mark.parametrize("text", ["", "not json", '{"a": 1', "```json\n{}\n```"])
    def test_invalid_json_is_a_parse_error(self, text: str) -> None:
        with pytest.raises(BackendError) as exc:
            parse_json_text(text, backend="local")

        assert exc.value.reason is BackendReason.PARSE
        assert exc.value.backend == "local"
        assert exc.value.detail.startswith("reply is not valid JSON: ")


class TestLLMRequest:
    def test_as_text_joins_system_and_prompt_with_a_blank_line(self) -> None:
        assert LLMRequest(prompt="extract", system="be strict").as_text() == "be strict\n\nextract"
        assert LLMRequest(prompt="classify", system="you sort docs").as_text() == "you sort docs\n\nclassify"

    def test_as_text_without_system_is_the_prompt(self) -> None:
        assert LLMRequest(prompt="extract").as_text() == "extract"
        assert LLMRequest(prompt="").as_text() == ""

    def test_request_is_frozen(self) -> None:
        request = LLMRequest(prompt="x")

        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(request, "prompt", "y")
