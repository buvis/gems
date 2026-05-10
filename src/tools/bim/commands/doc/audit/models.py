"""Domain models for the ``bim doc audit`` subsystem.

These are immutable internal DTOs (frozen dataclasses, not Pydantic - the
audit subsystem composes them in-process and serializes only at the JSON
output boundary). The ``AuditReport.legacy_layout_zettels`` tuple is a
binding output contract for PRD 00036; the JSON shape produced by
``AuditReport.to_json_dict`` is part of the public ``bim doc audit``
output schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

__all__ = [
    "VALIDATION_ERROR_CODES",
    "AuditReport",
    "InboxSummary",
    "PdfFinding",
    "PdfFindingCode",
    "RuleFinding",
    "RuleFindingCode",
]


# Subset of RuleFindingCode values that represent registry validation
# failures (vs. priority_conflict / stale_rule which are warnings). Both
# CommandAudit (filters into result.metadata) and the stdout reporter
# (gates the "Errors" block) read this set; keeping it here avoids two
# parallel definitions drifting apart when a new error code is added.
VALIDATION_ERROR_CODES: frozenset[str] = frozenset(
    {"validation_error", "duplicate_id", "regex_compile_failure"},
)


PdfFindingCode = Literal[
    "missing_zettel",
    "non_canonical_filename",
    "unknown_issuer",
    "invalid_doc_type",
    "missing_ocr",
    "low_ocr_confidence",
    "missing_state_db_entry",
    # Adapter failures: surfaced when the OCR-quality reader or hash reader
    # raises while inspecting a PDF (read error, permission denied, corrupted
    # file, adapter bug). The audit must report these rather than treat the
    # PDF as clean.
    "ocr_check_failed",
    "hash_check_failed",
]

RuleFindingCode = Literal[
    "validation_error",
    "duplicate_id",
    "regex_compile_failure",
    "priority_conflict",
    "stale_rule",
]


@dataclass(frozen=True)
class PdfFinding:
    pdf_path: str
    issuer_slug: str | None
    doc_type: str | None
    code: PdfFindingCode
    detail: str | None = None


@dataclass(frozen=True)
class RuleFinding:
    rule_id: str | None
    code: RuleFindingCode
    detail: str


@dataclass(frozen=True)
class InboxSummary:
    path: str
    unprocessed_count: int


@dataclass(frozen=True)
class AuditReport:
    walked_pdf_count: int
    clean_pdf_count: int
    pdf_findings: tuple[PdfFinding, ...]
    legacy_layout_zettels: tuple[str, ...]
    rule_findings: tuple[RuleFinding, ...]
    issuer_inboxes: tuple[InboxSummary, ...]
    triage_pending: int
    generated_at: datetime
    n_issuers_walked: int
    total_rules_in_registry: int = 0
    total_issuers_in_registry: int = 0
    # Number of distinct PDFs that are NOT clean: those with one or more
    # findings, OR a zettel at a legacy path, OR both. Together with
    # ``clean_pdf_count`` this is a true partition over walked PDFs:
    # ``clean_pdf_count + non_clean_pdf_count == walked_pdf_count``. Consumers
    # cannot derive this from ``len(pdf_findings) + len(legacy_layout_zettels)``
    # because a single PDF may contribute multiple findings and a legacy
    # entry; that arithmetic would double-count.
    non_clean_pdf_count: int = 0

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if self.walked_pdf_count < 0:
            raise ValueError(f"walked_pdf_count must be >= 0, got {self.walked_pdf_count}")
        if self.clean_pdf_count < 0:
            raise ValueError(f"clean_pdf_count must be >= 0, got {self.clean_pdf_count}")
        if self.clean_pdf_count > self.walked_pdf_count:
            raise ValueError(
                "clean_pdf_count must not exceed walked_pdf_count "
                f"(clean={self.clean_pdf_count}, walked={self.walked_pdf_count})"
            )
        if self.non_clean_pdf_count < 0:
            raise ValueError(f"non_clean_pdf_count must be >= 0, got {self.non_clean_pdf_count}")
        if self.clean_pdf_count + self.non_clean_pdf_count != self.walked_pdf_count:
            raise ValueError(
                "clean_pdf_count + non_clean_pdf_count must equal walked_pdf_count "
                f"(clean={self.clean_pdf_count}, non_clean={self.non_clean_pdf_count}, "
                f"walked={self.walked_pdf_count})"
            )
        if self.triage_pending < 0:
            raise ValueError(f"triage_pending must be >= 0, got {self.triage_pending}")
        if self.total_rules_in_registry < 0:
            raise ValueError(f"total_rules_in_registry must be >= 0, got {self.total_rules_in_registry}")
        if self.total_issuers_in_registry < 0:
            raise ValueError(f"total_issuers_in_registry must be >= 0, got {self.total_issuers_in_registry}")

    def to_json_dict(self) -> dict[str, Any]:
        """Render the report as a JSON-serializable dict.

        ``generated_at`` is emitted as an ISO 8601 string; collection
        fields are serialized as lists. Literal ``code`` values are
        already plain strings, no conversion needed.
        """
        return {
            "generated_at": self.generated_at.isoformat(),
            "walked_pdf_count": self.walked_pdf_count,
            "clean_pdf_count": self.clean_pdf_count,
            "non_clean_pdf_count": self.non_clean_pdf_count,
            "n_issuers_walked": self.n_issuers_walked,
            "triage_pending": self.triage_pending,
            "total_rules_in_registry": self.total_rules_in_registry,
            "total_issuers_in_registry": self.total_issuers_in_registry,
            "pdf_findings": [
                {
                    "pdf_path": finding.pdf_path,
                    "issuer_slug": finding.issuer_slug,
                    "doc_type": finding.doc_type,
                    "code": finding.code,
                    "detail": finding.detail,
                }
                for finding in self.pdf_findings
            ],
            "legacy_layout_zettels": list(self.legacy_layout_zettels),
            "rule_findings": [
                {
                    "rule_id": finding.rule_id,
                    "code": finding.code,
                    "detail": finding.detail,
                }
                for finding in self.rule_findings
            ],
            "issuer_inboxes": [
                {
                    "path": summary.path,
                    "unprocessed_count": summary.unprocessed_count,
                }
                for summary in self.issuer_inboxes
            ],
        }
