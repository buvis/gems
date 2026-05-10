"""Unit tests for the audit reporter (stdout + JSON output)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bim.commands.doc.audit.models import (
    AuditReport,
    InboxSummary,
    PdfFinding,
    RuleFinding,
)
from bim.commands.doc.audit.reporter import render_stdout, write_json_report


class _CapturingConsole:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, msg: str, *, mode: str = "normal") -> None:
        self.lines.append(msg)


def _make_report(**overrides: Any) -> AuditReport:
    defaults: dict[str, Any] = {
        "walked_pdf_count": 20,
        "clean_pdf_count": 8,
        "pdf_findings": (),
        "legacy_layout_zettels": (),
        "rule_findings": (),
        "issuer_inboxes": (),
        "triage_pending": 0,
        "generated_at": datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc),
        "n_issuers_walked": 4,
        "total_rules_in_registry": 0,
        "total_issuers_in_registry": 0,
    }
    defaults.update(overrides)
    # Auto-derive ``non_clean_pdf_count`` to keep the partition invariant in
    # tests that don't care about it. Tests that pin a specific non-clean
    # value can override it explicitly.
    defaults.setdefault("non_clean_pdf_count", defaults["walked_pdf_count"] - defaults["clean_pdf_count"])
    return AuditReport(**defaults)


def _full_report() -> AuditReport:
    pdf_findings = (
        PdfFinding(
            pdf_path="/v/cez-as/inv-1.pdf",
            issuer_slug="cez-as",
            doc_type="invoice",
            code="missing_zettel",
            detail=None,
        ),
        PdfFinding(
            pdf_path="/v/cez-as/inv-2.pdf",
            issuer_slug="cez-as",
            doc_type="invoice",
            code="non_canonical_filename",
            detail="bad name",
        ),
        PdfFinding(
            pdf_path="/v/acme/x.pdf",
            issuer_slug="acme",
            doc_type=None,
            code="invalid_doc_type",
            detail="unknown",
        ),
        PdfFinding(
            pdf_path="/v/_orphan/a.pdf",
            issuer_slug=None,
            doc_type=None,
            code="unknown_issuer",
            detail=None,
        ),
        PdfFinding(
            pdf_path="/v/cez-as/inv-3.pdf",
            issuer_slug="cez-as",
            doc_type="invoice",
            code="missing_ocr",
            detail=None,
        ),
        PdfFinding(
            pdf_path="/v/cez-as/inv-4.pdf",
            issuer_slug="cez-as",
            doc_type="invoice",
            code="low_ocr_confidence",
            detail="0.42",
        ),
        PdfFinding(
            pdf_path="/v/cez-as/inv-5.pdf",
            issuer_slug="cez-as",
            doc_type="invoice",
            code="missing_state_db_entry",
            detail=None,
        ),
    )
    rule_findings = (
        RuleFinding(rule_id="r-1", code="validation_error", detail="bad regex"),
        RuleFinding(rule_id="r-2", code="duplicate_id", detail="dup id"),
        RuleFinding(rule_id=None, code="regex_compile_failure", detail="cannot compile"),
        RuleFinding(rule_id="r-3", code="priority_conflict", detail="conflict with r-4"),
        RuleFinding(rule_id="r-9", code="stale_rule", detail="not matched in 400 days"),
    )
    return _make_report(
        walked_pdf_count=20,
        clean_pdf_count=8,
        pdf_findings=pdf_findings,
        legacy_layout_zettels=("/v/zettels/old.md",),
        rule_findings=rule_findings,
        issuer_inboxes=(InboxSummary(path="/v/inbox/cez-as", unprocessed_count=3),),
        triage_pending=2,
        total_rules_in_registry=10,
        total_issuers_in_registry=5,
    )


class TestRenderStdout:
    def test_renders_header_with_walked_count(self) -> None:
        report = _make_report(walked_pdf_count=42, n_issuers_walked=7)
        cons = _CapturingConsole()
        render_stdout(report, cons)
        joined = "\n".join(cons.lines)
        assert "Walked 42 documents in 7 folders" in joined

    def test_renders_clean_count(self) -> None:
        report = _make_report(walked_pdf_count=20, clean_pdf_count=8)
        cons = _CapturingConsole()
        render_stdout(report, cons)
        assert any("8 clean" in line for line in cons.lines)

    def test_renders_legacy_layout_count(self) -> None:
        report = _make_report(
            legacy_layout_zettels=("/a.md", "/b.md", "/c.md"),
        )
        cons = _CapturingConsole()
        render_stdout(report, cons)
        assert any("3 legacy layout zettels" in line for line in cons.lines)

    def test_renders_each_pdf_finding_category_count(self) -> None:
        report = _full_report()
        cons = _CapturingConsole()
        render_stdout(report, cons)
        joined = "\n".join(cons.lines)
        assert "1 missing zettel" in joined
        assert "1 filename non-canonical" in joined
        assert "1 invalid doc type" in joined
        assert "1 unknown issuer" in joined
        assert "1 missing OCR" in joined
        assert "1 low OCR confidence" in joined
        assert "1 missing state.db entry" in joined

    def test_renders_issues_by_issuer(self) -> None:
        report = _full_report()
        cons = _CapturingConsole()
        render_stdout(report, cons)
        joined = "\n".join(cons.lines)
        assert "Issues by issuer" in joined
        assert "acme: 1 issues" in joined
        assert "cez-as: 5 issues" in joined
        assert "(no issuer folder): 1 issues" in joined
        acme_idx = next(i for i, line in enumerate(cons.lines) if "acme:" in line)
        cez_idx = next(i for i, line in enumerate(cons.lines) if "cez-as:" in line)
        none_idx = next(i for i, line in enumerate(cons.lines) if "(no issuer folder):" in line)
        assert acme_idx < cez_idx < none_idx

    def test_skips_issues_by_issuer_when_no_findings(self) -> None:
        report = _make_report()
        cons = _CapturingConsole()
        render_stdout(report, cons)
        joined = "\n".join(cons.lines)
        assert "Issues by issuer" not in joined

    def test_renders_issuer_inboxes_block(self) -> None:
        report = _make_report(
            issuer_inboxes=(InboxSummary(path="/v/inbox/cez-as", unprocessed_count=3),),
        )
        cons = _CapturingConsole()
        render_stdout(report, cons)
        joined = "\n".join(cons.lines)
        assert "Issuer inboxes:" in joined
        assert "/v/inbox/cez-as: 3 unprocessed" in joined

    def test_skips_issuer_inboxes_when_empty(self) -> None:
        report = _make_report()
        cons = _CapturingConsole()
        render_stdout(report, cons)
        assert not any("Issuer inboxes:" in line for line in cons.lines)

    def test_renders_triage_row(self) -> None:
        report = _make_report(triage_pending=4)
        cons = _CapturingConsole()
        render_stdout(report, cons)
        joined = "\n".join(cons.lines)
        assert "Triage:" in joined
        assert "_triage: 4 awaiting review" in joined

    def test_rules_success_when_no_validation_errors(self) -> None:
        report = _make_report(
            rule_findings=(
                RuleFinding(rule_id="r-x", code="priority_conflict", detail="x"),
                RuleFinding(rule_id="r-y", code="priority_conflict", detail="y"),
                RuleFinding(rule_id="r-z", code="stale_rule", detail="z"),
            ),
            total_rules_in_registry=12,
            total_issuers_in_registry=6,
        )
        cons = _CapturingConsole()
        render_stdout(report, cons)
        joined = "\n".join(cons.lines)
        assert "12 rules valid (6 issuers, 2 conflicts)" in joined

    def test_rules_success_with_zero_findings(self) -> None:
        report = _make_report(total_rules_in_registry=5, total_issuers_in_registry=3)
        cons = _CapturingConsole()
        render_stdout(report, cons)
        joined = "\n".join(cons.lines)
        assert "5 rules valid (3 issuers, 0 conflicts)" in joined

    def test_rules_errors_block_when_validation_errors_present(self) -> None:
        report = _make_report(
            rule_findings=(
                RuleFinding(rule_id="r-1", code="validation_error", detail="bad"),
                RuleFinding(rule_id=None, code="regex_compile_failure", detail="cannot compile"),
                RuleFinding(rule_id="r-2", code="duplicate_id", detail="dup"),
            ),
        )
        cons = _CapturingConsole()
        render_stdout(report, cons)
        joined = "\n".join(cons.lines)
        assert "Errors:" in joined
        assert "[r-1] bad" in joined
        assert "[<no rule>] cannot compile" in joined
        assert "[r-2] dup" in joined

    def test_rules_conflicts_block_when_priority_conflicts_present(self) -> None:
        report = _make_report(
            rule_findings=(RuleFinding(rule_id="r-x", code="priority_conflict", detail="overlaps r-y"),),
        )
        cons = _CapturingConsole()
        render_stdout(report, cons)
        joined = "\n".join(cons.lines)
        assert "Conflicts:" in joined
        assert "[r-x] overlaps r-y" in joined

    def test_rules_stale_block_when_stale_rules_present(self) -> None:
        report = _make_report(
            rule_findings=(RuleFinding(rule_id="r-old", code="stale_rule", detail="last hit 400d ago"),),
        )
        cons = _CapturingConsole()
        render_stdout(report, cons)
        joined = "\n".join(cons.lines)
        assert "Stale rules:" in joined
        assert "[r-old] last hit 400d ago" in joined

    def test_renders_watcher_not_configured(self) -> None:
        report = _make_report()
        cons = _CapturingConsole()
        render_stdout(report, cons)
        joined = "\n".join(cons.lines)
        assert "Watcher:" in joined
        assert "not configured" in joined


class TestWriteJsonReport:
    def test_creates_directory(self, tmp_path: Path) -> None:
        report = _make_report()
        state_dir = tmp_path / "state"
        path = write_json_report(report, state_dir)
        assert (state_dir / "audit").is_dir()
        assert path.is_file()
        assert path.parent == state_dir / "audit"

    def test_filename_safe(self, tmp_path: Path) -> None:
        report = _make_report(
            generated_at=datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc),
        )
        path = write_json_report(report, tmp_path)
        assert ":" not in path.name
        assert "+" not in path.name
        assert path.suffix == ".json"

    def test_round_trips(self, tmp_path: Path) -> None:
        report = _full_report()
        path = write_json_report(report, tmp_path)
        decoded = json.loads(path.read_text(encoding="utf-8"))
        assert decoded["walked_pdf_count"] == 20
        assert decoded["clean_pdf_count"] == 8
        assert isinstance(decoded["legacy_layout_zettels"], list)
        assert decoded["legacy_layout_zettels"] == ["/v/zettels/old.md"]
        assert decoded["total_rules_in_registry"] == 10
        assert decoded["total_issuers_in_registry"] == 5
        assert len(decoded["pdf_findings"]) == 7
        assert len(decoded["rule_findings"]) == 5
        assert decoded["issuer_inboxes"][0]["path"] == "/v/inbox/cez-as"

    def test_atomic_overwrite_same_timestamp(self, tmp_path: Path) -> None:
        report1 = _make_report(walked_pdf_count=10)
        report2 = _make_report(walked_pdf_count=20)
        path1 = write_json_report(report1, tmp_path)
        path2 = write_json_report(report2, tmp_path)
        assert path1 == path2
        decoded = json.loads(path2.read_text(encoding="utf-8"))
        assert decoded["walked_pdf_count"] == 20
