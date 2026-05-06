from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from bim.commands.doc.shared.classifier import ClassifyResult
from bim.commands.doc.shared.extractor import ExtractResult, IncompleteExtraction
from bim.commands.doc.shared.issuers import IssuerRegistry, load_registry
from bim.commands.doc.shared.ocr import OCRResult
from bim.commands.doc.shared.pipeline import IngestOutcome, Pipeline, PipelineServices
from bim.commands.doc.shared.settings_models import (
    ClassifierSettings,
    DocPaths,
    DocSettings,
    OCRSettings,
    ZettelSettings,
)
from bim.commands.doc.shared.state_db import ProcessedRow, StateDB
from bim.commands.doc.shared.zettel_writer import ZettelWriter
from bim.params.doc_ingest import IngestParams
from buvis.pybase.result import CommandResult
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
) -> ClassifyResult:
    return ClassifyResult(
        issuer_slug=issuer_slug,
        issuer_display=issuer_display,
        doc_type=doc_type,
        language="cs",
        confidence=confidence,
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
    if classify_side_effect is not None:
        classify_mock = mocker.patch.object(classifier, "classify", side_effect=classify_side_effect)
    else:
        classify_mock = mocker.patch.object(classifier, "classify", return_value=classify_result)
    if extract_side_effect is not None:
        extract_mock = mocker.patch.object(extractor, "extract", side_effect=extract_side_effect)
    else:
        extract_mock = mocker.patch.object(extractor, "extract", return_value=extract_result)

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


# ----------------------- IngestOutcome -----------------------


class TestIngestOutcome:
    def test_outcome_values_are_filed_triaged_duplicate(self) -> None:
        # IngestOutcome must expose the three string outcomes the pipeline
        # records in CommandResult.metadata["outcome"].
        values = {IngestOutcome.FILED, IngestOutcome.TRIAGED, IngestOutcome.DUPLICATE}
        assert {str(v) for v in values} == {"filed", "triaged", "duplicate"}


# ----------------------- Pipeline scenarios -----------------------


class TestPipeline:
    # --- 1. digital PDF (text layer present, classifier confident, extract OK) ---

    def test_digital_pdf_filed_end_to_end(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        ocr_result = _make_ocr_result(pdf_path=staging_pdf)
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_result=_make_classify_result(),
            extract_result=_make_extract_result(),
        )
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert isinstance(result, CommandResult)
        assert result.success is True
        assert result.metadata["outcome"] == "filed"

        zettel_path = Path(result.metadata["zettel_path"])
        assert zettel_path.exists()
        assert zettel_path.suffix == ".md"
        assert zettel_path.parent == settings.paths.vault_root / "Zettelkasten" / "documents"

        pdf_path = Path(result.metadata["pdf_path"])
        assert pdf_path.exists()
        assert pdf_path.parent == settings.paths.business_root / "cez-as"
        assert pdf_path.suffix == ".pdf"

        # state_db must record the processed row with extraction_method=llm:<model>
        row = state_db.dedup(sha)
        assert row.is_duplicate is True
        assert row.existing_row is not None
        assert row.existing_row.extraction_method == f"llm:{settings.classifier.primary_model}"
        assert row.existing_row.issuer_slug == "cez-as"
        assert row.existing_row.doc_type == "invoice"

        mocks["ocr"].assert_called_once()
        mocks["classify"].assert_called_once()
        mocks["extract"].assert_called_once()

    # --- 2. scanned PDF (full OCR produces a new pdf_path) ---

    def test_scanned_pdf_full_ocr_filed(
        self,
        tmp_path: Path,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        ocr_pdf = _write_pdf(tmp_path / "ocr_output.pdf", b"%PDF-1.4\nocr'd content\n")
        ocr_result = OCRResult(
            ocr_text="OCR'd content from scan",
            pdf_path=ocr_pdf,
            was_redone=False,
            original_backup_path=None,
            mean_confidence=None,
            pages=1,
        )
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_result=_make_classify_result(),
            extract_result=_make_extract_result(),
        )
        params = IngestParams(source="scan", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "filed"
        # Pipeline must move the OCR'd PDF (ocr_result.pdf_path) - the OCR'd
        # one carries the embedded text layer, not the original staged image.
        filed_pdf = Path(result.metadata["pdf_path"])
        assert filed_pdf.exists()
        # OCR temp file should no longer exist at its old location after move.
        assert not ocr_pdf.exists()

    # --- 3. re-OCR low-confidence text layer ---

    def test_redo_ocr_branch_filed_with_backup_preserved(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        backup = tmp_path / "state" / "originals" / "20260506-aaaaaaaa.pdf"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(b"%PDF-1.4\noriginal pre-redo\n")

        ocr_result = OCRResult(
            ocr_text="redone ocr text",
            pdf_path=staging_pdf,
            was_redone=True,
            original_backup_path=backup,
            mean_confidence=None,
            pages=2,
        )
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_result=_make_classify_result(),
            extract_result=_make_extract_result(),
        )
        params = IngestParams(source="email", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "filed"
        # Backup must still exist after the pipeline runs - it's the rollback artifact.
        assert backup.exists()

    # --- 4. dedup hit (sha already in processed table) ---

    def test_dedup_hit_returns_duplicate_without_processing(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        existing = ProcessedRow(
            sha256=sha,
            canonical_filename="20210311083422-cez-as-7102105594.invoice.pdf",
            issuer_slug="cez-as",
            doc_type="invoice",
            processed_at=datetime(2021, 3, 11, 8, 34, 22, tzinfo=timezone.utc),
            extraction_method="llm:qwen2.5:7b-instruct",
        )
        state_db.record_processed(existing)

        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(),
            classify_result=_make_classify_result(),
            extract_result=_make_extract_result(),
        )
        params = IngestParams(source="email", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "duplicate"
        assert result.metadata.get("existing_canonical_filename") == existing.canonical_filename

        # OCR/classify/extract must NOT be called on a dedup hit.
        mocks["ocr"].assert_not_called()
        mocks["classify"].assert_not_called()
        mocks["extract"].assert_not_called()

        # A .duplicate.yml sidecar references the existing canonical entry.
        sidecar = staging_pdf.with_suffix(staging_pdf.suffix + ".duplicate.yml")
        assert sidecar.exists()
        sidecar_text = sidecar.read_text(encoding="utf-8")
        assert existing.canonical_filename in sidecar_text

    # --- 5. triage on classifier confidence below threshold ---

    def test_triage_on_low_classifier_confidence(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(confidence=0.62),  # < 0.85 threshold
            extract_result=_make_extract_result(),
        )
        params = IngestParams(source="email", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "triaged"

        proposal_path = Path(result.metadata["proposal_path"])
        assert proposal_path.exists()
        assert proposal_path.suffix == ".yml"
        assert proposal_path.name.endswith(".proposed.yml")
        proposal_text = proposal_path.read_text(encoding="utf-8")
        # PRD requires approved: false on a freshly written proposal.
        assert "approved: false" in proposal_text
        # Triage reasons should mention the confidence threshold breach.
        assert "confidence" in proposal_text.lower()

        # PDF must be in business_root/_triage/.
        triage_dir = settings.paths.business_root / "_triage"
        assert triage_dir.exists()
        triage_pdfs = list(triage_dir.glob("*.pdf"))
        assert len(triage_pdfs) == 1

        # state_db.processed must NOT have a row (only triaged, not filed).
        dedup = state_db.dedup(sha)
        assert dedup.is_duplicate is False

    # --- 6. triage on extractor IncompleteExtraction (missing required field) ---

    def test_triage_on_extractor_incomplete(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(),
            extract_side_effect=IncompleteExtraction(["missing field date", "missing field amount"]),
        )
        params = IngestParams(source="email", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "triaged"

        proposal_path = Path(result.metadata["proposal_path"])
        assert proposal_path.exists()
        proposal_text = proposal_path.read_text(encoding="utf-8")
        assert "missing field date" in proposal_text
        assert "missing field amount" in proposal_text

    # --- 7. triage on unknown issuer (classifier returned slug not in registry) ---

    def test_triage_on_unknown_issuer(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        # Classifier returns issuer_slug=None (resolve_alias upstream miss).
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(
                issuer_slug=None,
                issuer_display=None,
                confidence=0.95,
            ),
            extract_result=_make_extract_result(),
        )
        params = IngestParams(source="email", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "triaged"

        proposal_path = Path(result.metadata["proposal_path"])
        assert proposal_path.exists()
        proposal_text = proposal_path.read_text(encoding="utf-8").lower()
        # Should include a triage reason mentioning the issuer not being known.
        assert any(
            token in proposal_text for token in ("unknown issuer", "unrecognized issuer", "issuer not in registry")
        )

    # --- 8. issuer-inbox source uses doc_type_only classifier path ---

    def test_issuer_inbox_skips_full_classify_and_pins_issuer(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        # When source is issuer-inbox, the classifier is called doc_type_only=True
        # and the issuer is taken from IngestParams.issuer_slug_hint.
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(
                issuer_slug=None,  # doc_type_only path returns no issuer
                issuer_display=None,
                doc_type="invoice",
                confidence=0.96,
            ),
            extract_result=_make_extract_result(),
        )
        params = IngestParams(
            source="issuer-inbox",
            staging_path=staging_pdf,
            issuer_slug_hint="cez-as",
        )
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "filed"

        # Classifier MUST have been called with doc_type_only=True.
        assert mocks["classify"].call_count == 1
        kwargs = mocks["classify"].call_args.kwargs
        assert kwargs.get("doc_type_only") is True

        # Issuer slug pinned from the hint, not from classifier output.
        pdf_path = Path(result.metadata["pdf_path"])
        assert pdf_path.parent == settings.paths.business_root / "cez-as"

    # --- additional safety net: claim is released on triage so re-runs work ---

    def test_claim_released_on_triage_path(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(confidence=0.30),
            extract_result=_make_extract_result(),
        )
        # Compute sha before run() because triage moves the staging PDF away.
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        params = IngestParams(source="email", staging_path=staging_pdf)
        result = pipeline.run(params)
        assert result.metadata["outcome"] == "triaged"

        # The first claim should have been released so a re-run could re-attempt.
        assert state_db.claim(sha) is True
