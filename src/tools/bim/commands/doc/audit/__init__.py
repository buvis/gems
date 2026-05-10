"""Audit subsystem for ``bim doc audit``.

Re-exports the public domain models so callers can import directly from
``bim.commands.doc.audit``.
"""

from __future__ import annotations

from bim.commands.doc.audit.audit import AuditServices, CommandAudit
from bim.commands.doc.audit.auditor import Auditor
from bim.commands.doc.audit.models import (
    AuditReport,
    InboxSummary,
    PdfFinding,
    PdfFindingCode,
    RuleFinding,
    RuleFindingCode,
)
from bim.commands.doc.audit.pdf_checks import (
    OcrQualityReader,
    check_doc_type_valid,
    check_filename_canonical,
    check_issuer_registered,
    check_ocr,
    check_state_db_entry,
    check_zettel_exists,
    derive_zettel_filename,
    resolve_zettel_paths,
)
from bim.commands.doc.audit.reporter import render_stdout, write_json_report
from bim.commands.doc.audit.rules_checks import (
    check_priority_conflicts,
    check_registry_loadable,
    check_rule_freshness,
)
from bim.commands.doc.audit.walker import walk_business_root

__all__ = [
    "AuditReport",
    "AuditServices",
    "Auditor",
    "CommandAudit",
    "InboxSummary",
    "OcrQualityReader",
    "PdfFinding",
    "PdfFindingCode",
    "RuleFinding",
    "RuleFindingCode",
    "check_doc_type_valid",
    "check_filename_canonical",
    "check_issuer_registered",
    "check_ocr",
    "check_priority_conflicts",
    "check_registry_loadable",
    "check_rule_freshness",
    "check_state_db_entry",
    "check_zettel_exists",
    "derive_zettel_filename",
    "render_stdout",
    "resolve_zettel_paths",
    "walk_business_root",
    "write_json_report",
]
