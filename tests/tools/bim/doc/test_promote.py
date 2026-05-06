from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from bim.commands.doc.promote.promote import CommandPromote, PromoteServices
from bim.commands.doc.shared.issuers import load_registry
from bim.commands.doc.shared.ocr import OCRResult
from bim.commands.doc.shared.settings_models import (
    ClassifierSettings,
    DocPaths,
    DocSettings,
    OCRSettings,
    ZettelSettings,
)
from bim.commands.doc.shared.state_db import StateDB
from bim.commands.doc.shared.triage import (
    DocumentProposal,
    IssuerProposal,
    OCRProposal,
    SourceProposal,
    TriageProposal,
    ZettelPreview,
    write_proposal,
)
from bim.commands.doc.shared.zettel_writer import ZettelWriter
from bim.params.doc_promote import PromoteParams
from buvis.pybase.result import CommandResult
from pytest_mock import MockerFixture

FIXTURES = Path(__file__).parent / "fixtures"


# ----------------------- helpers -----------------------


def _make_settings(tmp_path: Path) -> DocSettings:
    paths = DocPaths.model_validate(
        {
            "business_root": str(tmp_path / "Business"),
            "vault_root": str(tmp_path / "Vault"),
            "vault_documents_subdir": "Zettelkasten/documents",
            "state_dir": str(tmp_path / "state"),
        }
    )
    return DocSettings(
        paths=paths,
        ocr=OCRSettings(),
        classifier=ClassifierSettings(),
        zettel=ZettelSettings(),
    )


def _build_proposal(
    *,
    sha256: str,
    triage_pdf: Path,
    approved: bool = True,
    register_issuer: bool = False,
    issuer_slug: str = "cez-as",
    issuer_display: str = "ČEZ a.s.",
    doc_type: str = "invoice",
    doc_number: str | None = "7102105594",
    doc_date: date | None = date(2021, 3, 11),
) -> TriageProposal:
    return TriageProposal(
        approved=approved,
        register_issuer=register_issuer,
        issuer=IssuerProposal(
            slug=issuer_slug,
            display_name=issuer_display,
            confidence=0.62,
            alternatives=[],
        ),
        document=DocumentProposal(
            type=doc_type,
            number=doc_number,
            date=doc_date,
            title=None,
            amount=4218.0,
            currency="CZK",
            language="cs",
        ),
        source=SourceProposal(
            kind="email",
            staging_path=triage_pdf,
            email_msgid="<x@y.cz>",
            email_from="noreply@cez.cz",
            email_subject="Faktura 02/2021",
            original_filename="invoice.pdf",
            sha256=sha256,
        ),
        ocr=OCRProposal(
            engine="tesseract",
            languages=["ces", "eng"],
            mean_confidence=0.91,
            pages=2,
        ),
        triage_reasons=["confidence below threshold"],
        zettel_preview=ZettelPreview(
            id="20260504093422",
            ingest_date=date(2026, 5, 4),
            tags=[f"document/{doc_type}", f"issuer/{issuer_slug}", "year/2021"],
        ),
    )


def _ocr_result_for(pdf_path: Path) -> OCRResult:
    return OCRResult(
        ocr_text="ČEZ a.s.\nFaktura č. 7102105594\nDatum vystavení: 11.03.2021\n",
        pdf_path=pdf_path,
        was_redone=False,
        original_backup_path=None,
        mean_confidence=0.91,
        pages=2,
    )


def _stage_triage_pair(triage_dir: Path, basename: str) -> tuple[Path, Path]:
    """Write a fake triage PDF + return ``(pdf_path, proposal_yml_path)``."""
    triage_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = triage_dir / f"{basename}.pdf"
    proposal_path = triage_dir / f"{basename}.pdf.proposed.yml"
    pdf_path.write_bytes(b"%PDF-1.4\nfake triage pdf\n")
    return pdf_path, proposal_path


@pytest.fixture
def settings(tmp_path: Path) -> DocSettings:
    s = _make_settings(tmp_path)
    s.paths.business_root.mkdir(parents=True, exist_ok=True)
    return s


@pytest.fixture
def registry_path(tmp_path: Path) -> Path:
    src = FIXTURES / "issuers" / "with_aliases.yml"
    dst = tmp_path / "issuers.yml"
    dst.write_bytes(src.read_bytes())
    return dst


@pytest.fixture
def lock_path(tmp_path: Path) -> Path:
    return tmp_path / "issuers.lock"


@pytest.fixture
def state_db(tmp_path: Path) -> StateDB:
    return StateDB.open(tmp_path / "state" / "state.db")


def _build_command(
    *,
    settings: DocSettings,
    registry_path: Path,
    lock_path: Path,
    state_db: StateDB,
    proposal_yml: Path,
    mocker: MockerFixture,
    ocr_pdf: Path,
) -> tuple[CommandPromote, dict[str, Any]]:
    from bim.commands.doc.shared.ocr import OCRRunner

    registry = load_registry(registry_path)
    ocr_runner = OCRRunner(settings=settings, state_dir=settings.paths.state_dir)
    ocr_mock = mocker.patch.object(ocr_runner, "run", return_value=_ocr_result_for(ocr_pdf))
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
        params=PromoteParams(proposed_yml_path=proposal_yml),
        settings=settings,
        services=services,
    )
    return cmd, {"ocr": ocr_mock}


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
        assert zettel_path.parent == settings.paths.vault_root / "Zettelkasten" / "documents"

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
