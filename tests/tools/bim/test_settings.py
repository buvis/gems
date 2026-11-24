from __future__ import annotations

from pathlib import Path

import bim
import pytest
import yaml
from bim.commands.doc.shared.llm import DocLLMTarget, resolve_doc_route
from bim.settings import BimSettings
from bim.shared.llm import ClaudeBackendSettings, CommandBackendSettings, HttpBackendSettings
from pydantic import ValidationError

_LLM_CONFIG = {
    "smart": {"kind": "claude", "model": "opus"},
    "local": {"kind": "llamacpp", "endpoint": "http://localhost:8002/"},
    "cli": {"kind": "command", "argv": ["codex", "exec"], "unattended": True},
}


def _assert_target(target: DocLLMTarget, backend: str, model: str | None, key: str) -> None:
    # Field by field: DocLLMTarget.__eq__ belongs to the type under test.
    assert type(target) is DocLLMTarget
    assert (target.backend, target.model, target.key) == (backend, model, key)


@pytest.fixture
def doc_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return {"business_root": str(tmp_path / "Business"), "vault_root": str(tmp_path / "Vault")}


class TestBimDefaultVaultFolder:
    def test_default_note_directory_is_notes_folder(self) -> None:
        assert BimSettings.model_fields["path_zettelkasten"].default == "~/bim/notes/"

    def test_default_archive_directory_is_local_reference_archive(self) -> None:
        assert BimSettings.model_fields["path_archive"].default == "~/Documents/reference/40-archives/"

    def test_settings_path_projects_default(self) -> None:
        assert BimSettings.model_fields["path_projects"].default == "~/Documents/reference/10-projects/"

    def test_settings_path_daily_and_articles_defaults(self) -> None:
        assert BimSettings.model_fields["path_daily"].default == "~/bim/notes/calendar/daily/"
        assert BimSettings.model_fields["path_articles"].default == "~/Documents/reference/40-archives/articles/"

    def test_contacts_query_reads_notes_folder(self) -> None:
        contacts = Path(bim.__file__).parent / "commands" / "query" / "contacts.yaml"
        source = yaml.safe_load(contacts.read_text(encoding="utf-8"))["source"]
        assert source["directory"] == "~/bim/notes/contact"


class TestBimLLMMap:
    def test_llm_map_defaults_to_empty(self) -> None:
        assert BimSettings.model_validate({}).llm == {}

    def test_llm_map_loads_one_entry_per_kind(self) -> None:
        settings = BimSettings.model_validate({"llm": _LLM_CONFIG})

        assert settings.llm == {
            "smart": ClaudeBackendSettings(kind="claude", model="opus"),
            "local": HttpBackendSettings(kind="llamacpp", endpoint="http://localhost:8002/"),
            "cli": CommandBackendSettings(kind="command", argv=["codex", "exec"], unattended=True),
        }

    def test_named_doc_backends_load(self, doc_paths: dict[str, str]) -> None:
        doc = {"paths": doc_paths, "classifier": {"backend": "smart", "fallback": "local"}}

        settings = BimSettings.model_validate({"llm": _LLM_CONFIG, "doc": doc})

        assert settings.doc is not None
        route = resolve_doc_route(settings.doc.classifier, settings.llm)
        assert route.primary == DocLLMTarget(backend="smart", model=None, key="smart")
        assert route.fallback == DocLLMTarget(backend="local", model=None, key="local")
        _assert_target(route.primary, "smart", None, "smart")
        _assert_target(route.fallback, "local", None, "local")

    def test_bad_doc_backend_fails_load(self, doc_paths: dict[str, str]) -> None:
        doc = {"paths": doc_paths, "classifier": {"backend": "vllm"}}

        with pytest.raises(ValidationError, match="'vllm' is neither an llm entry"):
            BimSettings.model_validate({"llm": _LLM_CONFIG, "doc": doc})

    def test_bad_doc_backend_fails_load_without_an_llm_map(self, doc_paths: dict[str, str]) -> None:
        doc = {"paths": doc_paths, "classifier": {"backend": "vllm"}}

        with pytest.raises(ValidationError, match="'vllm' is neither an llm entry"):
            BimSettings.model_validate({"doc": doc})

    def test_legacy_doc_backend_with_a_fallback_fails_load(self, doc_paths: dict[str, str]) -> None:
        doc = {"paths": doc_paths, "classifier": {"backend": "ollama", "fallback": "fast"}}
        llm = {"fast": {"kind": "ollama", "endpoint": "http://gpu-box:11434"}}

        with pytest.raises(ValidationError, match="doc.classifier.fallback needs doc.classifier.backend"):
            BimSettings.model_validate({"llm": llm, "doc": doc})

    def test_doc_backend_loads_once_the_llm_map_names_it(self, doc_paths: dict[str, str]) -> None:
        doc = {"paths": doc_paths, "classifier": {"backend": "vllm"}}
        llm = {"vllm": {"kind": "openai", "endpoint": "http://localhost:8000/v1"}}

        settings = BimSettings.model_validate({"llm": llm, "doc": doc})

        assert settings.doc is not None
        assert settings.doc.classifier.backend == "vllm"

    def test_unknown_doc_fallback_fails_load(self, doc_paths: dict[str, str]) -> None:
        doc = {"paths": doc_paths, "classifier": {"backend": "smart", "fallback": "remote"}}

        with pytest.raises(ValidationError, match="doc.classifier.fallback 'remote' is not an llm entry"):
            BimSettings.model_validate({"llm": _LLM_CONFIG, "doc": doc})

    def test_doc_backends_are_not_checked_without_a_doc_section(self) -> None:
        settings = BimSettings.model_validate({"llm": {}})

        assert settings.doc is None

    def test_legacy_doc_section_without_llm_keeps_its_endpoint_and_models(self, doc_paths: dict[str, str]) -> None:
        classifier = {
            "backend": "llamacpp",
            "endpoint": "http://localhost:8002/",
            "primary_model": "gemma-27b",
            "fallback_model": "gemma-4b",
        }

        settings = BimSettings.model_validate({"doc": {"paths": doc_paths, "classifier": classifier}})

        assert settings.llm == {}
        assert settings.doc is not None
        route = resolve_doc_route(settings.doc.classifier, settings.llm)
        assert route.legacy is True
        assert route.primary == DocLLMTarget(backend="llamacpp", model="gemma-27b", key="gemma-27b")
        assert route.fallback == DocLLMTarget(backend="llamacpp", model="gemma-4b", key="gemma-4b")
        _assert_target(route.primary, "llamacpp", "gemma-27b", "gemma-27b")
        _assert_target(route.fallback, "llamacpp", "gemma-4b", "gemma-4b")
        assert dict(route.backends) == {
            "llamacpp": HttpBackendSettings(kind="llamacpp", endpoint="http://localhost:8002/")
        }
