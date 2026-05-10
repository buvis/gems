"""Auditor orchestrator for ``bim doc audit``.

Composes :func:`walk_business_root`, the per-PDF check functions, and
the rule-engine checks into a single read-only audit pass that produces
an :class:`AuditReport`. The orchestrator never writes to ``state.db``,
never mutates files, and degrades gracefully when an individual PDF
check raises (the offending check is skipped, the run continues).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bim.commands.doc.audit.models import (
    AuditReport,
    InboxSummary,
    PdfFinding,
    RuleFinding,
)
from bim.commands.doc.audit.pdf_checks import (
    OcrQualityReader,
    check_doc_type_valid,
    check_filename_canonical,
    check_issuer_registered,
    check_ocr,
    check_state_db_entry,
    check_zettel_exists,
)
from bim.commands.doc.audit.rules_checks import (
    check_priority_conflicts,
    check_registry_loadable,
    check_rule_freshness,
)
from bim.commands.doc.audit.walker import walk_business_root
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.state_db import StateDB

__all__ = ["Auditor", "HashReader", "NowProvider"]


HashReader = Callable[[Path], str]
NowProvider = Callable[[], datetime]


def _default_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Auditor:
    """Read-only audit pass over the business root + issuer registry."""

    state_db: StateDB
    business_root: Path
    vault_root: Path
    vault_documents_subdir: str
    low_confidence_threshold: float
    ocr_quality_reader: OcrQualityReader
    hash_reader: HashReader
    now_provider: NowProvider = _default_now

    def run(self, issuers_path: Path) -> AuditReport:
        now = self.now_provider()
        registry, rule_findings = self._collect_rule_findings(issuers_path, now)

        walked = 0
        clean = 0
        non_clean = 0
        pdf_findings: list[PdfFinding] = []
        legacy: list[str] = []
        n_issuers_walked: set[str] = set()

        for folder_slug, pdf_path in walk_business_root(self.business_root):
            walked += 1
            n_issuers_walked.add(folder_slug)
            findings, legacy_for_pdf = self._check_pdf(pdf_path, folder_slug, registry)
            pdf_findings.extend(findings)
            legacy.extend(legacy_for_pdf)
            if not findings and not legacy_for_pdf:
                clean += 1
            else:
                non_clean += 1

        issuer_inboxes = self._collect_inboxes(registry)
        triage_pending = self._count_triage()
        total_issuers = len(registry.issuers) if registry is not None else 0
        total_rules = sum(len(entry.rules) for entry in registry.issuers.values()) if registry is not None else 0

        return AuditReport(
            walked_pdf_count=walked,
            clean_pdf_count=clean,
            pdf_findings=tuple(pdf_findings),
            legacy_layout_zettels=tuple(sorted(legacy)),
            rule_findings=tuple(rule_findings),
            issuer_inboxes=tuple(issuer_inboxes),
            triage_pending=triage_pending,
            generated_at=now,
            n_issuers_walked=len(n_issuers_walked),
            total_rules_in_registry=total_rules,
            total_issuers_in_registry=total_issuers,
            non_clean_pdf_count=non_clean,
        )

    def _collect_rule_findings(
        self,
        issuers_path: Path,
        now: datetime,
    ) -> tuple[IssuerRegistry | None, list[RuleFinding]]:
        registry, load_findings = check_registry_loadable(issuers_path)
        findings: list[RuleFinding] = list(load_findings)
        if registry is not None:
            findings.extend(check_priority_conflicts(registry))
            findings.extend(check_rule_freshness(registry, self.state_db.get_rule_last_matches(), now))
        return registry, findings

    def _check_pdf(
        self,
        pdf_path: Path,
        folder_slug: str,
        registry: IssuerRegistry | None,
    ) -> tuple[list[PdfFinding], list[str]]:
        slug_or_none = folder_slug if folder_slug != "" else None
        findings: list[PdfFinding] = []

        findings.extend(check_filename_canonical(pdf_path, slug_or_none))

        if registry is not None:
            findings.extend(check_issuer_registered(folder_slug, registry, pdf_path))
            findings.extend(check_doc_type_valid(pdf_path, slug_or_none, registry))

        zettel_findings, legacy_for_pdf = check_zettel_exists(
            pdf_path,
            folder_slug,
            self.vault_root,
            self.vault_documents_subdir,
        )
        findings.extend(zettel_findings)

        try:
            ocr_findings = check_ocr(
                pdf_path,
                self.low_confidence_threshold,
                self.ocr_quality_reader,
                slug_or_none,
            )
        except Exception as exc:
            findings.append(
                PdfFinding(
                    pdf_path=str(pdf_path),
                    issuer_slug=slug_or_none,
                    doc_type=None,
                    code="ocr_check_failed",
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
        else:
            findings.extend(ocr_findings)

        try:
            sha = self.hash_reader(pdf_path)
        except Exception as exc:
            findings.append(
                PdfFinding(
                    pdf_path=str(pdf_path),
                    issuer_slug=slug_or_none,
                    doc_type=None,
                    code="hash_check_failed",
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
        else:
            findings.extend(check_state_db_entry(pdf_path, sha, self.state_db, slug_or_none))

        return findings, list(legacy_for_pdf)

    def _collect_inboxes(self, registry: IssuerRegistry | None) -> list[InboxSummary]:
        if registry is None:
            return []
        summaries: list[InboxSummary] = []
        for slug in registry.issuers:
            inbox_dir = self.business_root / slug / "inbox"
            if not inbox_dir.is_dir():
                continue
            count = sum(1 for p in inbox_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
            if count > 0:
                summaries.append(InboxSummary(path=str(inbox_dir), unprocessed_count=count))
        summaries.sort(key=lambda s: s.path)
        return summaries

    def _count_triage(self) -> int:
        triage_dir = self.business_root / "_triage"
        if not triage_dir.is_dir():
            return 0
        return sum(1 for p in triage_dir.iterdir() if p.is_file() and p.name.endswith(".proposed.yml"))
