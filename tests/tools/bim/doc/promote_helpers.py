"""Shared fixtures and setup helpers for promote's own test modules.

Kept out of the directory-wide ``conftest.py`` on purpose: the ``settings``/
``state_db``/``registry_path``/``lock_path`` names below are generic, and
promote's ``DocSettings`` (pre-``mkdir``'d ``business_root``) must not leak
to the other 55+ modules under ``tests/tools/bim/doc/`` that happen to omit
their own same-named fixture. Only ``test_promote.py`` and
``test_promote_collision.py`` should import from here.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
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
)
from bim.commands.doc.shared.zettel_writer import ZettelWriter
from bim.params.doc_promote import PromoteParams
from pytest_mock import MockerFixture

FIXTURES = Path(__file__).parent / "fixtures"


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


@pytest.fixture
def settings(tmp_path: Path) -> DocSettings:
    """Shared ``DocSettings`` fixture for ``test_promote.py`` and
    ``test_promote_collision.py`` (lifted here so both files can use it
    without duplicating the helper)."""
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
    summary: str | None = None,
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
            title=f"{issuer_display} {doc_type} {doc_number}" if doc_number else f"{issuer_display} {doc_type}",
            ingested_at=datetime(2026, 5, 4, 9, 34, 22, tzinfo=timezone(timedelta(hours=2))),
            tags=[f"document/{doc_type}", f"issuer/{issuer_slug}", "year/2021"],
            summary=summary,
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


def _advance_seconds(zk_timestamp: str, seconds: int) -> str:
    moment = datetime.strptime(zk_timestamp, "%Y%m%d%H%M%S")
    return (moment + timedelta(seconds=seconds)).strftime("%Y%m%d%H%M%S")
