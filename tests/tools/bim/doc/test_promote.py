from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from bim.commands.doc.promote.promote import CommandPromote, PromoteServices
from bim.commands.doc.shared.issuers import load_registry
from bim.commands.doc.shared.ocr import OCRResult
from bim.commands.doc.shared.settings_models import DocSettings
from bim.commands.doc.shared.state_db import StateDB
from bim.commands.doc.shared.triage import write_proposal
from bim.commands.doc.shared.zettel_writer import ZettelWriter
from bim.params.doc_promote import PromoteParams
from buvis.pybase.result import CommandResult
from pytest_mock import MockerFixture

from . import promote_helpers
from .promote_helpers import _build_command, _build_proposal, _stage_triage_pair

settings = promote_helpers.settings
registry_path = promote_helpers.registry_path
lock_path = promote_helpers.lock_path
state_db = promote_helpers.state_db

# ----------------------- scenarios -----------------------


class TestCommandPromote:
    def test_happy_path_files_pdf_and_writes_zettel(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        triage_dir = settings.paths.business_root / "_triage"
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        write_proposal(yml, _build_proposal(sha256=sha, triage_pdf=pdf))

        cmd, _mocks = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml,
            mocker=mocker,
            ocr_pdf=pdf,
        )

        result = cmd.execute()

        assert isinstance(result, CommandResult)
        assert result.success is True

        target_pdf = Path(result.metadata["pdf_path"])
        assert target_pdf.exists()
        assert target_pdf.parent == settings.paths.business_root / "cez-as"
        assert not pdf.exists()

        zettel_path = Path(result.metadata["zettel_path"])
        assert zettel_path.exists()
        # v1: zettel lands under per-issuer subfolder.
        assert zettel_path.parent == settings.paths.vault_root / "Zettelkasten" / "documents" / "cez-as"

        # Proposal deleted after promote.
        assert not yml.exists()

        # state_db has a processed row for this sha.
        dedup = state_db.dedup(sha)
        assert dedup.is_duplicate is True
        assert dedup.existing_row is not None
        # extraction_method=manual since promote came from human-approved triage.
        assert dedup.existing_row.extraction_method == "manual"

    def test_register_issuer_adds_entry_and_files_pdf(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        triage_dir = settings.paths.business_root / "_triage"
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-newvendor-12345.invoice")
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        write_proposal(
            yml,
            _build_proposal(
                sha256=sha,
                triage_pdf=pdf,
                register_issuer=True,
                issuer_slug="new-vendor",
                issuer_display="New Vendor s.r.o.",
                doc_number="12345",
            ),
        )

        cmd, _ = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml,
            mocker=mocker,
            ocr_pdf=pdf,
        )

        result = cmd.execute()

        assert result.success is True

        reloaded = load_registry(registry_path)
        assert "new-vendor" in reloaded.issuers
        assert reloaded.issuers["new-vendor"].display_name == "New Vendor s.r.o."

        target_pdf = Path(result.metadata["pdf_path"])
        assert target_pdf.parent == settings.paths.business_root / "new-vendor"
        assert target_pdf.exists()

        # Spec §3 mandates inbox/ for every registered issuer.
        inbox_dir = settings.paths.business_root / "new-vendor" / "inbox"
        assert inbox_dir.is_dir()

    def test_unapproved_proposal_returns_failure(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        triage_dir = settings.paths.business_root / "_triage"
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-x.invoice")
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        write_proposal(yml, _build_proposal(sha256=sha, triage_pdf=pdf, approved=False))

        cmd, _ = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml,
            mocker=mocker,
            ocr_pdf=pdf,
        )

        result = cmd.execute()

        assert result.success is False
        assert "approved" in (result.error or "").lower()
        assert pdf.exists()
        assert yml.exists()

    def test_invalid_slug_returns_failure(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        triage_dir = settings.paths.business_root / "_triage"
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-bogus-x.invoice")
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        write_proposal(
            yml,
            _build_proposal(
                sha256=sha,
                triage_pdf=pdf,
                issuer_slug="not-in-registry",
                register_issuer=False,
            ),
        )

        cmd, _ = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml,
            mocker=mocker,
            ocr_pdf=pdf,
        )

        result = cmd.execute()

        assert result.success is False
        assert pdf.exists()
        assert yml.exists()

    def test_promote_files_ocr_result_pdf_when_full_ocr_branch_ran(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """Regression: promote must file the OCR'd PDF, not the original sibling, when full OCR fired."""
        from bim.commands.doc.shared.ocr import OCRRunner

        triage_dir = settings.paths.business_root / "_triage"
        sibling_pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
        sibling_bytes = b"%PDF-1.4\nold sibling without ocr layer\n"
        sibling_pdf.write_bytes(sibling_bytes)
        # Full-OCR branch produces a separate file with embedded text layer.
        ocr_pdf = triage_dir / "ocr-output.pdf"
        ocr_bytes = b"%PDF-1.4\nfreshly ocr'd content\n"
        ocr_pdf.write_bytes(ocr_bytes)

        sha_of_sibling = hashlib.sha256(sibling_bytes).hexdigest()
        sha_of_ocr = hashlib.sha256(ocr_bytes).hexdigest()
        assert sha_of_sibling != sha_of_ocr  # sanity: bytes truly differ

        write_proposal(yml, _build_proposal(sha256=sha_of_sibling, triage_pdf=sibling_pdf))

        registry = load_registry(registry_path)
        ocr_runner = OCRRunner(settings=settings, state_dir=settings.paths.state_dir)
        mocker.patch.object(
            ocr_runner,
            "run",
            return_value=OCRResult(
                ocr_text="fresh ocr text",
                pdf_path=ocr_pdf,
                was_redone=False,
                original_backup_path=None,
                mean_confidence=0.91,
                pages=2,
            ),
        )
        zettel_writer = ZettelWriter(
            repo=None,
            vault_root=settings.paths.vault_root,
            vault_documents_subdir=settings.paths.vault_documents_subdir,
        )
        services = PromoteServices(
            registry=registry,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            ocr_runner=ocr_runner,
            zettel_writer=zettel_writer,
        )
        cmd = CommandPromote(
            params=PromoteParams(proposed_yml_path=yml),
            settings=settings,
            services=services,
        )
        result = cmd.execute()

        assert result.success is True
        target_pdf = Path(result.metadata["pdf_path"])
        # Filed PDF must be the OCR'd bytes, not the original sibling bytes.
        assert target_pdf.read_bytes() == ocr_bytes
        # state_db sha must match the OCR'd bytes.
        assert state_db.dedup(sha_of_ocr).is_duplicate is True
        # Original sibling and OCR temp paths are both gone.
        assert not sibling_pdf.exists()
        assert not ocr_pdf.exists()

    def test_promote_dedups_raw_source_sha_as_well_as_filed_pdf_sha(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """Re-ingesting the original source PDF after promote must be a duplicate.

        Promote's full-OCR branch files a PDF carrying an embedded text layer,
        so its bytes - and its sha - differ from the raw source the pipeline
        claimed on at ingest time. Recording only the filed sha leaves the
        original file unknown, and the next arrival of it gets archived a
        second time. Both identities have to resolve.
        """
        from bim.commands.doc.shared.ocr import OCRRunner

        triage_dir = settings.paths.business_root / "_triage"
        sibling_pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
        # The file that arrived by email. Ingest OCR'd it before parking the
        # result in _triage, so these bytes exist on no disk that promote can
        # see - the proposal's recorded sha is the only trace of them left.
        raw_source_bytes = b"%PDF-1.4\nraw source exactly as it arrived by email\n"
        # What actually waits in _triage: ingest's OCR output, already a
        # different file from the raw source.
        triage_bytes = b"%PDF-1.4\ntriage copy the ingest run left behind\n"
        sibling_pdf.write_bytes(triage_bytes)
        ocr_pdf = triage_dir / "ocr-output.pdf"
        filed_bytes = b"%PDF-1.4\nsame document, now with an embedded text layer\n"
        ocr_pdf.write_bytes(filed_bytes)

        raw_source_sha = hashlib.sha256(raw_source_bytes).hexdigest()
        filed_sha = hashlib.sha256(filed_bytes).hexdigest()
        triage_sha = hashlib.sha256(triage_bytes).hexdigest()
        # sanity: three genuinely different identities in play
        assert len({raw_source_sha, filed_sha, triage_sha}) == 3

        # sha256 on the proposal's source block is the raw source sha the
        # pipeline computed and claimed on at ingest time.
        write_proposal(yml, _build_proposal(sha256=raw_source_sha, triage_pdf=sibling_pdf))

        registry = load_registry(registry_path)
        ocr_runner = OCRRunner(settings=settings, state_dir=settings.paths.state_dir)
        mocker.patch.object(
            ocr_runner,
            "run",
            return_value=OCRResult(
                ocr_text="fresh ocr text",
                pdf_path=ocr_pdf,
                was_redone=False,
                original_backup_path=None,
                mean_confidence=0.91,
                pages=2,
            ),
        )
        zettel_writer = ZettelWriter(
            repo=None,
            vault_root=settings.paths.vault_root,
            vault_documents_subdir=settings.paths.vault_documents_subdir,
        )
        services = PromoteServices(
            registry=registry,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            ocr_runner=ocr_runner,
            zettel_writer=zettel_writer,
        )
        cmd = CommandPromote(
            params=PromoteParams(proposed_yml_path=yml),
            settings=settings,
            services=services,
        )
        result = cmd.execute()

        assert result.success is True
        target_pdf = Path(result.metadata["pdf_path"])
        # Precondition for the whole test: the filed bytes are the OCR'd ones.
        assert target_pdf.read_bytes() == filed_bytes

        # The headline: the source file, re-ingested, is recognised. Nothing on
        # disk hashes to it any more, so this only holds if promote records the
        # identity the proposal carries from ingest rather than re-hashing
        # whichever PDF it happens to be holding.
        raw_dedup = state_db.dedup(raw_source_sha)
        assert raw_dedup.is_duplicate is True
        assert raw_dedup.existing_row is not None

        # Regression pin: the filed sha's row must survive too, not be
        # replaced by the raw one.
        filed_dedup = state_db.dedup(filed_sha)
        assert filed_dedup.is_duplicate is True
        assert filed_dedup.existing_row is not None

        # Both identities describe the one archived document, so both rows have
        # to name the file that is actually on disk and agree on everything but
        # the sha that indexes them. A row of placeholders would satisfy
        # ``is_duplicate`` while telling every later audit query a wrong story.
        raw_row = raw_dedup.existing_row
        filed_row = filed_dedup.existing_row
        assert raw_row.canonical_filename == target_pdf.name
        volatile = {"sha256", "processed_at"}
        assert raw_row.model_dump(exclude=volatile) == filed_row.model_dump(exclude=volatile)
        # processed_at is compared loosely: writing the two rows microseconds
        # apart is legitimate, stamping one with a placeholder instant is not.
        assert abs(raw_row.processed_at - filed_row.processed_at) < timedelta(seconds=5)
        assert datetime.now(timezone.utc) - raw_row.processed_at < timedelta(minutes=1)
        assert len(list((settings.paths.business_root / "cez-as").glob("*.pdf"))) == 1

    def test_promote_dedups_raw_source_sha_when_ocr_hands_back_the_triage_pdf(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """The raw source identity is recorded on the cheap promote path too.

        Most promotes never produce a new PDF: the file waiting in ``_triage``
        already carries a text layer, so OCR hands the same file straight back
        and that file is what gets filed. The raw source the pipeline claimed on
        at ingest is still a different file, so its identity has to be recorded
        here as well - not only when the full-OCR branch fires.
        """
        triage_dir = settings.paths.business_root / "_triage"
        sibling_pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
        # The file as it arrived by email. Ingest OCR'd it before parking the
        # result in _triage, so nothing promote can see hashes to these bytes.
        raw_source_sha = hashlib.sha256(b"%PDF-1.4\nraw source exactly as it arrived by email\n").hexdigest()
        sibling_sha = hashlib.sha256(sibling_pdf.read_bytes()).hexdigest()
        assert raw_source_sha != sibling_sha  # sanity: two genuine identities

        write_proposal(yml, _build_proposal(sha256=raw_source_sha, triage_pdf=sibling_pdf))

        cmd, _mocks = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml,
            # OCR returns the very file it was handed - no new PDF, no new sha.
            ocr_pdf=sibling_pdf,
            mocker=mocker,
        )
        result = cmd.execute()

        assert result.success is True
        target_pdf = Path(result.metadata["pdf_path"])
        # Precondition for the whole test: this run did NOT take the full-OCR
        # branch, so the filed bytes are the triage sibling's own.
        assert hashlib.sha256(target_pdf.read_bytes()).hexdigest() == sibling_sha

        # Re-arrival of the original source is still recognised, even though
        # this promote produced no new bytes to notice the difference on.
        assert state_db.dedup(raw_source_sha).is_duplicate is True
        # And the filed identity resolves too.
        assert state_db.dedup(sibling_sha).is_duplicate is True

    def test_missing_sibling_pdf_returns_failure(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        triage_dir = settings.paths.business_root / "_triage"
        triage_dir.mkdir(parents=True, exist_ok=True)
        yml = triage_dir / "20210311083422-cez-as-7102105594.invoice.pdf.proposed.yml"
        missing_pdf = triage_dir / "20210311083422-cez-as-7102105594.invoice.pdf"
        # Note: missing_pdf is intentionally NOT created on disk.
        write_proposal(yml, _build_proposal(sha256="0" * 64, triage_pdf=missing_pdf))

        cmd, _ = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml,
            mocker=mocker,
            ocr_pdf=missing_pdf,
        )

        result = cmd.execute()

        assert result.success is False
        assert "pdf" in (result.error or "").lower()
        assert yml.exists()

    def test_promote_preserves_proposal_ingested_at(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """Regression for criterion 8: promote must preserve the proposal's ingested-at."""
        triage_dir = settings.paths.business_root / "_triage"
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        write_proposal(yml, _build_proposal(sha256=sha, triage_pdf=pdf))

        # _build_proposal pins ingested_at to a known datetime; freeze it here so
        # the assertion is independent of helper internals.
        proposal_ingested_at = datetime(2026, 5, 4, 9, 34, 22, tzinfo=timezone(timedelta(hours=2)))

        cmd, _ = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml,
            mocker=mocker,
            ocr_pdf=pdf,
        )

        result = cmd.execute()
        assert result.success is True

        zettel_path = Path(result.metadata["zettel_path"])
        text = zettel_path.read_text(encoding="utf-8")
        # Frontmatter is between the first two `---` fences.
        _, frontmatter_text, _ = text.split("---", 2)
        frontmatter = yaml.safe_load(frontmatter_text)

        zettel_ingested_at = frontmatter["ingested-at"]
        assert isinstance(zettel_ingested_at, datetime)
        assert zettel_ingested_at == proposal_ingested_at

    def test_promote_carries_proposal_summary_into_zettel_body(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """Regression for blind I1: promote must thread the triage proposal's
        summary into the zettel body so promoted-document bodies match the
        ingest path's body shape (PRD 00035 + post-blind follow-up).
        """
        triage_dir = settings.paths.business_root / "_triage"
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        summary_text = "Monthly electricity invoice for March 2021 from ČEZ a.s."
        write_proposal(yml, _build_proposal(sha256=sha, triage_pdf=pdf, summary=summary_text))

        cmd, _ = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml,
            mocker=mocker,
            ocr_pdf=pdf,
        )
        result = cmd.execute()
        assert result.success is True

        zettel_path = Path(result.metadata["zettel_path"])
        text = zettel_path.read_text(encoding="utf-8")
        # Body lives after the second `---` fence.
        _, _, body = text.split("---", 2)
        assert summary_text in body, "promoted zettel body must include the proposal summary"

    def test_promote_omits_summary_paragraph_when_proposal_summary_is_none(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        """When the proposal has no summary, the body must not insert filler.

        Mirrors ``build_zettel_body``'s contract that the summary paragraph is
        optional and entirely omitted when the source has no summary text.
        """
        triage_dir = settings.paths.business_root / "_triage"
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        write_proposal(yml, _build_proposal(sha256=sha, triage_pdf=pdf, summary=None))

        cmd, _ = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml,
            mocker=mocker,
            ocr_pdf=pdf,
        )
        result = cmd.execute()
        assert result.success is True

        zettel_path = Path(result.metadata["zettel_path"])
        text = zettel_path.read_text(encoding="utf-8")
        _, _, body = text.split("---", 2)
        body_lines = body.split("\n")
        h1_idx = next(i for i, line in enumerate(body_lines) if line.startswith("# "))
        assert body_lines[h1_idx + 1] == ""
        assert body_lines[h1_idx + 2] == "## OCR text"


class TestPromoteValidatesYAMLSchema:
    """Sanity check that round-tripped YAML reload works for the proposals we build."""

    def test_proposal_yaml_round_trip(self, tmp_path: Path) -> None:
        triage_dir = tmp_path / "_triage"
        pdf, yml = _stage_triage_pair(triage_dir, "stub-name")
        proposal = _build_proposal(sha256="0" * 64, triage_pdf=pdf)
        write_proposal(yml, proposal)
        loaded = yaml.safe_load(yml.read_text(encoding="utf-8"))
        assert loaded["approved"] is True
        assert loaded["issuer"]["slug"] == "cez-as"
        assert loaded["document"]["type"] == "invoice"


class TestValidIngestSourcesDerivation:
    """Pin the derivation contract between the IngestSource Literal and
    the runtime ``_VALID_INGEST_SOURCES`` guard. If someone hand-edits the
    tuple instead of letting ``get_args(IngestSource)`` populate it, this
    test fails immediately so the guard cannot silently lag the type.
    """

    def test_runtime_tuple_mirrors_literal(self) -> None:
        from typing import get_args

        from bim.commands.doc.promote.promote import _VALID_INGEST_SOURCES
        from bim.commands.doc.shared.zettel_writer import IngestSource

        assert _VALID_INGEST_SOURCES == get_args(IngestSource)

    def test_runtime_tuple_includes_documented_kinds(self) -> None:
        # Documented kinds that downstream code (and the spec) rely on.
        from bim.commands.doc.promote.promote import _VALID_INGEST_SOURCES

        assert "email" in _VALID_INGEST_SOURCES
        assert "scan" in _VALID_INGEST_SOURCES
        assert "issuer-inbox" in _VALID_INGEST_SOURCES


class TestCommandPromoteRuleMatchRecording:
    """``CommandPromote`` refreshes ``state_db.rule_matches`` when the
    proposal carries an ``applied_rule_id`` (set by the pipeline when triage
    was the outcome of a rule-engine ``full``/``partial`` match).
    Pre-existing proposals without the field skip the refresh entirely.
    """

    def test_records_rule_match_when_applied_rule_id_set(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        triage_dir = settings.paths.business_root / "_triage"
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        proposal = _build_proposal(sha256=sha, triage_pdf=pdf).model_copy(
            update={"applied_rule_id": "cez-invoice-2021-template"}
        )
        write_proposal(yml, proposal)

        before = datetime.now(timezone.utc)
        cmd, _ = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml,
            mocker=mocker,
            ocr_pdf=pdf,
        )

        result = cmd.execute()
        assert result.success is True

        recorded = state_db.get_rule_last_matches()
        assert "cez-invoice-2021-template" in recorded
        # Recorded timestamp is at-or-after the moment we captured before run.
        assert recorded["cez-invoice-2021-template"] >= before

    def test_no_rule_match_recorded_when_applied_rule_id_none(
        self,
        settings: DocSettings,
        registry_path: Path,
        lock_path: Path,
        state_db: StateDB,
        mocker: MockerFixture,
    ) -> None:
        triage_dir = settings.paths.business_root / "_triage"
        pdf, yml = _stage_triage_pair(triage_dir, "20210311083422-cez-as-7102105594.invoice")
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        # Default ``_build_proposal`` leaves ``applied_rule_id=None``.
        write_proposal(yml, _build_proposal(sha256=sha, triage_pdf=pdf))

        cmd, _ = _build_command(
            settings=settings,
            registry_path=registry_path,
            lock_path=lock_path,
            state_db=state_db,
            proposal_yml=yml,
            mocker=mocker,
            ocr_pdf=pdf,
        )

        result = cmd.execute()
        assert result.success is True
        assert state_db.get_rule_last_matches() == {}
