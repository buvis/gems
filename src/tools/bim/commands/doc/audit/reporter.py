"""Render an :class:`AuditReport` to stdout and to a JSON file.

``render_stdout`` emits human-friendly rows through a console adapter that
implements ``print(msg, *, mode="raw")``. ``write_json_report`` writes the
report to ``<state_dir>/audit/<safe-iso>.json`` atomically.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING, Protocol

from bim.commands.doc.audit.models import VALIDATION_ERROR_CODES, AuditReport
from bim.commands.doc.shared.atomic_write import atomic_write_text

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["render_stdout", "write_json_report"]


class _ConsoleLike(Protocol):
    def print(self, msg: str, *, mode: str = ...) -> None: ...


def _emit(console: _ConsoleLike, line: str) -> None:
    console.print(line, mode="raw")


def _blank(console: _ConsoleLike) -> None:
    console.print("", mode="raw")


def _render_summary_block(report: AuditReport, console: _ConsoleLike) -> None:
    code_counts: Counter[str] = Counter(f.code for f in report.pdf_findings)
    legacy_count = len(report.legacy_layout_zettels)

    _emit(
        console,
        f"Audit complete. Walked {report.walked_pdf_count} documents in {report.n_issuers_walked} folders.",
    )
    _blank(console)
    _emit(console, f"  ✓ {report.clean_pdf_count} clean")
    _emit(console, f"  ⚠ {code_counts.get('missing_zettel', 0)} missing zettel")
    _emit(console, f"  ⚠ {legacy_count} legacy layout zettels")
    _emit(console, f"  ⚠ {code_counts.get('non_canonical_filename', 0)} filename non-canonical")
    _emit(console, f"  ⚠ {code_counts.get('invalid_doc_type', 0)} invalid doc type")
    _emit(console, f"  ⚠ {code_counts.get('unknown_issuer', 0)} unknown issuer")
    _emit(console, f"  ⚠ {code_counts.get('missing_ocr', 0)} missing OCR")
    low_ocr_count = code_counts.get("low_ocr_confidence", 0)
    if report.ocr_confidence_assessable_count == 0 and low_ocr_count == 0:
        # The OCR-quality reader did not expose a confidence value for any
        # PDF in this run -- e.g. the production pdfminer-based reader.
        # Showing "0 low OCR confidence" here would falsely imply the
        # check ran and found nothing.
        _emit(console, "  · low OCR confidence: not assessed (reader does not expose confidence)")
    else:
        _emit(console, f"  ⚠ {low_ocr_count} low OCR confidence")
    _emit(console, f"  ⚠ {code_counts.get('missing_state_db_entry', 0)} missing state.db entry")
    ocr_failed = code_counts.get("ocr_check_failed", 0)
    hash_failed = code_counts.get("hash_check_failed", 0)
    if ocr_failed:
        _emit(console, f"  ✘ {ocr_failed} OCR check failed")
    if hash_failed:
        _emit(console, f"  ✘ {hash_failed} hash check failed")


def _render_issues_by_issuer(report: AuditReport, console: _ConsoleLike) -> None:
    if not report.pdf_findings:
        return
    by_issuer: Counter[str | None] = Counter(f.issuer_slug for f in report.pdf_findings)
    named = sorted(slug for slug in by_issuer if slug is not None)
    has_none = None in by_issuer

    _blank(console)
    _emit(console, "Issues by issuer:")
    for slug in named:
        _emit(console, f"  {slug}: {by_issuer[slug]} issues")
    if has_none:
        _emit(console, f"  (no issuer folder): {by_issuer[None]} issues")


def _render_issuer_inboxes(report: AuditReport, console: _ConsoleLike) -> None:
    if not report.issuer_inboxes:
        return
    _blank(console)
    _emit(console, "Issuer inboxes:")
    for summary in report.issuer_inboxes:
        _emit(console, f"  {summary.path}: {summary.unprocessed_count} unprocessed")


def _render_triage(report: AuditReport, console: _ConsoleLike) -> None:
    _blank(console)
    _emit(console, "Triage:")
    _emit(console, f"  _triage: {report.triage_pending} awaiting review")


def _render_rules(report: AuditReport, console: _ConsoleLike) -> None:
    errors = [f for f in report.rule_findings if f.code in VALIDATION_ERROR_CODES]
    conflicts = [f for f in report.rule_findings if f.code == "priority_conflict"]
    stale = [f for f in report.rule_findings if f.code == "stale_rule"]

    _blank(console)
    _emit(console, "Rules:")

    if not errors:
        _emit(
            console,
            f"  ✓ {report.total_rules_in_registry} rules valid "
            f"({report.total_issuers_in_registry} issuers, {len(conflicts)} conflicts)",
        )

    if errors:
        _emit(console, "  ✘ Errors:")
        for finding in errors:
            label = finding.rule_id if finding.rule_id is not None else "<no rule>"
            _emit(console, f"    [{label}] {finding.detail}")

    if conflicts:
        _emit(console, "  Conflicts:")
        for finding in conflicts:
            label = finding.rule_id if finding.rule_id is not None else "<no rule>"
            _emit(console, f"    [{label}] {finding.detail}")

    if stale:
        _emit(console, "  Stale rules:")
        for finding in stale:
            label = finding.rule_id if finding.rule_id is not None else "<no rule>"
            _emit(console, f"    [{label}] {finding.detail}")


def _render_watcher(console: _ConsoleLike) -> None:
    _blank(console)
    _emit(console, "Watcher:")
    _emit(console, "  not configured")


def render_stdout(report: AuditReport, console_obj: _ConsoleLike) -> None:
    """Render the audit report to the buvis console.

    All output goes through ``console_obj.print(line, mode="raw")``. Sections
    are separated by blank raw lines.
    """
    _render_summary_block(report, console_obj)
    _render_issues_by_issuer(report, console_obj)
    _render_issuer_inboxes(report, console_obj)
    _render_triage(report, console_obj)
    _render_rules(report, console_obj)
    _render_watcher(console_obj)
    _blank(console_obj)


def _safe_iso(report: AuditReport) -> str:
    iso = report.generated_at.isoformat()
    return iso.replace(":", "_").replace("+", "_")


def write_json_report(report: AuditReport, state_dir: Path) -> Path:
    """Write the report to ``<state_dir>/audit/<safe-iso>.json``.

    Returns the full path to the written file. Uses
    :func:`atomic_write_text` so a crashed write never leaves a partial
    file in place.
    """
    report_dir = state_dir / "audit"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{_safe_iso(report)}.json"
    payload = json.dumps(report.to_json_dict(), indent=2, ensure_ascii=False) + "\n"
    atomic_write_text(report_path, payload)
    return report_path
