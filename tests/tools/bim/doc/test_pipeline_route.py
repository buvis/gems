"""Pipeline tests for the doc LLM route: retry keys and the stored extraction_method."""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import pytest
from bim.commands.doc.shared.classifier import ClassifierError
from bim.commands.doc.shared.extractor import IncompleteExtraction
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.llm import DocLLMRoute, resolve_doc_route
from bim.commands.doc.shared.pipeline import Pipeline
from bim.commands.doc.shared.settings_models import ClassifierSettings, DocSettings
from bim.commands.doc.shared.state_db import StateDB
from bim.params.doc_ingest import IngestParams
from bim.shared.llm import HttpBackendSettings
from pytest_mock import MockerFixture

from . import pipeline_helpers
from .pipeline_helpers import _build_pipeline, _make_classify_result, _make_extract_result, _make_ocr_result

settings = pipeline_helpers.settings
registry = pipeline_helpers.registry
state_db = pipeline_helpers.state_db
staging_pdf = pipeline_helpers.staging_pdf


def _named_route(primary: str, fallback: str) -> DocLLMRoute:
    llm = {
        primary: HttpBackendSettings(kind="ollama", endpoint="http://primary:11434", model="m-primary"),
        fallback: HttpBackendSettings(kind="llamacpp", endpoint="http://fallback:8002", model="m-fallback"),
    }
    return resolve_doc_route(ClassifierSettings(backend=primary, fallback=fallback), llm)


def _run_with_fallback(
    settings: DocSettings,
    registry: IssuerRegistry,
    state_db: StateDB,
    staging_pdf: Path,
    mocker: MockerFixture,
    route: DocLLMRoute | None,
) -> tuple[list[str], list[str], str]:
    """Fail each LLM stage 1 + max_retries (2) times so it falls back once.

    Returns the classify keys, the extract keys and the stored extraction_method.
    """
    pipeline, mocks = _build_pipeline(
        settings,
        registry,
        state_db,
        mocker,
        ocr_result=_make_ocr_result(pdf_path=staging_pdf),
        classify_side_effect=[ClassifierError(f"t{n}") for n in range(3)] + [_make_classify_result()],
        extract_side_effect=[IncompleteExtraction([f"HTTP error: t{n}"], transient=True) for n in range(3)]
        + [_make_extract_result()],
    )
    if route is not None:
        services = dataclasses.replace(getattr(pipeline, "_services"), llm_route=route)
        pipeline = Pipeline(settings, services)
    sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()

    result = pipeline.run(IngestParams(source="download", staging_path=staging_pdf))

    assert result.metadata["outcome"] == "filed"
    row = state_db.dedup(sha).existing_row
    assert row is not None
    classify_keys = [call.kwargs.get("model") for call in mocks["classify"].call_args_list]
    extract_keys = [call.kwargs.get("model") for call in mocks["extract"].call_args_list]
    return classify_keys, extract_keys, row.extraction_method


class TestNamedRoute:
    @pytest.mark.parametrize(
        ("primary", "fallback"),
        [("fast", "slow"), ("alpha", "alpha-big")],
        ids=["fast-slow", "fallback-shares-primary-prefix"],
    )
    def test_retry_keys_and_extraction_method_come_from_the_route(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
        primary: str,
        fallback: str,
    ) -> None:
        # settings.classifier is legacy (qwen2.5 models); the injected route must win.
        classify_keys, extract_keys, method = _run_with_fallback(
            settings, registry, state_db, staging_pdf, mocker, _named_route(primary, fallback)
        )

        assert classify_keys == [primary, primary, primary, fallback]
        assert extract_keys == [primary, primary, primary, fallback]
        assert method == f"llm:{primary}"


class TestLegacyRoute:
    @pytest.mark.parametrize(
        ("classifier", "primary", "fallback"),
        [
            (None, "qwen2.5:7b-instruct", "qwen2.5:14b-instruct"),
            (ClassifierSettings(), "qwen3:30b-a3b", "qwen3:14b"),
        ],
        ids=["helper-models", "default-models"],
    )
    def test_without_route_keys_stay_the_configured_models(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
        classifier: ClassifierSettings | None,
        primary: str,
        fallback: str,
    ) -> None:
        if classifier is not None:
            settings = settings.model_copy(update={"classifier": classifier})

        classify_keys, extract_keys, method = _run_with_fallback(
            settings, registry, state_db, staging_pdf, mocker, None
        )

        assert classify_keys == [primary, primary, primary, fallback]
        assert extract_keys == [primary, primary, primary, fallback]
        assert method == f"llm:{primary}"
