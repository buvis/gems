"""CommandAudit - read-only walk of the Business folder; reports drift.

Composes :class:`Auditor` with the JSON reporter and returns a
:class:`CommandResult`. The audit always succeeds when the file walk
runs; ``success=False`` is reserved for infrastructure failures
(unexpected I/O during walk, JSON report write failure).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from bim.commands.doc.audit.auditor import Auditor, HashReader, NowProvider
from bim.commands.doc.audit.models import VALIDATION_ERROR_CODES
from bim.commands.doc.audit.pdf_checks import OcrQualityReader
from bim.commands.doc.audit.reporter import write_json_report

if TYPE_CHECKING:
    from bim.commands.doc.shared.state_db import StateDB

__all__ = ["AuditServices", "CommandAudit"]


@dataclass(frozen=True)
class AuditServices:
    """Bundle of the boundary adapters CommandAudit depends on."""

    state_db: StateDB
    business_root: Path
    vault_root: Path
    vault_documents_subdir: str
    issuers_path: Path
    state_dir: Path
    low_confidence_threshold: float
    ocr_quality_reader: OcrQualityReader
    hash_reader: HashReader


@dataclass(frozen=True)
class CommandAudit:
    """Read-only audit of the Business folder, producing a CommandResult."""

    services: AuditServices
    now_provider: NowProvider | None = None

    def execute(self) -> CommandResult:
        now: NowProvider = self.now_provider if self.now_provider is not None else (lambda: datetime.now(timezone.utc))
        auditor = Auditor(
            state_db=self.services.state_db,
            business_root=self.services.business_root,
            vault_root=self.services.vault_root,
            vault_documents_subdir=self.services.vault_documents_subdir,
            low_confidence_threshold=self.services.low_confidence_threshold,
            ocr_quality_reader=self.services.ocr_quality_reader,
            hash_reader=self.services.hash_reader,
            now_provider=now,
        )

        try:
            report = auditor.run(self.services.issuers_path)
        except OSError as exc:
            return CommandResult(success=False, error=f"audit failed: {exc}")

        try:
            json_path = write_json_report(report, self.services.state_dir)
        except OSError as exc:
            return CommandResult(
                success=False,
                error=f"audit ran but JSON report write failed: {exc}",
                metadata={"report": report},
            )

        validation_errors = [f for f in report.rule_findings if f.code in VALIDATION_ERROR_CODES]
        return CommandResult(
            success=True,
            metadata={
                "report": report,
                "report_path": str(json_path),
                "walked_pdf_count": report.walked_pdf_count,
                "clean_pdf_count": report.clean_pdf_count,
                "legacy_layout_count": len(report.legacy_layout_zettels),
                "validation_errors": validation_errors,
            },
        )
