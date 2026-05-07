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

    def test_unknown_issuer_guess_prefilled_in_proposal(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        # Classifier returns no canonical match but a slugified guess. The
        # proposal should pre-fill the issuer slug from that guess so the
        # human reviewer has something to react to instead of a blank field;
        # display_name and register_issuer stay empty/false, gating actual
        # registration behind explicit human confirmation.
        import yaml

        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(
                issuer_slug=None,
                issuer_display=None,
                issuer_guess="totally-unknown-llc",
                confidence=0.55,
            ),
            extract_result=_make_extract_result(),
        )
        params = IngestParams(source="email", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "triaged"

        proposal_path = Path(result.metadata["proposal_path"])
        proposal_data = yaml.safe_load(proposal_path.read_text(encoding="utf-8"))

        assert proposal_data["approved"] is False
        assert proposal_data["register_issuer"] is False
        assert proposal_data["issuer"]["slug"] == "totally-unknown-llc"
        assert proposal_data["issuer"]["display_name"] == ""
        # Triage filename also uses the guess so it's recognisable on disk.
        assert "totally-unknown-llc" in proposal_path.name
        # Reason names the guess so the user understands what the model proposed.
        assert any("totally-unknown-llc" in r for r in proposal_data["triage_reasons"])

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

    def test_filename_collision_increments_timestamp(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """Spec §11 row 11: pre-move check must avoid silently overwriting an existing file."""
        # Pre-create a colliding canonical PDF in business_root so the pipeline
        # has to walk forward in seconds to find a free slot.
        existing_canonical = settings.paths.business_root / "cez-as" / "20210311000000-cez-as-7102105594.invoice.pdf"
        existing_canonical.parent.mkdir(parents=True, exist_ok=True)
        existing_bytes = b"%PDF-1.4\nfirst-arrival\n"
        existing_canonical.write_bytes(existing_bytes)

        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(),
            extract_result=_make_extract_result(),
        )
        params = IngestParams(source="email", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "filed"

        filed_pdf = Path(result.metadata["pdf_path"])
        # The new file MUST NOT have overwritten the pre-existing one.
        assert filed_pdf != existing_canonical
        assert existing_canonical.exists()
        assert existing_canonical.read_bytes() == existing_bytes
        # The new filename should differ in the seconds portion of the timestamp.
        assert filed_pdf.name.startswith("20210311000001-cez-as-7102105594.invoice")

    def test_claim_released_on_filed_path(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """Successful filing must remove the claim row to avoid unbounded growth."""
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(),
            extract_result=_make_extract_result(),
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)
        assert result.metadata["outcome"] == "filed"

        # No claim row should remain - the processed row prevents re-ingestion;
        # the claim row was just an in-flight reservation. release_claim returns
        # False if there was no claim row to remove.
        assert state_db.release_claim(sha) is False


class _RecordingProgressReporter:
    """Test double that records ``stage()`` call order without UI side effects."""

    def __init__(self) -> None:
        self.stages: list[str] = []

    def stage(self, message: str) -> None:
        self.stages.append(message)

    def __enter__(self) -> _RecordingProgressReporter:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        return None


class TestPipelineProgressReporting:
    """Pipeline.run calls reporter.stage() before each slow boundary call.

    The CLI's ``SpinnerProgressReporter`` updates a Rich spinner label from
    these stage messages; the pipeline only owns the order and labels.
    """

    def test_filed_path_reports_ocr_then_classify_then_extract(
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
            extract_result=_make_extract_result(),
        )
        reporter = _RecordingProgressReporter()
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params, reporter=reporter)

        assert result.metadata["outcome"] == "filed"
        # Order matters - the spinner label progresses with the slow call in flight.
        assert reporter.stages == ["running OCR", "classifying document", "extracting fields"]

    def test_triage_path_stops_reporting_at_classify_when_extract_skipped(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        # Low-confidence classify result short-circuits to triage before extract.
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(confidence=0.10),
        )
        reporter = _RecordingProgressReporter()
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params, reporter=reporter)

        assert result.metadata["outcome"] == "triaged"
        # Pipeline reports OCR + classify before deciding to triage; extract
        # never runs, so it must not appear in the recorded stages.
        assert reporter.stages == ["running OCR", "classifying document"]

    def test_default_reporter_is_silent_no_op(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        # Existing call sites (and every other pipeline test in this file)
        # invoke ``pipeline.run(params)`` with no reporter. That path must
        # keep working - the default no-op reporter must not raise.
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(),
            extract_result=_make_extract_result(),
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)
        assert result.success is True
        assert result.metadata["outcome"] == "filed"


class TestExceptionContextPreserved:
    """Pipeline.run outer except records exception type+repr in metadata."""

    def test_unhandled_exception_records_structured_context(
        self,
        settings: DocSettings,
        state_db: StateDB,
        staging_pdf: Path,
        registry: IssuerRegistry,
        mocker: MockerFixture,
    ) -> None:
        # OCR runner raises an unexpected error after claim succeeds; the
        # outer except in Pipeline.run must surface exception type/repr.
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=None,
        )
        # Patch the OCR runner to raise instead of returning.
        mocker.patch.object(
            pipeline._services.ocr_runner,
            "run",
            side_effect=RuntimeError("boom from ocr"),
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is False
        assert "pipeline failed" in (result.error or "")
        assert result.metadata.get("stage") == "post-claim"
        assert result.metadata.get("exception_type") == "RuntimeError"
        assert "boom from ocr" in (result.metadata.get("exception_repr") or "")


class TestRetryLLMCall:
    """Standalone tests for the _retry_llm_call helper used by classifier/extractor wiring."""

    def _make_func_from_seq(self, side_effects: list[object]) -> tuple[object, list[str]]:
        """Returns (func, calls_log) where func pops the next side effect on each call.

        Each item is either a return value (returned) or an Exception instance (raised).
        ``calls_log`` records the model name passed to each invocation.
        """
        calls: list[str] = []
        seq = list(side_effects)

        def func(model: str) -> object:
            calls.append(model)
            item = seq.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        return func, calls

    def test_succeeds_first_try(self) -> None:
        from bim.commands.doc.shared.pipeline import _retry_llm_call

        func, calls = self._make_func_from_seq(["ok"])
        result = _retry_llm_call(
            func=func,
            primary_model="primary",
            fallback_model="fallback",
            max_retries=2,
            is_transient=lambda exc: True,
        )
        assert result == "ok"
        assert calls == ["primary"]

    def test_retries_then_succeeds(self) -> None:
        from bim.commands.doc.shared.pipeline import _retry_llm_call

        func, calls = self._make_func_from_seq([RuntimeError("transient"), "ok"])
        result = _retry_llm_call(
            func=func,
            primary_model="primary",
            fallback_model="fallback",
            max_retries=2,
            is_transient=lambda exc: True,
        )
        assert result == "ok"
        assert calls == ["primary", "primary"]

    def test_exhausts_primary_then_fallback_succeeds(self) -> None:
        from bim.commands.doc.shared.pipeline import _retry_llm_call

        func, calls = self._make_func_from_seq([RuntimeError("t1"), RuntimeError("t2"), RuntimeError("t3"), "ok"])
        result = _retry_llm_call(
            func=func,
            primary_model="primary",
            fallback_model="fallback",
            max_retries=2,
            is_transient=lambda exc: True,
        )
        assert result == "ok"
        assert calls == ["primary", "primary", "primary", "fallback"]

    def test_exhausts_primary_and_fallback_fails(self) -> None:
        from bim.commands.doc.shared.pipeline import _retry_llm_call

        func, calls = self._make_func_from_seq(
            [
                RuntimeError("t1"),
                RuntimeError("t2"),
                RuntimeError("t3"),
                RuntimeError("fallback failure"),
            ]
        )
        with pytest.raises(RuntimeError, match="fallback failure"):
            _retry_llm_call(
                func=func,
                primary_model="primary",
                fallback_model="fallback",
                max_retries=2,
                is_transient=lambda exc: True,
            )
        assert calls == ["primary", "primary", "primary", "fallback"]

    def test_non_transient_raises_without_retry(self) -> None:
        from bim.commands.doc.shared.pipeline import _retry_llm_call

        func, calls = self._make_func_from_seq([ValueError("semantic failure"), "should-not-reach"])
        with pytest.raises(ValueError, match="semantic"):
            _retry_llm_call(
                func=func,
                primary_model="primary",
                fallback_model="fallback",
                max_retries=2,
                is_transient=lambda exc: False,
            )
        assert calls == ["primary"]


class TestClassifierRetry:
    """Integration tests for classifier retry semantics through the pipeline."""

    def test_retry_then_succeed(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import ClassifierError

        # First call raises ClassifierError (transient HTTP), second succeeds.
        ocr_result = _make_ocr_result(pdf_path=staging_pdf)
        side_effects = [ClassifierError("transient"), _make_classify_result()]
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_side_effect=side_effects,
            extract_result=_make_extract_result(),
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "filed"
        # Both calls used the primary model.
        models = [call.kwargs.get("model") for call in mocks["classify"].call_args_list]
        assert models == ["qwen2.5:7b-instruct", "qwen2.5:7b-instruct"]

    def test_exhaust_primary_then_fallback_succeeds(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import ClassifierError

        # max_retries=2 means 1 + 2 = 3 primary attempts, then 1 fallback attempt.
        side_effects = [
            ClassifierError("t1"),
            ClassifierError("t2"),
            ClassifierError("t3"),
            _make_classify_result(),
        ]
        ocr_result = _make_ocr_result(pdf_path=staging_pdf)
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_side_effect=side_effects,
            extract_result=_make_extract_result(),
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "filed"
        models = [call.kwargs.get("model") for call in mocks["classify"].call_args_list]
        assert models == [
            "qwen2.5:7b-instruct",
            "qwen2.5:7b-instruct",
            "qwen2.5:7b-instruct",
            "qwen2.5:14b-instruct",
        ]

    def test_exhaust_primary_and_fallback_triages(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        from bim.commands.doc.shared.classifier import ClassifierError

        side_effects = [
            ClassifierError("t1"),
            ClassifierError("t2"),
            ClassifierError("t3"),
            ClassifierError("fallback fails"),
        ]
        ocr_result = _make_ocr_result(pdf_path=staging_pdf)
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_side_effect=side_effects,
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "triaged"
        reasons = result.metadata["triage_reasons"]
        assert any("classifier error" in r for r in reasons)

    def test_non_transient_classifier_error_short_circuits(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """A semantic ClassifierError (parse / missing-field) must NOT consume
        the retry budget — the pipeline routes straight to triage on the first
        attempt. Without this short-circuit, un-fixable model output would
        burn 1 + max_retries primary attempts plus the fallback attempt.
        """
        from bim.commands.doc.shared.classifier import ClassifierError

        # One single-element list: if the predicate were wrong (transient=True
        # treated as retryable), a second attempt would raise StopIteration.
        side_effects = [ClassifierError("missing field 'doc_type'", transient=False)]
        ocr_result = _make_ocr_result(pdf_path=staging_pdf)
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_side_effect=side_effects,
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "triaged"
        # Exactly one classifier call — no retry, no fallback.
        assert mocks["classify"].call_count == 1
        reasons = result.metadata["triage_reasons"]
        assert any("classifier error" in r for r in reasons)


class TestExtractorRetry:
    """Integration tests for extractor retry semantics through the pipeline."""

    def test_transient_retry_then_succeed(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        ocr_result = _make_ocr_result(pdf_path=staging_pdf)
        side_effects = [
            IncompleteExtraction(["HTTP error: refused"], transient=True),
            _make_extract_result(),
        ]
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_result=_make_classify_result(),
            extract_side_effect=side_effects,
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "filed"
        models = [call.kwargs.get("model") for call in mocks["extract"].call_args_list]
        assert models == ["qwen2.5:7b-instruct", "qwen2.5:7b-instruct"]

    def test_transient_exhaust_then_fallback_succeeds(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        ocr_result = _make_ocr_result(pdf_path=staging_pdf)
        side_effects = [
            IncompleteExtraction(["HTTP error: t1"], transient=True),
            IncompleteExtraction(["HTTP error: t2"], transient=True),
            IncompleteExtraction(["HTTP error: t3"], transient=True),
            _make_extract_result(),
        ]
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_result=_make_classify_result(),
            extract_side_effect=side_effects,
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "filed"
        models = [call.kwargs.get("model") for call in mocks["extract"].call_args_list]
        assert models[-1] == "qwen2.5:14b-instruct"

    def test_transient_exhaust_and_fallback_triages(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        ocr_result = _make_ocr_result(pdf_path=staging_pdf)
        side_effects = [
            IncompleteExtraction(["HTTP error: t1"], transient=True),
            IncompleteExtraction(["HTTP error: t2"], transient=True),
            IncompleteExtraction(["HTTP error: t3"], transient=True),
            IncompleteExtraction(["HTTP error: fallback"], transient=True),
        ]
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_result=_make_classify_result(),
            extract_side_effect=side_effects,
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "triaged"

    def test_semantic_failure_does_not_retry(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        ocr_result = _make_ocr_result(pdf_path=staging_pdf)
        # Single semantic failure - must NOT trigger retries.
        side_effects = [
            IncompleteExtraction(["missing field date"], transient=False),
        ]
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_result=_make_classify_result(),
            extract_side_effect=side_effects,
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "triaged"
        # Exactly one extract call (no retry).
        assert mocks["extract"].call_count == 1


class TestPipelineTimeoutShortCircuit:
    """``requests.exceptions.Timeout`` must short-circuit to triage without retry.

    Spec §11 explicitly excludes Timeout from the transient class - the
    classifier/extractor wrappers re-raise it unwrapped, ``_retry_llm_call``
    sees a non-transient exception (``is_transient`` returns False) and
    propagates it on the first attempt. The orchestrator catches it and
    triages the document.
    """

    def test_classifier_timeout_short_circuits_without_retry(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        from requests.exceptions import Timeout

        ocr_result = _make_ocr_result(pdf_path=staging_pdf)
        # Inject Timeout on the very first classify call. If the helper
        # mistakenly treated it as transient, the side_effect list would
        # need additional entries; a single entry proves the call is one-shot.
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_side_effect=[Timeout("upstream timed out")],
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "triaged"
        assert mocks["classify"].call_count == 1
        reasons = result.metadata["triage_reasons"]
        assert any("classifier error" in r for r in reasons)

    def test_extractor_timeout_short_circuits_without_retry(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        from requests.exceptions import Timeout

        ocr_result = _make_ocr_result(pdf_path=staging_pdf)
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_result=_make_classify_result(),
            extract_side_effect=[Timeout("upstream timed out")],
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "triaged"
        assert mocks["extract"].call_count == 1
        reasons = result.metadata["triage_reasons"]
        assert any("extractor error" in r for r in reasons)
