from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from bim.commands.doc.shared.classifier import ClassifyResult
from bim.commands.doc.shared.extractor import ExtractResult
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
from bim.commands.doc.shared.state_db import StateDB
from bim.commands.doc.shared.zettel_writer import ZettelWriter
from bim.params.doc_ingest import IngestParams
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


# ----------------------- TestClaimReleaseAndReclaim -----------------------


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
        # Backing off must not release someone else's claim: a fresh attempt
        # can only lose while the live worker's row is still there.
        assert state_db.claim(sha) is False

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
