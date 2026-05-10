"""Tests for the audit Auditor orchestrator.

The Auditor composes walker + pdf_checks + rules_checks into a read-only
audit pass over the business root. These tests focus on the orchestration
contract: clean/legacy counting, finding aggregation, inbox/triage rollup,
total counts, registry-load-failure resilience, and the read-only invariant.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest
from bim.commands.doc.audit.auditor import Auditor
from bim.commands.doc.audit.models import AuditReport
from bim.commands.doc.shared.hashing import sha256_file
from bim.commands.doc.shared.state_db import (
    ProcessedRow,
    StateDB,
    open_state_db,
)

FIXED_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
CANONICAL_PDF = "20260101000000-cez-as-foo.invoice.pdf"
CANONICAL_MD = "20260101000000-cez-as-foo.invoice.md"


def _ok_ocr(_path: Path) -> tuple[bool, float | None]:
    return (True, 0.85)


def _write_issuers_yml(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def _basic_issuers_yml(path: Path) -> None:
    _write_issuers_yml(
        path,
        """
version: 1
doc_types: [invoice, statement]
reserved_slugs: [unknown]
issuers:
  cez-as:
    display_name: ČEZ a.s.
""",
    )


def _make_pdf(path: Path, body: bytes = b"%PDF-fake") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def _make_zettel(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nid: test\n---\nbody\n")


def _record_processed(state_db: StateDB, sha: str, *, slug: str = "cez-as") -> None:
    state_db.record_processed(
        ProcessedRow(
            sha256=sha,
            canonical_filename=CANONICAL_PDF,
            issuer_slug=slug,
            doc_type="invoice",
            processed_at=FIXED_NOW,
            extraction_method="manual",
        )
    )


@dataclass(frozen=True)
class AuditorFactory:
    """Builds an Auditor over a tmp tree, exposing business/vault paths."""

    business: Path
    vault: Path
    state_db: StateDB

    def build(
        self,
        *,
        ocr_quality_reader: Callable[[Path], tuple[bool, float | None]] = _ok_ocr,
        low_confidence_threshold: float = 0.7,
        hash_reader: Callable[[Path], str] = sha256_file,
        now: datetime = FIXED_NOW,
    ) -> Auditor:
        return Auditor(
            state_db=self.state_db,
            business_root=self.business,
            vault_root=self.vault,
            vault_documents_subdir="Zettelkasten/documents",
            low_confidence_threshold=low_confidence_threshold,
            ocr_quality_reader=ocr_quality_reader,
            hash_reader=hash_reader,
            now_provider=lambda: now,
        )


@pytest.fixture
def state_db(tmp_path: Path) -> StateDB:
    return open_state_db(tmp_path / "s.db")


@pytest.fixture
def factory(tmp_path: Path, state_db: StateDB) -> AuditorFactory:
    business = tmp_path / "business"
    vault = tmp_path / "vault"
    business.mkdir()
    vault.mkdir()
    return AuditorFactory(business=business, vault=vault, state_db=state_db)


def _docs_dir(vault: Path) -> Path:
    return vault / "Zettelkasten" / "documents"


class TestCleanAndLegacy:
    def test_clean_pdf_no_findings_no_legacy(self, tmp_path: Path, factory: AuditorFactory, state_db: StateDB) -> None:
        pdf = factory.business / "cez-as" / CANONICAL_PDF
        _make_pdf(pdf)
        _make_zettel(_docs_dir(factory.vault) / "cez-as" / CANONICAL_MD)
        _record_processed(state_db, sha256_file(pdf))

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build().run(issuers)
        assert report.walked_pdf_count == 1
        assert report.clean_pdf_count == 1
        assert report.pdf_findings == ()
        assert report.legacy_layout_zettels == ()

    def test_legacy_layout_pdf_populates_legacy_list(
        self, tmp_path: Path, factory: AuditorFactory, state_db: StateDB
    ) -> None:
        pdf = factory.business / "cez-as" / CANONICAL_PDF
        _make_pdf(pdf)
        legacy_md = _docs_dir(factory.vault) / CANONICAL_MD
        _make_zettel(legacy_md)
        _record_processed(state_db, sha256_file(pdf))

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build().run(issuers)
        assert report.walked_pdf_count == 1
        assert report.clean_pdf_count == 0  # legacy is not clean
        assert all(f.code != "missing_zettel" for f in report.pdf_findings)
        assert report.legacy_layout_zettels == (str(legacy_md),)

    def test_missing_zettel_emits_finding(self, tmp_path: Path, factory: AuditorFactory, state_db: StateDB) -> None:
        pdf = factory.business / "cez-as" / CANONICAL_PDF
        _make_pdf(pdf)
        _record_processed(state_db, sha256_file(pdf))

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build().run(issuers)
        codes = {f.code for f in report.pdf_findings}
        assert "missing_zettel" in codes
        assert report.legacy_layout_zettels == ()


class TestPerPdfFindings:
    def test_unknown_issuer_folder(self, tmp_path: Path, factory: AuditorFactory) -> None:
        pdf = factory.business / "unknown-folder" / "20260101000000-foo-bar.invoice.pdf"
        _make_pdf(pdf)

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build().run(issuers)
        codes = [f.code for f in report.pdf_findings]
        assert "unknown_issuer" in codes

    def test_non_canonical_filename(self, tmp_path: Path, factory: AuditorFactory) -> None:
        pdf = factory.business / "cez-as" / "notcanonical.pdf"
        _make_pdf(pdf)

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build().run(issuers)
        codes = [f.code for f in report.pdf_findings]
        assert "non_canonical_filename" in codes

    def test_missing_ocr_finding(self, tmp_path: Path, factory: AuditorFactory, state_db: StateDB) -> None:
        pdf = factory.business / "cez-as" / CANONICAL_PDF
        _make_pdf(pdf)
        _record_processed(state_db, sha256_file(pdf))

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build(ocr_quality_reader=lambda _p: (False, None)).run(issuers)
        codes = [f.code for f in report.pdf_findings]
        assert "missing_ocr" in codes

    def test_low_ocr_confidence(self, tmp_path: Path, factory: AuditorFactory, state_db: StateDB) -> None:
        pdf = factory.business / "cez-as" / CANONICAL_PDF
        _make_pdf(pdf)
        _record_processed(state_db, sha256_file(pdf))

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build(
            ocr_quality_reader=lambda _p: (True, 0.5),
            low_confidence_threshold=0.7,
        ).run(issuers)
        codes = [f.code for f in report.pdf_findings]
        assert "low_ocr_confidence" in codes

    def test_missing_state_db_entry(self, tmp_path: Path, factory: AuditorFactory) -> None:
        pdf = factory.business / "cez-as" / CANONICAL_PDF
        _make_pdf(pdf)
        _make_zettel(_docs_dir(factory.vault) / "cez-as" / CANONICAL_MD)

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build().run(issuers)
        codes = [f.code for f in report.pdf_findings]
        assert "missing_state_db_entry" in codes


class TestInboxesAndTriage:
    def test_inbox_summary_emitted(self, tmp_path: Path, factory: AuditorFactory) -> None:
        inbox_pdf = factory.business / "cez-as" / "inbox" / "pending.pdf"
        _make_pdf(inbox_pdf)

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build().run(issuers)
        assert len(report.issuer_inboxes) == 1
        summary = report.issuer_inboxes[0]
        assert summary.unprocessed_count == 1
        assert summary.path.endswith("cez-as/inbox")
        # Walker must have skipped the inbox PDF entirely.
        assert report.walked_pdf_count == 0

    def test_inbox_skipped_when_empty(self, tmp_path: Path, factory: AuditorFactory) -> None:
        empty_inbox = factory.business / "cez-as" / "inbox"
        empty_inbox.mkdir(parents=True)

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build().run(issuers)
        assert report.issuer_inboxes == ()

    def test_triage_count(self, tmp_path: Path, factory: AuditorFactory) -> None:
        triage = factory.business / "_triage"
        triage.mkdir()
        (triage / "x.proposed.yml").write_text("a: 1\n")
        (triage / "y.proposed.yml").write_text("b: 2\n")
        (triage / "ignored.txt").write_text("noop")

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build().run(issuers)
        assert report.triage_pending == 2

    def test_triage_zero_when_dir_missing(self, tmp_path: Path, factory: AuditorFactory) -> None:
        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build().run(issuers)
        assert report.triage_pending == 0


class TestRegistryFailures:
    def test_registry_load_failure_continues_audit(self, tmp_path: Path, factory: AuditorFactory) -> None:
        pdf = factory.business / "cez-as" / "notcanonical.pdf"
        _make_pdf(pdf)

        # No issuers.yml on disk.
        issuers = tmp_path / "missing.yml"
        report = factory.build().run(issuers)

        rule_codes = {f.code for f in report.rule_findings}
        assert "validation_error" in rule_codes
        # PDF walk still happened.
        assert report.walked_pdf_count == 1
        # Filename check (registry-independent) ran.
        pdf_codes = {f.code for f in report.pdf_findings}
        assert "non_canonical_filename" in pdf_codes
        # Registry-dependent checks must NOT have run.
        assert "unknown_issuer" not in pdf_codes
        assert "invalid_doc_type" not in pdf_codes


class TestRuleFindings:
    def test_freshness_check_invokes_with_now_provider(
        self, tmp_path: Path, factory: AuditorFactory, state_db: StateDB
    ) -> None:
        _write_issuers_yml(
            tmp_path / "issuers.yml",
            """
version: 1
doc_types: [invoice]
reserved_slugs: [unknown]
issuers:
  cez-as:
    display_name: ČEZ a.s.
    rules:
      - id: rule-1
        match: {ocr_contains: [foo]}
        extract: {doc_type: invoice}
""",
        )
        state_db.record_rule_match("rule-1", datetime(2026, 1, 1, tzinfo=timezone.utc))

        report = factory.build().run(tmp_path / "issuers.yml")
        stale = [f for f in report.rule_findings if f.code == "stale_rule"]
        assert len(stale) == 1
        assert stale[0].rule_id == "rule-1"
        assert "129 days" in stale[0].detail

    def test_priority_conflict_surfaces(self, tmp_path: Path, factory: AuditorFactory) -> None:
        _write_issuers_yml(
            tmp_path / "issuers.yml",
            """
version: 1
doc_types: [invoice, statement]
reserved_slugs: [unknown]
issuers:
  cez-as:
    display_name: ČEZ a.s.
    rules:
      - id: rule-a
        priority: 50
        match: {ocr_contains: [foo]}
        extract: {doc_type: invoice}
      - id: rule-b
        priority: 50
        match: {ocr_contains: [bar]}
        extract: {doc_type: statement}
""",
        )

        report = factory.build().run(tmp_path / "issuers.yml")
        codes = {f.code for f in report.rule_findings}
        assert "priority_conflict" in codes

    def test_total_rule_and_issuer_counts_populated(self, tmp_path: Path, factory: AuditorFactory) -> None:
        _write_issuers_yml(
            tmp_path / "issuers.yml",
            """
version: 1
doc_types: [invoice, statement]
reserved_slugs: [unknown]
issuers:
  cez-as:
    display_name: ČEZ a.s.
    rules:
      - id: r1
        match: {ocr_contains: [a]}
        extract: {doc_type: invoice}
      - id: r2
        match: {ocr_contains: [b]}
        extract: {doc_type: statement}
  acme:
    display_name: Acme
    rules:
      - id: r3
        match: {ocr_contains: [c]}
        extract: {doc_type: invoice}
""",
        )

        report = factory.build().run(tmp_path / "issuers.yml")
        assert report.total_issuers_in_registry == 2
        assert report.total_rules_in_registry == 3


class TestAdapterFailures:
    """When the OCR-quality reader or hash reader raises, the auditor must
    surface the failure as a finding rather than silently treating the PDF
    as clean. The PRD's "failure modes report; they do not auto-heal"
    invariant requires this.
    """

    def test_ocr_reader_exception_emits_ocr_check_failed(
        self,
        tmp_path: Path,
        factory: AuditorFactory,
        state_db: StateDB,
    ) -> None:
        pdf = factory.business / "cez-as" / CANONICAL_PDF
        _make_pdf(pdf)
        _make_zettel(_docs_dir(factory.vault) / "cez-as" / CANONICAL_MD)
        _record_processed(state_db, sha256_file(pdf))

        def _boom_ocr(_path: Path) -> tuple[bool, float | None]:
            raise OSError("permission denied")

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)
        report = factory.build(ocr_quality_reader=_boom_ocr).run(issuers)

        ocr_failures = [f for f in report.pdf_findings if f.code == "ocr_check_failed"]
        assert len(ocr_failures) == 1
        finding = ocr_failures[0]
        assert finding.pdf_path == str(pdf)
        assert finding.issuer_slug == "cez-as"
        assert finding.detail is not None
        assert "OSError" in finding.detail
        assert "permission denied" in finding.detail
        # PDF with adapter failure does NOT count as clean.
        assert report.clean_pdf_count == 0

    def test_hash_reader_exception_emits_hash_check_failed_and_skips_state_db_check(
        self,
        tmp_path: Path,
        factory: AuditorFactory,
        state_db: StateDB,
    ) -> None:
        pdf = factory.business / "cez-as" / CANONICAL_PDF
        _make_pdf(pdf)
        _make_zettel(_docs_dir(factory.vault) / "cez-as" / CANONICAL_MD)
        # Note: no record_processed call, so missing_state_db_entry would
        # normally fire; but hash failure short-circuits the check.

        def _boom_hash(_path: Path) -> str:
            raise OSError("read failed")

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)
        report = factory.build(hash_reader=_boom_hash).run(issuers)

        hash_failures = [f for f in report.pdf_findings if f.code == "hash_check_failed"]
        assert len(hash_failures) == 1
        finding = hash_failures[0]
        assert finding.pdf_path == str(pdf)
        assert finding.issuer_slug == "cez-as"
        assert finding.detail is not None
        assert "OSError" in finding.detail
        # state_db check skipped when hash failed -- no missing_state_db_entry.
        missing_state = [f for f in report.pdf_findings if f.code == "missing_state_db_entry"]
        assert missing_state == []
        assert report.clean_pdf_count == 0


class TestReadOnlyInvariant:
    def test_state_db_unmodified(self, tmp_path: Path, factory: AuditorFactory, state_db: StateDB) -> None:
        pdf = factory.business / "cez-as" / CANONICAL_PDF
        _make_pdf(pdf)
        _make_zettel(_docs_dir(factory.vault) / "cez-as" / CANONICAL_MD)
        _record_processed(state_db, sha256_file(pdf))
        state_db.record_rule_match("rule-1", datetime(2026, 1, 1, tzinfo=timezone.utc))

        def _snapshot() -> dict[str, list[tuple[object, ...]]]:
            conn = state_db.connection
            return {
                "processed": list(conn.execute("SELECT * FROM processed").fetchall()),
                "originals": list(conn.execute("SELECT * FROM originals").fetchall()),
                "claims": list(conn.execute("SELECT * FROM claims").fetchall()),
                "rule_matches": list(conn.execute("SELECT * FROM rule_matches").fetchall()),
            }

        before = _snapshot()
        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)
        factory.build().run(issuers)
        after = _snapshot()
        assert before == after


class TestIssuersWalkedCount:
    def test_n_issuers_walked_count(self, tmp_path: Path, factory: AuditorFactory) -> None:
        _make_pdf(factory.business / "cez-as" / CANONICAL_PDF)
        _make_pdf(factory.business / "acme" / "20260101000000-acme-foo.invoice.pdf")

        _write_issuers_yml(
            tmp_path / "issuers.yml",
            """
version: 1
doc_types: [invoice]
reserved_slugs: [unknown]
issuers:
  cez-as:
    display_name: ČEZ a.s.
  acme:
    display_name: Acme
""",
        )

        report = factory.build().run(tmp_path / "issuers.yml")
        assert report.n_issuers_walked == 2

    def test_top_level_pdf_contributes_empty_slug(self, tmp_path: Path, factory: AuditorFactory) -> None:
        _make_pdf(factory.business / "cez-as" / CANONICAL_PDF)
        _make_pdf(factory.business / "loose.pdf")

        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)

        report = factory.build().run(issuers)
        # cez-as + "" => 2 distinct slugs walked
        assert report.n_issuers_walked == 2


class TestReportShape:
    def test_returns_audit_report_with_aware_now(self, tmp_path: Path, factory: AuditorFactory) -> None:
        issuers = tmp_path / "issuers.yml"
        _basic_issuers_yml(issuers)
        report = factory.build().run(issuers)
        assert isinstance(report, AuditReport)
        assert report.generated_at == FIXED_NOW
