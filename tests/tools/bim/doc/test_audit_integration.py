"""End-to-end integration test for ``bim doc audit``.

Builds a single fixture exercising every audit category in one run, then
asserts the PRD's success metrics directly against the report produced
by :class:`CommandAudit`. Uses the real ``StateDB``, real walker, real
reporter; only the OCR-quality reader is stubbed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bim.commands.doc.audit import AuditServices, CommandAudit
from bim.commands.doc.audit.models import AuditReport, PdfFinding
from bim.commands.doc.shared.hashing import sha256_file
from bim.commands.doc.shared.state_db import (
    ProcessedRow,
    StateDB,
    open_state_db,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIXED_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
R_RECENT_MATCHED_AT = datetime(2026, 5, 5, tzinfo=timezone.utc)  # 5 days before FIXED_NOW

CANONICAL_CLEAN_PDF = "20260101000000-cez-as-foo.invoice.pdf"
CANONICAL_LEGACY_PDF = "20260101000001-cez-as-bar.statement.pdf"
CANONICAL_MISSING_ZETTEL_PDF = "20260101000002-cez-as-baz.invoice.pdf"
NON_CANONICAL_PDF = "notcanonical.pdf"
CANONICAL_O2_PDF = "20260101000003-o2-czech-x.invoice.pdf"
CANONICAL_UNKNOWN_FOLDER_PDF = "20260101000004-unknown-folder-z.invoice.pdf"
INBOX_PDF = "pending.pdf"

ISSUERS_YML = """
version: 1
doc_types: [invoice, receipt, statement, contract, certificate, reminder, correspondence, other]
reserved_slugs: []
issuers:
  cez-as:
    display_name: "ČEZ a.s."
    rules:
      - id: r-recent
        priority: 50
        match:
          ocr_contains: ["cez"]
        extract:
          doc_type: invoice
  o2-czech:
    display_name: "O2 Czech Republic"
    rules:
      - id: r-stale
        priority: 60
        match:
          ocr_contains: ["o2"]
        extract:
          doc_type: invoice
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stub_ocr(pdf_path: Path) -> tuple[bool, float | None]:
    """Map a PDF to OCR quality based on its parent folder.

    The o2-czech PDF returns ``(False, None)`` to trigger the
    ``missing_ocr`` finding; everything else gets a clean OCR signal.
    """
    if pdf_path.parent.name == "o2-czech":
        return (False, None)
    return (True, 0.85)


def _make_pdf(path: Path, body: bytes = b"%PDF-fake") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def _make_zettel(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nid: test\n---\nbody\n")


def _snapshot_state_db(state_db: StateDB) -> dict[str, list[tuple[object, ...]]]:
    conn = state_db.connection
    return {
        "processed": list(conn.execute("SELECT * FROM processed").fetchall()),
        "originals": list(conn.execute("SELECT * FROM originals").fetchall()),
        "claims": list(conn.execute("SELECT * FROM claims").fetchall()),
        "rule_matches": list(conn.execute("SELECT * FROM rule_matches").fetchall()),
    }


@dataclass(frozen=True)
class _Fixture:
    services: AuditServices
    business_root: Path
    vault_root: Path
    vault_docs_dir: Path
    state_db: StateDB
    state_dir: Path
    clean_pdf: Path
    legacy_pdf: Path
    missing_zettel_pdf: Path
    non_canonical_pdf: Path
    o2_pdf: Path
    unknown_folder_pdf: Path
    inbox_pdf: Path
    triage_proposal: Path
    legacy_zettel: Path


def _build_full_fixture(tmp_path: Path) -> _Fixture:
    """Build a fixture that exercises every audit category in one run."""
    business_root = tmp_path / "business"
    vault_root = tmp_path / "vault"
    business_root.mkdir()
    vault_root.mkdir()

    cez_dir = business_root / "cez-as"
    o2_dir = business_root / "o2-czech"
    unknown_dir = business_root / "unknown-folder"
    inbox_dir = cez_dir / "inbox"
    triage_dir = business_root / "_triage"

    # Clean PDF (per-issuer zettel + state.db row): CLEAN
    clean_pdf = cez_dir / CANONICAL_CLEAN_PDF
    _make_pdf(clean_pdf, body=b"%PDF-clean")

    # Legacy-layout PDF (zettel only at flat path): LEGACY
    legacy_pdf = cez_dir / CANONICAL_LEGACY_PDF
    _make_pdf(legacy_pdf, body=b"%PDF-legacy")

    # Missing zettel PDF: MISSING_ZETTEL
    missing_zettel_pdf = cez_dir / CANONICAL_MISSING_ZETTEL_PDF
    _make_pdf(missing_zettel_pdf, body=b"%PDF-missing-zettel")

    # Non-canonical filename: NON_CANONICAL_FILENAME
    non_canonical_pdf = cez_dir / NON_CANONICAL_PDF
    _make_pdf(non_canonical_pdf, body=b"%PDF-non-canonical")

    # Issuer inbox PDF (must NOT be walked, just counted in inbox summary)
    inbox_pdf = inbox_dir / INBOX_PDF
    _make_pdf(inbox_pdf, body=b"%PDF-inbox")

    # OCR-missing PDF in o2-czech: MISSING_OCR
    o2_pdf = o2_dir / CANONICAL_O2_PDF
    _make_pdf(o2_pdf, body=b"%PDF-o2")

    # PDF in unknown-folder: UNKNOWN_ISSUER (folder not in registry)
    unknown_folder_pdf = unknown_dir / CANONICAL_UNKNOWN_FOLDER_PDF
    _make_pdf(unknown_folder_pdf, body=b"%PDF-unknown")

    # Triage proposal (must NOT be walked, just counted)
    triage_proposal = triage_dir / "x.proposed.yml"
    triage_dir.mkdir(parents=True, exist_ok=True)
    triage_proposal.write_text("issuer_slug: cez-as\n")

    # Vault zettels: per-issuer for clean, legacy flat for legacy_pdf
    vault_docs_dir = vault_root / "Zettelkasten" / "documents"
    clean_zettel = vault_docs_dir / "cez-as" / CANONICAL_CLEAN_PDF.replace(".pdf", ".md")
    _make_zettel(clean_zettel)
    legacy_zettel = vault_docs_dir / CANONICAL_LEGACY_PDF.replace(".pdf", ".md")
    _make_zettel(legacy_zettel)

    # State DB: record the clean PDF + r-recent match 5 days ago
    state_dir = tmp_path / "state"
    state_db_path = state_dir / "state.db"
    state_db = open_state_db(state_db_path)
    state_db.record_processed(
        ProcessedRow(
            sha256=sha256_file(clean_pdf),
            canonical_filename=clean_pdf.name,
            issuer_slug="cez-as",
            doc_type="invoice",
            processed_at=FIXED_NOW,
            extraction_method="rule:r-recent:v1",
        )
    )
    state_db.record_rule_match("r-recent", R_RECENT_MATCHED_AT)

    # issuers.yml
    issuers_path = tmp_path / "issuers.yml"
    issuers_path.write_text(ISSUERS_YML)

    services = AuditServices(
        state_db=state_db,
        business_root=business_root,
        vault_root=vault_root,
        vault_documents_subdir="Zettelkasten/documents",
        issuers_path=issuers_path,
        state_dir=state_dir,
        low_confidence_threshold=0.7,
        ocr_quality_reader=_stub_ocr,
        hash_reader=sha256_file,
    )
    return _Fixture(
        services=services,
        business_root=business_root,
        vault_root=vault_root,
        vault_docs_dir=vault_docs_dir,
        state_db=state_db,
        state_dir=state_dir,
        clean_pdf=clean_pdf,
        legacy_pdf=legacy_pdf,
        missing_zettel_pdf=missing_zettel_pdf,
        non_canonical_pdf=non_canonical_pdf,
        o2_pdf=o2_pdf,
        unknown_folder_pdf=unknown_folder_pdf,
        inbox_pdf=inbox_pdf,
        triage_proposal=triage_proposal,
        legacy_zettel=legacy_zettel,
    )


def _findings_for(report: AuditReport, pdf_path: Path) -> list[PdfFinding]:
    target = str(pdf_path)
    return [f for f in report.pdf_findings if f.pdf_path == target]


def _codes_for(report: AuditReport, pdf_path: Path) -> set[str]:
    return {f.code for f in _findings_for(report, pdf_path)}


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


class TestAuditE2EAgainstFullFixture:
    """One integration test exercising every audit category + PRD metrics."""

    def test_audit_e2e_against_full_fixture(self, tmp_path: Path) -> None:
        fx = _build_full_fixture(tmp_path)
        before_state = _snapshot_state_db(fx.state_db)

        result = CommandAudit(
            services=fx.services,
            now_provider=lambda: FIXED_NOW,
        ).execute()

        # ---- basic success path -------------------------------------------
        assert result.success is True
        report_path = Path(result.metadata["report_path"])
        assert report_path.is_file()
        report_json = json.loads(report_path.read_text())
        report = result.metadata["report"]
        assert isinstance(report, AuditReport)

        # ---- (1) clean PDF: no findings, contributes to clean_pdf_count ---
        assert _findings_for(report, fx.clean_pdf) == []
        assert report.clean_pdf_count >= 1

        # ---- (2) legacy layout (PRD 00036 contract) -----------------------
        assert len(report.legacy_layout_zettels) == 1
        assert report.legacy_layout_zettels[0] == str(fx.legacy_zettel)
        # The legacy PDF must NOT be flagged as missing_zettel.
        assert "missing_zettel" not in _codes_for(report, fx.legacy_pdf)
        # JSON exposes the same paths (PRD 00036 reads from JSON).
        assert report_json["legacy_layout_zettels"] == [str(fx.legacy_zettel)]
        # All legacy paths point to files that exist on disk.
        for legacy in report.legacy_layout_zettels:
            assert Path(legacy).is_file()

        # ---- (3) missing zettel -------------------------------------------
        assert "missing_zettel" in _codes_for(report, fx.missing_zettel_pdf)

        # ---- (4) non-canonical filename -----------------------------------
        assert "non_canonical_filename" in _codes_for(report, fx.non_canonical_pdf)

        # ---- (5) missing OCR ----------------------------------------------
        assert "missing_ocr" in _codes_for(report, fx.o2_pdf)

        # ---- (6) unknown issuer -------------------------------------------
        assert "unknown_issuer" in _codes_for(report, fx.unknown_folder_pdf)

        # ---- (7) triage + inboxes -----------------------------------------
        assert report.triage_pending == 1
        assert len(report.issuer_inboxes) == 1
        only_inbox = report.issuer_inboxes[0]
        assert only_inbox.path.endswith("cez-as/inbox")
        assert only_inbox.unprocessed_count == 1

        # ---- (8) rules block ----------------------------------------------
        assert report.total_issuers_in_registry == 2
        assert report.total_rules_in_registry == 2

        stale_findings = [f for f in report.rule_findings if f.code == "stale_rule"]
        assert len(stale_findings) == 1
        assert stale_findings[0].rule_id == "r-stale"

        # r-recent matched 5 days ago -> no stale finding for it.
        assert all(f.rule_id != "r-recent" for f in stale_findings)

        # No priority conflicts (different priorities).
        priority_conflicts = [f for f in report.rule_findings if f.code == "priority_conflict"]
        assert priority_conflicts == []

        # No validation_error / duplicate_id (registry is well-formed).
        validation_codes = {"validation_error", "duplicate_id", "regex_compile_failure"}
        validation_findings = [f for f in report.rule_findings if f.code in validation_codes]
        assert validation_findings == []

        # ---- (9) read-only invariant on state.db --------------------------
        after_state = _snapshot_state_db(fx.state_db)
        assert before_state == after_state

        # ---- (10) walked count + inbox/triage exclusion -------------------
        # 6 PDFs are walked: 4 under cez-as/ (clean, legacy, missing_zettel,
        # non_canonical), 1 under o2-czech/, 1 under unknown-folder/. The
        # inbox PDF and the triage proposal must be excluded from the walk.
        assert report.walked_pdf_count == 6
        assert report.n_issuers_walked >= 3
        # Partition invariant: clean + non_clean == walked. Catches the
        # double-counting trap from naively summing pdf_findings + legacy.
        assert report.clean_pdf_count + report.non_clean_pdf_count == report.walked_pdf_count

        # ---- (10a) missing_state_db_entry ---------------------------------
        # Only the clean PDF has a recorded ProcessedRow; every other walked
        # PDF must surface ``missing_state_db_entry``. Regression test for
        # the integration coverage gap where the ``check_state_db_entry``
        # failure path was never exercised end-to-end.
        for pdf in (
            fx.legacy_pdf,
            fx.missing_zettel_pdf,
            fx.non_canonical_pdf,
            fx.o2_pdf,
            fx.unknown_folder_pdf,
        ):
            assert "missing_state_db_entry" in _codes_for(report, pdf), pdf
        assert "missing_state_db_entry" not in _codes_for(report, fx.clean_pdf)

        # ---- (11) JSON shape sanity ---------------------------------------
        assert isinstance(report_json["legacy_layout_zettels"], list)
        assert all(isinstance(p, str) for p in report_json["legacy_layout_zettels"])
        assert isinstance(report_json["pdf_findings"], list)
        for entry in report_json["pdf_findings"]:
            assert set(entry.keys()) == {"pdf_path", "issuer_slug", "doc_type", "code", "detail"}
        # generated_at is an ISO 8601 string.
        parsed_generated_at = datetime.fromisoformat(report_json["generated_at"])
        assert parsed_generated_at == FIXED_NOW
        assert report_json["walked_pdf_count"] == 6
