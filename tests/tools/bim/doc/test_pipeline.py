from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
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
        # v1: zettel lands under per-issuer subfolder.
        assert zettel_path.parent == settings.paths.vault_root / "Zettelkasten" / "documents" / "cez-as"

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

    def test_filed_document_duplicate_sidecar_keeps_filed_wording(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """A duplicate of a genuinely filed document must keep today's sidecar
        wording unchanged. Only a duplicate of a still-pending triage document
        should stop claiming the document was filed - this row was actually
        filed, so the claim is true and must survive the fix.
        """
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

        pipeline, _ = _build_pipeline(
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

        assert result.metadata["outcome"] == "duplicate"
        sidecar = staging_pdf.with_suffix(staging_pdf.suffix + ".duplicate.yml")
        sidecar_text = sidecar.read_text(encoding="utf-8")
        assert "already maps to a filed document" in sidecar_text

    # --- 5. triage on classifier confidence below threshold ---

    def test_triage_on_low_classifier_confidence(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        import yaml

        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        pipeline, mocks = _build_pipeline(
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

        # Extraction must run even when confidence is below threshold so the
        # human reviewer sees the model's best guess at the document fields,
        # not a wall of nulls.
        assert mocks["extract"].call_count == 1
        proposal_data = yaml.safe_load(proposal_text)
        assert proposal_data["document"]["number"] == "7102105594"
        assert proposal_data["document"]["amount"] == 4218.0
        assert proposal_data["document"]["currency"] == "CZK"

        # PDF must be in business_root/_triage/.
        triage_dir = settings.paths.business_root / "_triage"
        assert triage_dir.exists()
        triage_pdfs = list(triage_dir.glob("*.pdf"))
        assert len(triage_pdfs) == 1

        # Triage records a dedup row for the raw source sha so the same bytes
        # arriving again while the proposal is still pending don't re-run the
        # whole pipeline. Nothing is filed yet - that half is pinned by
        # ``test_triage_records_processed_row_for_raw_source_sha``.
        dedup = state_db.dedup(sha)
        assert dedup.is_duplicate is True
        assert dedup.existing_row is not None
        # The row has to describe THIS document: the file it names is the one
        # this run parked in _triage, so anyone following the dedup record
        # reaches the pending proposal instead of an unrelated document.
        assert dedup.existing_row.canonical_filename == f"_triage/{triage_pdfs[0].name} (pending review)"

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

    def test_pipeline_passes_original_filename_to_extractor(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        # The original filename signal often is the invoice number itself
        # for downloaded PDFs (e.g. 1059707807.pdf). The pipeline must thread
        # it into the extractor as a hint so the model can ground numbers
        # it can't recover from noisy OCR.
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(),
            extract_result=_make_extract_result(),
        )
        params = IngestParams(
            source="download",
            staging_path=staging_pdf,
            original_filename="1059707807.pdf",
            email_subject="Your invoice is ready",
        )
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "filed"
        assert mocks["extract"].call_count == 1
        call_kwargs = mocks["extract"].call_args.kwargs
        hints = call_kwargs.get("hints")
        assert hints == {
            "original_filename": "1059707807.pdf",
            "email_subject": "Your invoice is ready",
        }

    def test_pipeline_extractor_hints_omitted_when_no_signals(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        # When IngestParams has neither original_filename nor email_subject,
        # the pipeline must pass hints=None (rather than an empty dict) so
        # the extractor's user prompt stays clean.
        pipeline, mocks = _build_pipeline(
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
        call_kwargs = mocks["extract"].call_args.kwargs
        assert call_kwargs.get("hints") is None

    def test_triage_surfaces_partial_extracted_fields(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        # When the extractor finds some fields but misses required ones, the
        # IncompleteExtraction it raises now carries a partial ExtractResult.
        # The pipeline must surface those partial fields in the proposal -
        # otherwise the human reviewer ends up filling in fields the model
        # did successfully read off the page.
        import yaml

        partial_result = ExtractResult(
            doc_type="invoice",
            number="INV-2026-0042",
            currency="CZK",
        )
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(),
            extract_side_effect=IncompleteExtraction(
                ["missing field date", "missing field amount"],
                partial=partial_result,
            ),
        )
        params = IngestParams(source="email", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "triaged"
        proposal_path = Path(result.metadata["proposal_path"])
        proposal_data = yaml.safe_load(proposal_path.read_text(encoding="utf-8"))

        # Partial fields populate the proposal so the reviewer doesn't lose them.
        assert proposal_data["document"]["number"] == "INV-2026-0042"
        assert proposal_data["document"]["currency"] == "CZK"
        # Missing required fields stay null and the reasons name them.
        assert proposal_data["document"]["date"] is None
        assert proposal_data["document"]["amount"] is None
        assert any("date" in r for r in proposal_data["triage_reasons"])
        assert any("amount" in r for r in proposal_data["triage_reasons"])

    # --- 7. triage on unknown issuer (classifier returned slug not in registry) ---

    def test_triage_on_unknown_issuer(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        import yaml

        # Classifier returns issuer_slug=None (resolve_alias upstream miss).
        pipeline, mocks = _build_pipeline(
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
        # Computed before run() because triage moves the staging PDF away.
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        params = IngestParams(source="email", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "triaged"

        proposal_path = Path(result.metadata["proposal_path"])
        assert proposal_path.exists()
        proposal_text = proposal_path.read_text(encoding="utf-8")
        # Should include a triage reason mentioning the issuer not being known.
        lower = proposal_text.lower()
        assert any(token in lower for token in ("unknown issuer", "unrecognized issuer", "issuer not in registry"))

        # The dedup row this triage records has to describe THIS document: the
        # document type the classifier returned, and no attribution to an
        # issuer nobody identified. (Which placeholder stands in for "no
        # issuer" is not pinned by the spec, so only the misattribution is
        # ruled out here.)
        row = state_db.dedup(sha).existing_row
        assert row is not None
        assert row.doc_type == "invoice"
        assert row.issuer_slug != "cez-as"

        # Extraction must run even when the issuer is unknown so the human
        # reviewer sees the model's best guess at the document fields, not a
        # wall of nulls. This is what `bim doc ingest` users hit when a vendor
        # is brand new but qwen recognised it as an invoice with date/number.
        assert mocks["extract"].call_count == 1
        proposal_data = yaml.safe_load(proposal_text)
        assert proposal_data["document"]["number"] == "7102105594"
        # write_proposal serialises dates as ISO strings via YAML's default
        # representer; safe_load parses them back as plain strings.
        assert proposal_data["document"]["date"] == "2021-03-11"
        assert proposal_data["document"]["amount"] == 4218.0
        assert proposal_data["document"]["currency"] == "CZK"

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

        pipeline, mocks = _build_pipeline(
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

        # Extraction still runs - both unknown issuer and low confidence are
        # triage triggers, but neither suppresses the extractor. The proposal
        # carries the model's field-level output so the human reviewer can
        # confirm or correct it.
        assert mocks["extract"].call_count == 1
        assert proposal_data["document"]["number"] == "7102105594"
        assert proposal_data["document"]["amount"] == 4218.0

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

        # The in-flight claim row must be gone; release_claim returns False when
        # there was nothing left to remove. ``claim()`` can no longer stand in
        # for this check - triage now records a processed row for the raw source
        # sha, and claim() refuses any sha that is already processed.
        assert state_db.release_claim(sha) is False
        # So a later claim is refused, but for the right reason: the document
        # is known, not because this run parked its reservation forever. Both
        # halves together are what "released" means after triage.
        assert state_db.claim(sha) is False

    def test_triage_records_processed_row_for_raw_source_sha(
        self,
        tmp_path: Path,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """Routing to triage must still stamp the raw source sha as seen.

        The proposal can sit in ``_triage`` for days. Until it is promoted no
        ``processed`` row used to exist, so the same source arriving again paid
        for a second OCR/classify/extract pass. The row is a dedup marker only -
        nothing is filed at this point.
        """
        # A scanned source: OCR writes a NEW pdf carrying the text layer, so the
        # file that ends up parked in _triage does not hash to the file that
        # arrived. Only the identity the run claimed on can match a re-arrival
        # of the source, so re-hashing whatever is on hand records a sha no
        # incoming file will ever have.
        ocr_pdf = _write_pdf(tmp_path / "ocr_output.pdf", b"%PDF-1.4\nocr'd content with a text layer\n")
        # Deliberately not the default ČEZ invoice the other tests use: doc
        # type, date and number all differ, so the row below can only be right
        # if it was built from this run's own inputs.
        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=ocr_pdf),
            classify_result=_make_classify_result(doc_type="receipt", confidence=0.30),
            extract_result=_make_extract_result(
                doc_type="receipt",
                number="RS-2019-0042",
                date_value=date(2019, 7, 4),
            ),
        )
        # Computed before run() because triage moves the staging PDF away.
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        assert hashlib.sha256(ocr_pdf.read_bytes()).hexdigest() != sha  # sanity: bytes truly differ
        params = IngestParams(source="email", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "triaged"

        dedup = state_db.dedup(sha)
        assert dedup.is_duplicate is True
        assert dedup.existing_row is not None
        row = dedup.existing_row
        assert row.sha256 == sha
        # The row describes this document, not a generic placeholder: it names
        # the very file the run parked in _triage (whose timestamp and title
        # come from the extracted date and number), and carries the issuer and
        # document type the classifier produced for it.
        triage_pdf = Path(result.metadata["triage_pdf_path"])
        assert triage_pdf.exists()
        # The parked file is not the source file - the sha above is the claimed
        # one, not a hash taken after the move.
        assert hashlib.sha256(triage_pdf.read_bytes()).hexdigest() != sha
        assert row.canonical_filename == f"_triage/{triage_pdf.name} (pending review)"
        assert row.issuer_slug == "cez-as"
        assert row.doc_type == "receipt"
        # Stamped when this run happened. A fixed instant would make every
        # "what did we process this week" query answer wrong.
        assert datetime.now(timezone.utc) - row.processed_at < timedelta(minutes=1)

        # Nothing was filed to earn that row: the PDF is still parked in
        # _triage beside its proposal, and no zettel exists.
        triage_dir = settings.paths.business_root / "_triage"
        assert Path(result.metadata["proposal_path"]).exists()
        assert [p for p in settings.paths.business_root.rglob("*.pdf") if p.parent != triage_dir] == []
        assert list(settings.paths.vault_root.rglob("*.md")) == []

    def test_second_arrival_of_triaged_document_is_duplicate_without_reprocessing(
        self,
        tmp_path: Path,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """A resent copy of a document awaiting triage must cost nothing.

        Same bytes, different staging path (a re-sent mail, a repeated scan).
        The pending proposal already represents this document, so the second
        run reports ``duplicate`` and touches none of the slow boundaries.
        """
        source_bytes = staging_pdf.read_bytes()
        # The first run's OCR produces its own file, so what waits in _triage
        # hashes differently from the source. Recognising the resent copy can
        # then only work off the identity the first run claimed on.
        first_ocr_pdf = _write_pdf(tmp_path / "ingest_ocr_output.pdf", b"%PDF-1.4\nocr'd content with a text layer\n")
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=first_ocr_pdf),
            classify_result=_make_classify_result(confidence=0.30),
            extract_result=_make_extract_result(),
        )
        first = pipeline.run(IngestParams(source="email", staging_path=staging_pdf))
        assert first.metadata["outcome"] == "triaged"
        calls_after_first = (
            mocks["ocr"].call_count,
            mocks["classify"].call_count,
            mocks["extract"].call_count,
        )

        resent = _write_pdf(tmp_path / "staging-resent" / "input.pdf", source_bytes)
        # Point the OCR stub at the file the second run would hand it, so this
        # run could complete on its own merits. Reporting ``duplicate`` has to
        # be a decision, not a crash on a moved staging file.
        mocks["ocr"].return_value = _make_ocr_result(pdf_path=resent)
        second = pipeline.run(IngestParams(source="email", staging_path=resent))

        assert second.success is True
        assert second.metadata["outcome"] == "duplicate"
        # The reviewer is pointed at the pending file this document already
        # produced - the name the first run wrote to _triage, both in the
        # result and in the sidecar left next to the resent copy.
        first_triage_name = Path(first.metadata["triage_pdf_path"]).name
        assert second.metadata["existing_canonical_filename"] == f"_triage/{first_triage_name} (pending review)"
        sidecar = resent.with_suffix(resent.suffix + ".duplicate.yml")
        assert sidecar.exists()
        assert first_triage_name in sidecar.read_text(encoding="utf-8")
        # Not one extra call to OCR, the classifier or the extractor.
        assert (
            mocks["ocr"].call_count,
            mocks["classify"].call_count,
            mocks["extract"].call_count,
        ) == calls_after_first
        # And no second proposal competing for the reviewer's attention.
        triage_dir = settings.paths.business_root / "_triage"
        assert len(list(triage_dir.glob("*.proposed.yml"))) == 1

    def test_pending_triage_duplicate_sidecar_says_awaiting_review_not_filed(
        self,
        tmp_path: Path,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """A duplicate of a document still parked in ``_triage`` must not lie
        and say it was filed - nothing has been filed yet, the document is
        awaiting human review.
        """
        source_bytes = staging_pdf.read_bytes()
        first_ocr_pdf = _write_pdf(tmp_path / "ingest_ocr_output.pdf", b"%PDF-1.4\nocr'd content with a text layer\n")
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=first_ocr_pdf),
            classify_result=_make_classify_result(confidence=0.30),
            extract_result=_make_extract_result(),
        )
        first = pipeline.run(IngestParams(source="email", staging_path=staging_pdf))
        assert first.metadata["outcome"] == "triaged"

        resent = _write_pdf(tmp_path / "staging-resent" / "input.pdf", source_bytes)
        mocks["ocr"].return_value = _make_ocr_result(pdf_path=resent)
        second = pipeline.run(IngestParams(source="email", staging_path=resent))

        assert second.metadata["outcome"] == "duplicate"
        sidecar = resent.with_suffix(resent.suffix + ".duplicate.yml")
        sidecar_text = sidecar.read_text(encoding="utf-8")
        assert "filed document" not in sidecar_text
        assert "review" in sidecar_text.lower()

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

    def test_zettel_collision_in_per_issuer_subfolder_increments_timestamp(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """A pre-existing zettel under <vault>/<doc-subdir>/<issuer-slug>/ must
        block the same canonical filename from being reused.

        Regression: blind review found _resolve_collision probed the flat
        legacy path (vault/<basename>.md) while ZettelWriter writes to the
        per-issuer path (vault/<issuer-slug>/<basename>.md). A collision in
        the per-issuer subfolder was therefore missed and the existing zettel
        would be silently overwritten.
        """
        # Pre-create a colliding zettel in the per-issuer vault subfolder.
        existing_zettel = (
            settings.paths.vault_root
            / "Zettelkasten"
            / "documents"
            / "cez-as"
            / "20210311000000-cez-as-7102105594.invoice.md"
        )
        existing_zettel.parent.mkdir(parents=True, exist_ok=True)
        existing_text = "# pre-existing zettel\n\nthis content must survive\n"
        existing_zettel.write_text(existing_text, encoding="utf-8")

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

        # The pre-existing zettel must still hold its original bytes.
        assert existing_zettel.exists()
        assert existing_zettel.read_text(encoding="utf-8") == existing_text

        # The newly-written zettel must use a different (advanced) timestamp.
        new_zettel = Path(result.metadata["zettel_path"])
        assert new_zettel != existing_zettel
        assert new_zettel.name.startswith("20210311000001-cez-as-7102105594.invoice")
        assert new_zettel.parent == existing_zettel.parent

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

    def test_triage_path_stops_reporting_at_classify_when_classifier_fails(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        # A hard classifier failure (no doc_type produced) short-circuits to
        # triage before extract - there's nothing to extract against. Soft
        # triage triggers (low confidence, unknown issuer) DO run extract so
        # the proposal carries field guesses for the human reviewer; that
        # behaviour is covered by the dedicated triage tests above.
        from bim.commands.doc.shared.classifier import ClassifierError

        pipeline, _ = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_side_effect=ClassifierError("could not parse JSON", transient=False),
        )
        reporter = _RecordingProgressReporter()
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params, reporter=reporter)

        assert result.metadata["outcome"] == "triaged"
        # Pipeline reports OCR + classify; extract never runs because there's
        # no doc_type to extract against, so it must not appear in stages.
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


class TestClaimReleaseAndReclaim:
    """A claim must outlive neither a Ctrl-C nor the worker that took it.

    Two ways a sha256 used to get parked forever: the pipeline released its
    claim only in ``except Exception``, so a ``KeyboardInterrupt`` skipped
    the release; and the claim was taken with no max age, so a claim left by
    a killed worker made every later run report "duplicate".
    """

    def test_keyboard_interrupt_propagates_and_releases_claim(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(),
            extract_result=_make_extract_result(),
        )
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        second_claim_during_run: list[bool] = []

        def interrupt_while_claimed(*_args: Any, **_kwargs: Any) -> OCRResult:
            # Mid-run, a competing worker must be locked out. A second claim
            # can only fail while this run is holding the sha, so recording
            # False here proves the run reserved it rather than merely reading
            # the claims table and walking past it.
            second_claim_during_run.append(state_db.claim(sha))
            raise KeyboardInterrupt

        # Ctrl-C lands while the slow OCR boundary call is in flight - the
        # realistic moment for a user to abandon an ingest run.
        mocks["ocr"].side_effect = interrupt_while_claimed
        params = IngestParams(source="download", staging_path=staging_pdf)

        # The interrupt must reach the caller; the pipeline may not swallow it
        # into a CommandResult.
        with pytest.raises(KeyboardInterrupt):
            pipeline.run(params)

        # The sha was genuinely held while the run was in flight...
        assert second_claim_during_run == [False]
        # ...and the claim must be gone anyway. A fresh claim succeeding here
        # proves no claim row was left behind.
        assert state_db.claim(sha) is True

    def test_system_exit_also_releases_claim(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """Every BaseException releases the claim, not just Ctrl-C.

        ``SystemExit`` (a shutdown signal handler, ``sys.exit`` from a
        boundary library) parks the sha just as permanently as an interrupt
        would, so catching only ``KeyboardInterrupt`` is not enough.
        """
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(),
            extract_result=_make_extract_result(),
        )
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        mocks["ocr"].side_effect = SystemExit()
        params = IngestParams(source="download", staging_path=staging_pdf)

        with pytest.raises(SystemExit):
            pipeline.run(params)

        assert state_db.claim(sha) is True

    def test_interrupt_releases_only_the_interrupted_documents_claim(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """Releasing a claim must not disturb claims other workers hold.

        The interrupted run owns exactly one sha; a sibling worker's live
        claim on a different document has to survive the release.
        """
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(),
            extract_result=_make_extract_result(),
        )
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        other_sha = hashlib.sha256(b"a different document another worker is busy with").hexdigest()
        state_db.connection.execute(
            "INSERT INTO claims (sha256, claimed_at) VALUES (?, ?)",
            (other_sha, datetime.now(timezone.utc).isoformat()),
        )

        mocks["ocr"].side_effect = KeyboardInterrupt()
        params = IngestParams(source="download", staging_path=staging_pdf)
        with pytest.raises(KeyboardInterrupt):
            pipeline.run(params)

        assert state_db.claim(sha) is True
        # The sibling worker still owns its document: a claim attempt on it
        # only fails while its row is still there.
        assert state_db.claim(other_sha) is False

    def test_rerun_after_interrupt_files_instead_of_reporting_duplicate(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(pdf_path=staging_pdf),
            classify_result=_make_classify_result(),
            extract_result=_make_extract_result(),
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        mocks["ocr"].side_effect = KeyboardInterrupt()
        with pytest.raises(KeyboardInterrupt):
            pipeline.run(params)

        # The user re-runs the same source file after the interrupt. It must
        # be processed for real, not reported as already handled.
        mocks["ocr"].side_effect = None
        mocks["ocr"].return_value = _make_ocr_result(pdf_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "filed"
        assert Path(result.metadata["pdf_path"]).exists()
        assert Path(result.metadata["zettel_path"]).exists()

    @pytest.mark.parametrize("claim_max_age_minutes", [60, 10])
    def test_stale_claim_is_reclaimed_instead_of_reported_duplicate(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
        claim_max_age_minutes: int,
    ) -> None:
        # Run at the default window and at a configured one: the age that
        # counts as abandoned has to follow the setting, so no fixed window
        # baked into the pipeline can satisfy both this test and its live-claim
        # counterpart.
        settings = settings.model_copy(update={"claim_max_age_minutes": claim_max_age_minutes})
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        # A worker died mid-ingest longer ago than claim_max_age_minutes and
        # never released its claim. Seeded straight into the table because no
        # public API can backdate a claim.
        stale_at = datetime.now(timezone.utc) - timedelta(minutes=claim_max_age_minutes + 5)
        state_db.connection.execute(
            "INSERT INTO claims (sha256, claimed_at) VALUES (?, ?)",
            (sha, stale_at.isoformat()),
        )

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
        assert result.metadata["outcome"] != IngestOutcome.DUPLICATE.value
        assert result.metadata["outcome"] == "filed"
        # Proceeding means the document really was processed, not relabelled.
        assert Path(result.metadata["pdf_path"]).exists()
        assert state_db.dedup(sha).is_duplicate is True

    @pytest.mark.parametrize("claim_max_age_minutes", [60, 10])
    def test_live_claim_still_short_circuits_as_duplicate(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
        claim_max_age_minutes: int,
    ) -> None:
        """Reclaim must only fire past the age limit, never on a live claim.

        Boundary guard for the max_age wiring: a claim taken inside the window
        belongs to a worker that is still running, so stealing it would process
        the same document twice. Run at both windows so "live" is read from the
        setting rather than from a fixed span.
        """
        settings = settings.model_copy(update={"claim_max_age_minutes": claim_max_age_minutes})
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        # Five minutes short of the limit: still unambiguously live (staleness
        # is strictly older than the limit), yet close enough to the boundary
        # that a window shrunk to some fraction of the setting would wrongly
        # steal it.
        claimed_at = datetime.now(timezone.utc) - timedelta(minutes=claim_max_age_minutes - 5)
        state_db.connection.execute(
            "INSERT INTO claims (sha256, claimed_at) VALUES (?, ?)",
            (sha, claimed_at.isoformat()),
        )

        pipeline, mocks = _build_pipeline(
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
        assert result.metadata["outcome"] == IngestOutcome.DUPLICATE.value
        assert result.metadata["sha256"] == sha
        # No work done - the other worker owns this document.
        mocks["ocr"].assert_not_called()
        mocks["classify"].assert_not_called()

    def test_exception_path_keeps_structured_result_and_releases_claim(
        self,
        settings: DocSettings,
        registry: IssuerRegistry,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """Moving the release into ``finally`` must not change the error result."""
        pipeline, mocks = _build_pipeline(
            settings,
            registry,
            state_db,
            mocker,
            ocr_result=None,
        )
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        mocks["ocr"].side_effect = RuntimeError("boom from ocr")
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is False
        assert "pipeline failed" in (result.error or "")
        assert "boom from ocr" in (result.error or "")
        assert result.metadata["sha256"] == sha
        assert result.metadata["stage"] == "post-claim"
        assert result.metadata["exception_type"] == "RuntimeError"
        assert "boom from ocr" in result.metadata["exception_repr"]
        # The claim still has to go, exactly as the old except-block did it.
        assert state_db.claim(sha) is True


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
