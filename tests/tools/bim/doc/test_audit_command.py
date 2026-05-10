"""Tests for CommandAudit.

CommandAudit composes the Auditor + JSON reporter into a CommandResult.
The audit is read-only: state.db must never be modified, and the command
should succeed even when issuers.yml is malformed (the malformedness
surfaces as rule_findings inside the report).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bim.commands.doc.audit import AuditServices, CommandAudit
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

_VALID_ISSUERS_YML = """
version: 1
doc_types: [invoice, statement]
reserved_slugs: [unknown]
issuers:
  cez-as:
    display_name: ČEZ a.s.
    rules:
      - id: rule-1
        match: {ocr_contains: [foo]}
        extract: {doc_type: invoice}
"""


def _ok_ocr(_path: Path) -> tuple[bool, float | None]:
    return (True, 0.85)


def _make_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-fake")


def _make_zettel(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nid: test\n---\nbody\n")


def _record_processed(state_db: StateDB, sha: str) -> None:
    state_db.record_processed(
        ProcessedRow(
            sha256=sha,
            canonical_filename=CANONICAL_PDF,
            issuer_slug="cez-as",
            doc_type="invoice",
            processed_at=FIXED_NOW,
            extraction_method="manual",
        )
    )


@dataclass(frozen=True)
class _Fixture:
    services: AuditServices
    business_root: Path
    vault_root: Path
    state_db: StateDB
    issuers_path: Path
    state_dir: Path


def _build_clean_fixture(tmp_path: Path) -> _Fixture:
    business_root = tmp_path / "business"
    vault_root = tmp_path / "vault"
    business_root.mkdir()
    vault_root.mkdir()

    pdf = business_root / "cez-as" / CANONICAL_PDF
    _make_pdf(pdf)
    _make_zettel(vault_root / "Zettelkasten" / "documents" / "cez-as" / CANONICAL_MD)

    state_db = open_state_db(tmp_path / "state.db")
    _record_processed(state_db, sha256_file(pdf))

    issuers_path = tmp_path / "issuers.yml"
    issuers_path.write_text(_VALID_ISSUERS_YML)

    state_dir = tmp_path / "state"
    services = AuditServices(
        state_db=state_db,
        business_root=business_root,
        vault_root=vault_root,
        vault_documents_subdir="Zettelkasten/documents",
        issuers_path=issuers_path,
        state_dir=state_dir,
        low_confidence_threshold=0.7,
        ocr_quality_reader=_ok_ocr,
        hash_reader=sha256_file,
    )
    return _Fixture(
        services=services,
        business_root=business_root,
        vault_root=vault_root,
        state_db=state_db,
        issuers_path=issuers_path,
        state_dir=state_dir,
    )


def _snapshot_state_db(state_db: StateDB) -> dict[str, list[tuple[object, ...]]]:
    conn = state_db.connection
    return {
        "processed": list(conn.execute("SELECT * FROM processed").fetchall()),
        "originals": list(conn.execute("SELECT * FROM originals").fetchall()),
        "claims": list(conn.execute("SELECT * FROM claims").fetchall()),
        "rule_matches": list(conn.execute("SELECT * FROM rule_matches").fetchall()),
    }


class TestExecuteSuccess:
    def test_execute_clean_audit_returns_success(self, tmp_path: Path) -> None:
        fx = _build_clean_fixture(tmp_path)
        result = CommandAudit(services=fx.services).execute()

        assert result.success is True
        assert result.metadata["walked_pdf_count"] == 1
        assert result.metadata["clean_pdf_count"] == 1
        assert isinstance(result.metadata["report"], AuditReport)

    def test_execute_writes_json_report(self, tmp_path: Path) -> None:
        fx = _build_clean_fixture(tmp_path)
        result = CommandAudit(services=fx.services).execute()

        report_path = Path(result.metadata["report_path"])
        assert report_path.is_file()
        payload = json.loads(report_path.read_text())
        assert payload["walked_pdf_count"] == 1
        assert payload["clean_pdf_count"] == 1


class TestExecuteFindings:
    def test_execute_legacy_layout_in_metadata_count(self, tmp_path: Path) -> None:
        fx = _build_clean_fixture(tmp_path)
        per_issuer_md = fx.vault_root / "Zettelkasten" / "documents" / "cez-as" / CANONICAL_MD
        per_issuer_md.unlink()
        legacy_md = fx.vault_root / "Zettelkasten" / "documents" / CANONICAL_MD
        _make_zettel(legacy_md)

        result = CommandAudit(services=fx.services).execute()

        assert result.success is True
        assert result.metadata["legacy_layout_count"] == 1

        payload = json.loads(Path(result.metadata["report_path"]).read_text())
        assert payload["legacy_layout_zettels"] == [str(legacy_md)]

    def test_execute_passes_through_findings(self, tmp_path: Path) -> None:
        fx = _build_clean_fixture(tmp_path)
        zettel = fx.vault_root / "Zettelkasten" / "documents" / "cez-as" / CANONICAL_MD
        zettel.unlink()

        result = CommandAudit(services=fx.services).execute()

        report = result.metadata["report"]
        codes = {f.code for f in report.pdf_findings}
        assert "missing_zettel" in codes

        payload = json.loads(Path(result.metadata["report_path"]).read_text())
        json_codes = {f["code"] for f in payload["pdf_findings"]}
        assert "missing_zettel" in json_codes


class TestExecuteResilience:
    def test_execute_with_invalid_issuers_yml_still_succeeds(self, tmp_path: Path) -> None:
        fx = _build_clean_fixture(tmp_path)
        fx.issuers_path.write_text("!!! not valid yaml ::: [\n")

        result = CommandAudit(services=fx.services).execute()

        assert result.success is True
        assert Path(result.metadata["report_path"]).is_file()
        assert len(result.metadata["validation_errors"]) >= 1

    def test_execute_uses_injected_now_provider(self, tmp_path: Path) -> None:
        fx = _build_clean_fixture(tmp_path)
        fixed = datetime(2030, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

        result = CommandAudit(
            services=fx.services,
            now_provider=lambda: fixed,
        ).execute()

        payload = json.loads(Path(result.metadata["report_path"]).read_text())
        assert payload["generated_at"] == fixed.isoformat()

    def test_execute_state_db_unchanged(self, tmp_path: Path) -> None:
        fx = _build_clean_fixture(tmp_path)
        before = _snapshot_state_db(fx.state_db)

        CommandAudit(services=fx.services).execute()

        after = _snapshot_state_db(fx.state_db)
        assert before == after


class TestExecuteFailure:
    def test_execute_failure_when_state_dir_not_writable(self, tmp_path: Path) -> None:
        fx = _build_clean_fixture(tmp_path)
        blocking_file = tmp_path / "blocking_file"
        blocking_file.write_text("x")
        bad_services = AuditServices(
            state_db=fx.services.state_db,
            business_root=fx.services.business_root,
            vault_root=fx.services.vault_root,
            vault_documents_subdir=fx.services.vault_documents_subdir,
            issuers_path=fx.services.issuers_path,
            state_dir=blocking_file / "audit_state",
            low_confidence_threshold=fx.services.low_confidence_threshold,
            ocr_quality_reader=fx.services.ocr_quality_reader,
            hash_reader=fx.services.hash_reader,
        )

        result = CommandAudit(services=bad_services).execute()

        assert result.success is False
        assert result.error is not None
        assert "report write failed" in result.error.lower()
