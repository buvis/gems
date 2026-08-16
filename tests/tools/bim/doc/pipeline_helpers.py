"""Shared fixtures and setup helpers for the pipeline test modules.

``test_pipeline.py`` and ``test_pipeline_claims.py`` both build a mocked
``Pipeline`` around the same settings/registry/state_db/staging_pdf fixtures;
kept here once so neither file duplicates the scaffolding.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from bim.commands.doc.shared.classifier import ClassifyResult
from bim.commands.doc.shared.extractor import ExtractResult
from bim.commands.doc.shared.issuers import IssuerRegistry, load_registry
from bim.commands.doc.shared.ocr import OCRResult
from bim.commands.doc.shared.pipeline import Pipeline, PipelineServices
from bim.commands.doc.shared.settings_models import (
    ClassifierSettings,
    DocPaths,
    DocSettings,
    OCRSettings,
    ZettelSettings,
)
from bim.commands.doc.shared.state_db import StateDB
from bim.commands.doc.shared.zettel_writer import ZettelWriter
from pytest_mock import MockerFixture

FIXTURES = Path(__file__).parent / "fixtures"


# ----------------------- helpers -----------------------


def _make_settings(tmp_path: Path, *, triage_threshold: float = 0.85) -> DocSettings:
    paths = DocPaths.model_validate(
        {
            "business_root": str(tmp_path / "Business"),
            "vault_root": str(tmp_path / "Vault"),
            "vault_documents_subdir": "Zettelkasten/documents",
            "state_dir": str(tmp_path / "state"),
        }
    )
    classifier = ClassifierSettings(
        backend="ollama",
        endpoint="http://localhost:11434",
        primary_model="qwen2.5:7b-instruct",
        fallback_model="qwen2.5:14b-instruct",
        triage_threshold=triage_threshold,
        max_retries=2,
    )
    return DocSettings(
        paths=paths,
        ocr=OCRSettings(),
        classifier=classifier,
        zettel=ZettelSettings(),
    )


def _make_registry() -> IssuerRegistry:
    return load_registry(FIXTURES / "issuers" / "with_aliases.yml")


def _write_pdf(path: Path, content: bytes = b"%PDF-1.4\nfake pdf bytes\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _make_ocr_result(text: str = "ČEZ a.s.\nFaktura č. 7102105594\n", pdf_path: Path | None = None) -> OCRResult:
    return OCRResult(
        ocr_text=text,
        pdf_path=pdf_path or Path("/tmp/unused.pdf"),
        was_redone=False,
        original_backup_path=None,
        mean_confidence=0.95,
        pages=2,
    )


def _make_classify_result(
    *,
    issuer_slug: str | None = "cez-as",
    issuer_display: str | None = "ČEZ a.s.",
    doc_type: str = "invoice",
    confidence: float = 0.95,
    issuer_guess: str | None = None,
) -> ClassifyResult:
    return ClassifyResult(
        issuer_slug=issuer_slug,
        issuer_display=issuer_display,
        doc_type=doc_type,
        language="cs",
        confidence=confidence,
        issuer_guess=issuer_guess,
    )


def _make_extract_result(
    *,
    doc_type: str = "invoice",
    number: str | None = "7102105594",
    date_value: date | None = date(2021, 3, 11),
    amount: float | None = 4218.0,
    currency: str | None = "CZK",
) -> ExtractResult:
    return ExtractResult(
        doc_type=doc_type,
        number=number,
        date=date_value,
        amount=amount,
        currency=currency,
    )


def _build_pipeline(
    settings: DocSettings,
    registry: IssuerRegistry,
    state_db: StateDB,
    mocker: MockerFixture,
    *,
    ocr_result: OCRResult | None = None,
    classify_result: ClassifyResult | None = None,
    classify_side_effect: Any = None,
    extract_result: ExtractResult | None = None,
    extract_side_effect: Any = None,
) -> tuple[Pipeline, dict[str, Any]]:
    """Build a Pipeline with the boundary services mocked at class level."""
    from bim.commands.doc.shared.classifier import Classifier
    from bim.commands.doc.shared.extractor import Extractor
    from bim.commands.doc.shared.ocr import OCRRunner

    ocr_runner = OCRRunner(settings=settings, state_dir=settings.paths.state_dir)
    classifier = Classifier(settings.classifier)
    extractor = Extractor(settings.classifier)
    zettel_writer = ZettelWriter(
        repo=None,
        vault_root=settings.paths.vault_root,
        vault_documents_subdir=settings.paths.vault_documents_subdir,
    )

    ocr_mock = mocker.patch.object(ocr_runner, "run", return_value=ocr_result)
    # Pipeline now calls classify_with_model via the retry helper. Mock the
    # model-substituting variant; the legacy ``classify`` shim forwards to it.
    if classify_side_effect is not None:
        classify_mock = mocker.patch.object(classifier, "classify_with_model", side_effect=classify_side_effect)
    else:
        classify_mock = mocker.patch.object(classifier, "classify_with_model", return_value=classify_result)
    # Pipeline now calls extract_with_model via the retry helper. Mock the
    # model-substituting variant; the legacy ``extract`` shim forwards to it.
    if extract_side_effect is not None:
        extract_mock = mocker.patch.object(extractor, "extract_with_model", side_effect=extract_side_effect)
    else:
        extract_mock = mocker.patch.object(extractor, "extract_with_model", return_value=extract_result)

    services = PipelineServices(
        state_db=state_db,
        ocr_runner=ocr_runner,
        classifier=classifier,
        extractor=extractor,
        registry=registry,
        zettel_writer=zettel_writer,
    )
    pipeline = Pipeline(settings, services)
    return pipeline, {"ocr": ocr_mock, "classify": classify_mock, "extract": extract_mock}


@pytest.fixture
def settings(tmp_path: Path) -> DocSettings:
    return _make_settings(tmp_path)


@pytest.fixture
def registry() -> IssuerRegistry:
    return _make_registry()


@pytest.fixture
def state_db(tmp_path: Path) -> StateDB:
    db_path = tmp_path / "state" / "state.db"
    return StateDB.open(db_path)


@pytest.fixture
def staging_pdf(tmp_path: Path) -> Path:
    return _write_pdf(tmp_path / "staging" / "input.pdf")
