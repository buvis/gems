"""Unit tests for the audit subsystem domain models.

Models are frozen dataclasses (immutable DTOs). The
``AuditReport.legacy_layout_zettels`` field is a binding contract for
PRD 00036.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any

import pytest
from bim.commands.doc.audit.models import (
    AuditReport,
    InboxSummary,
    PdfFinding,
    RuleFinding,
)


def _make_report(**overrides: Any) -> AuditReport:
    """Build an AuditReport with safe defaults; override per-test.

    Defaults satisfy the partition invariant
    ``clean_pdf_count + non_clean_pdf_count == walked_pdf_count`` so tests
    that don't care about the partition can stay short. Tests overriding
    any of these counts are responsible for keeping the invariant.
    """
    defaults: dict[str, Any] = {
        "walked_pdf_count": 10,
        "clean_pdf_count": 5,
        "non_clean_pdf_count": 5,
        "pdf_findings": (),
        "legacy_layout_zettels": (),
        "rule_findings": (),
        "issuer_inboxes": (),
        "triage_pending": 0,
        "generated_at": datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc),
        "n_issuers_walked": 3,
    }
    defaults.update(overrides)
    return AuditReport(**defaults)


class TestPdfFinding:
    def test_fields_stored_as_given(self) -> None:
        finding = PdfFinding(
            pdf_path="/vault/x.pdf",
            issuer_slug="cez-as",
            doc_type="invoice",
            code="missing_zettel",
            detail="orphan",
        )
        assert finding.pdf_path == "/vault/x.pdf"
        assert finding.issuer_slug == "cez-as"
        assert finding.doc_type == "invoice"
        assert finding.code == "missing_zettel"
        assert finding.detail == "orphan"

    def test_detail_defaults_to_none(self) -> None:
        finding = PdfFinding(
            pdf_path="/x.pdf",
            issuer_slug=None,
            doc_type=None,
            code="unknown_issuer",
        )
        assert finding.detail is None

    def test_is_frozen(self) -> None:
        finding = PdfFinding(
            pdf_path="/x.pdf",
            issuer_slug=None,
            doc_type=None,
            code="unknown_issuer",
        )
        with pytest.raises(FrozenInstanceError):
            finding.pdf_path = "/y.pdf"


class TestRuleFinding:
    def test_fields_stored_as_given(self) -> None:
        finding = RuleFinding(
            rule_id="rule-42",
            code="stale_rule",
            detail="last matched 400 days ago",
        )
        assert finding.rule_id == "rule-42"
        assert finding.code == "stale_rule"
        assert finding.detail == "last matched 400 days ago"

    def test_rule_id_can_be_none(self) -> None:
        finding = RuleFinding(rule_id=None, code="validation_error", detail="bad regex")
        assert finding.rule_id is None

    def test_is_frozen(self) -> None:
        finding = RuleFinding(rule_id="r1", code="duplicate_id", detail="dup")
        with pytest.raises(FrozenInstanceError):
            finding.code = "stale_rule"


class TestInboxSummary:
    def test_fields_stored_as_given(self) -> None:
        summary = InboxSummary(path="/vault/inbox/cez-as", unprocessed_count=12)
        assert summary.path == "/vault/inbox/cez-as"
        assert summary.unprocessed_count == 12

    def test_is_frozen(self) -> None:
        summary = InboxSummary(path="/p", unprocessed_count=0)
        with pytest.raises(FrozenInstanceError):
            summary.unprocessed_count = 1


class TestAuditReport:
    def test_post_init_rejects_naive_datetime(self) -> None:
        with pytest.raises(ValueError, match="generated_at must be timezone-aware"):
            _make_report(generated_at=datetime(2026, 5, 10, 12, 0, 0))

    def test_post_init_accepts_utc_datetime(self) -> None:
        report = _make_report(generated_at=datetime.now(timezone.utc))
        assert report.generated_at.tzinfo is not None

    def test_post_init_rejects_clean_exceeds_walked(self) -> None:
        with pytest.raises(ValueError):
            _make_report(walked_pdf_count=5, clean_pdf_count=10, non_clean_pdf_count=0)

    def test_post_init_rejects_negative_walked(self) -> None:
        with pytest.raises(ValueError):
            _make_report(walked_pdf_count=-1, clean_pdf_count=0, non_clean_pdf_count=0)

    def test_post_init_rejects_partition_mismatch(self) -> None:
        # Spec invariant: clean + non_clean must equal walked. Catches the
        # gap where a legacy-only PDF could fall outside both the findings
        # list and the clean count.
        with pytest.raises(ValueError, match="clean_pdf_count \\+ non_clean_pdf_count"):
            _make_report(walked_pdf_count=10, clean_pdf_count=5, non_clean_pdf_count=4)

    def test_post_init_rejects_negative_non_clean(self) -> None:
        with pytest.raises(ValueError, match="non_clean_pdf_count"):
            _make_report(walked_pdf_count=0, clean_pdf_count=0, non_clean_pdf_count=-1)

    def test_post_init_rejects_negative_triage_pending(self) -> None:
        with pytest.raises(ValueError):
            _make_report(triage_pending=-1)

    def test_to_json_dict_round_trips_through_json(self) -> None:
        report = _make_report(
            pdf_findings=(
                PdfFinding(
                    pdf_path="/vault/x.pdf",
                    issuer_slug="cez-as",
                    doc_type="invoice",
                    code="missing_zettel",
                    detail=None,
                ),
            ),
            legacy_layout_zettels=("/vault/foo.md",),
            rule_findings=(RuleFinding(rule_id="r-1", code="stale_rule", detail="not used"),),
            issuer_inboxes=(InboxSummary(path="/vault/inbox/cez-as", unprocessed_count=2),),
        )
        encoded = json.dumps(report.to_json_dict())
        decoded = json.loads(encoded)
        assert isinstance(decoded, dict)
        for key in (
            "generated_at",
            "walked_pdf_count",
            "clean_pdf_count",
            "n_issuers_walked",
            "triage_pending",
            "pdf_findings",
            "legacy_layout_zettels",
            "rule_findings",
            "issuer_inboxes",
        ):
            assert key in decoded

    def test_to_json_dict_preserves_legacy_layout_zettels(self) -> None:
        report = _make_report(
            legacy_layout_zettels=("/vault/foo.md", "/vault/bar.md"),
        )
        out = report.to_json_dict()
        assert out["legacy_layout_zettels"] == ["/vault/foo.md", "/vault/bar.md"]

    def test_to_json_dict_iso_format_generated_at(self) -> None:
        report = _make_report(
            generated_at=datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc),
        )
        out = report.to_json_dict()
        parsed = datetime.fromisoformat(out["generated_at"])
        assert parsed.tzinfo is not None

    def test_to_json_dict_codes_are_strings(self) -> None:
        report = _make_report(
            pdf_findings=(
                PdfFinding(
                    pdf_path="/x.pdf",
                    issuer_slug=None,
                    doc_type=None,
                    code="unknown_issuer",
                ),
            ),
            rule_findings=(RuleFinding(rule_id="r1", code="duplicate_id", detail="d"),),
        )
        out = report.to_json_dict()
        assert out["pdf_findings"][0]["code"] == "unknown_issuer"
        assert isinstance(out["pdf_findings"][0]["code"], str)
        assert out["rule_findings"][0]["code"] == "duplicate_id"
        assert isinstance(out["rule_findings"][0]["code"], str)

    def test_pdf_findings_serialized_keys(self) -> None:
        report = _make_report(
            pdf_findings=(
                PdfFinding(
                    pdf_path="/x.pdf",
                    issuer_slug="acme",
                    doc_type="invoice",
                    code="missing_zettel",
                    detail=None,
                ),
            ),
        )
        out = report.to_json_dict()
        entry = out["pdf_findings"][0]
        assert set(entry.keys()) == {
            "pdf_path",
            "issuer_slug",
            "doc_type",
            "code",
            "detail",
        }
        assert entry["detail"] is None

    def test_is_frozen(self) -> None:
        report = _make_report()
        with pytest.raises(FrozenInstanceError):
            report.triage_pending = 99
