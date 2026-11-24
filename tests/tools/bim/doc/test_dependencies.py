"""Wiring tests for the bim doc subsystem factories in bim/dependencies.py."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest
from bim.commands.doc.shared.classifier import Classifier
from bim.commands.doc.shared.extractor import Extractor
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.llm import DocLLMRoute
from bim.commands.doc.shared.ocr import OCRRunner
from bim.commands.doc.shared.pipeline import Pipeline, PipelineServices
from bim.commands.doc.shared.settings_models import ClassifierSettings, DocPaths, DocSettings
from bim.commands.doc.shared.state_db import StateDB
from bim.commands.doc.shared.zettel_writer import ZettelWriter
from bim.dependencies import (
    _load_issuer_registry,
    get_classifier,
    get_extractor,
    get_health_checker,
    get_pipeline,
)
from bim.shared.llm import HttpBackendSettings, LLMConfigError
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository
from pytest_mock import MockerFixture

FIXTURES = Path(__file__).parent / "fixtures" / "issuers"

NAMED_LLM = {
    "fast": HttpBackendSettings(kind="ollama", endpoint="http://fast:11434", model="m-fast"),
    "slow": HttpBackendSettings(kind="llamacpp", endpoint="http://slow:8002", model="m-slow"),
}


def _with_classifier(settings: DocSettings, classifier: ClassifierSettings) -> DocSettings:
    return settings.model_copy(update={"classifier": classifier})


@pytest.fixture
def doc_settings(tmp_path: Path) -> DocSettings:
    issuers_file = tmp_path / "issuers.yml"
    shutil.copy(FIXTURES / "valid.yml", issuers_file)
    paths = DocPaths.model_validate(
        {
            "business_root": str(tmp_path / "Business"),
            "vault_root": str(tmp_path / "Vault"),
            "state_dir": str(tmp_path / "state"),
            "issuers_file": str(issuers_file),
        }
    )
    return DocSettings(paths=paths)


class TestLoadIssuerRegistry:
    def test_returns_registry_only(self, doc_settings: DocSettings) -> None:
        issuers_file = doc_settings.paths.issuers_file
        assert issuers_file is not None
        result = _load_issuer_registry(issuers_file)
        assert isinstance(result, IssuerRegistry)
        assert result.version == 1


class TestGetPipeline:
    def test_wires_all_six_services(self, doc_settings: DocSettings) -> None:
        # ZettelWriter stashes the repo as ``self.repo`` without introspecting
        # in v1; cast lets the test focus on factory wiring rather than a real
        # repo construction (which would require a markdown vault on disk).
        sentinel_repo = cast(ZettelRepository, object())
        pipeline = get_pipeline(doc_settings, sentinel_repo)

        assert isinstance(pipeline, Pipeline)
        services = getattr(pipeline, "_services")
        assert isinstance(services, PipelineServices)
        assert isinstance(services.state_db, StateDB)
        assert isinstance(services.ocr_runner, OCRRunner)
        assert isinstance(services.classifier, Classifier)
        assert isinstance(services.extractor, Extractor)
        assert isinstance(services.registry, IssuerRegistry)
        assert isinstance(services.zettel_writer, ZettelWriter)


class TestGetPipelineLLMRoute:
    @pytest.mark.parametrize("llm", [None, {}], ids=["llm-none", "llm-empty"])
    def test_old_config_without_llm_keeps_original_endpoint_and_models(
        self, doc_settings: DocSettings, llm: dict[str, HttpBackendSettings] | None
    ) -> None:
        pipeline = get_pipeline(doc_settings, cast(ZettelRepository, object()), llm)

        route = getattr(pipeline, "_services").llm_route
        assert isinstance(route, DocLLMRoute)
        assert route.legacy is True
        assert route.primary.backend == "ollama"
        assert route.primary.model == "qwen3:30b-a3b"
        assert route.primary.key == "qwen3:30b-a3b"
        assert route.fallback.backend == "ollama"
        assert route.fallback.model == "qwen3:14b"
        assert route.fallback.key == "qwen3:14b"
        assert list(route.backends) == ["ollama"]
        assert route.backends["ollama"].endpoint == "http://localhost:11434"

    def test_old_custom_config_reaches_the_route_unchanged(self, doc_settings: DocSettings) -> None:
        classifier = ClassifierSettings(
            backend="llamacpp", endpoint="http://gpu:8002", primary_model="a-model", fallback_model="b-model"
        )
        settings = _with_classifier(doc_settings, classifier)

        pipeline = get_pipeline(settings, cast(ZettelRepository, object()))

        route = getattr(pipeline, "_services").llm_route
        assert (route.primary.backend, route.primary.key) == ("llamacpp", "a-model")
        assert (route.fallback.backend, route.fallback.key) == ("llamacpp", "b-model")
        assert route.backends["llamacpp"].kind == "llamacpp"
        assert route.backends["llamacpp"].endpoint == "http://gpu:8002"

    def test_named_config_shares_one_route_and_one_registry(self, doc_settings: DocSettings) -> None:
        settings = _with_classifier(doc_settings, ClassifierSettings(backend="fast", fallback="slow"))

        pipeline = get_pipeline(settings, cast(ZettelRepository, object()), NAMED_LLM)

        services = getattr(pipeline, "_services")
        route = services.llm_route
        assert isinstance(route, DocLLMRoute)
        assert route.legacy is False
        assert (route.primary.key, route.fallback.key) == ("fast", "slow")
        assert dict(route.backends) == NAMED_LLM
        assert getattr(services.classifier, "_route") is route
        assert getattr(services.extractor, "_route") is route
        assert getattr(services.classifier, "_registry") is getattr(services.extractor, "_registry")

    def test_named_config_without_fallback_falls_back_to_the_primary_entry(self, doc_settings: DocSettings) -> None:
        settings = _with_classifier(doc_settings, ClassifierSettings(backend="fast"))

        pipeline = get_pipeline(settings, cast(ZettelRepository, object()), NAMED_LLM)

        route = getattr(pipeline, "_services").llm_route
        assert isinstance(route, DocLLMRoute)
        assert route.legacy is False
        assert route.primary.key == "fast"
        assert route.fallback.key == "fast"

    @pytest.mark.parametrize(
        ("backend", "fallback"),
        [("fas", "slow"), ("fast", "slo")],
        ids=["backend-prefix-of-entry", "fallback-prefix-of-entry"],
    )
    def test_named_config_with_unknown_entry_raises(
        self, doc_settings: DocSettings, backend: str, fallback: str
    ) -> None:
        settings = _with_classifier(doc_settings, ClassifierSettings(backend=backend, fallback=fallback))

        with pytest.raises(LLMConfigError):
            get_pipeline(settings, cast(ZettelRepository, object()), NAMED_LLM)


class TestGetClassifierAndExtractorLLM:
    def test_llm_map_reaches_both_factories(self, doc_settings: DocSettings) -> None:
        settings = _with_classifier(doc_settings, ClassifierSettings(backend="slow", fallback="fast"))

        classifier = get_classifier(settings, NAMED_LLM)
        extractor = get_extractor(settings, NAMED_LLM)

        for service in (classifier, extractor):
            route = getattr(service, "_route")
            assert (route.primary.key, route.fallback.key) == ("slow", "fast")
            assert route.legacy is False
            assert dict(route.backends) == NAMED_LLM

    def test_without_llm_map_factories_stay_legacy(self, doc_settings: DocSettings) -> None:
        for service in (get_classifier(doc_settings), get_extractor(doc_settings)):
            route = getattr(service, "_route")
            assert route.legacy is True
            assert (route.primary.key, route.fallback.key) == ("qwen3:30b-a3b", "qwen3:14b")


class TestGetHealthChecker:
    def test_checker_probes_the_named_llm_entries(self, doc_settings: DocSettings, mocker: MockerFixture) -> None:
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        mocker.patch("bim.commands.doc.shared.health.subprocess.run", return_value=ok)
        replies = {
            "http://fast:11434/api/tags": mocker.Mock(status_code=200, json=lambda: {"models": [{"name": "m-fast"}]}),
            "http://slow:8002/v1/models": mocker.Mock(status_code=200, json=lambda: {"data": []}),
        }
        fake_requests = mocker.MagicMock()
        fake_requests.get.side_effect = lambda url, *args, **kwargs: replies[url]
        mocker.patch.dict("sys.modules", {"requests": fake_requests}, clear=False)
        settings = _with_classifier(doc_settings, ClassifierSettings(backend="fast", fallback="slow"))

        get_health_checker()(settings, NAMED_LLM)

        probed = [call.args[0] for call in fake_requests.get.call_args_list]
        assert probed == ["http://fast:11434/api/tags", "http://slow:8002/v1/models"]
