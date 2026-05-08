"""``bim doc rules test`` — run a single rule against a single PDF.

Reports clause-by-clause match results plus the extracted fields. Read-only:
does not write a zettel, does not move the PDF, does not touch state.db.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from buvis.pybase.result import CommandResult

from bim.commands.doc.shared.rules.extractor import apply_extract
from bim.commands.doc.shared.rules.matcher import evaluate_match
from bim.commands.doc.shared.rules.models import Rule, SourceMetadata

if TYPE_CHECKING:
    from bim.commands.doc.shared.issuers import IssuerRegistry
    from bim.commands.doc.shared.ocr import OCRResult

__all__ = ["CommandRulesTest"]


class _OCRRunnerProto(Protocol):
    def run(self, pdf_path: Path) -> OCRResult: ...


def _find_rule(registry: IssuerRegistry, rule_id: str) -> Rule | None:
    for entry in registry.issuers.values():
        for rule in entry.rules:
            if rule.id == rule_id:
                return rule
    return None


def _format_clause_lines(rule: Rule, ocr_text: str, source: SourceMetadata) -> list[str]:
    """Per-clause pass/fail summary by re-evaluating each clause in isolation."""
    lines: list[str] = []
    clause_attrs = (
        "ocr_contains",
        "ocr_matches",
        "email_from_domain",
        "email_subject_contains",
        "email_subject_matches",
        "original_filename_matches",
    )
    for attr in clause_attrs:
        clause_value = getattr(rule.match, attr)
        if clause_value is None:
            continue
        narrowed = rule.match.model_copy(update={a: None for a in clause_attrs if a != attr})
        narrowed_rule = rule.model_copy(update={"match": narrowed})
        clause_result = evaluate_match(narrowed_rule, ocr_text, source)
        glyph = "✓" if clause_result.matched else "✗"
        lines.append(f"  {glyph} {attr}: {clause_value!r}")
    return lines


class CommandRulesTest:
    """Run a single rule against a single PDF and report clause-level results."""

    def __init__(self, *, ocr_runner: _OCRRunnerProto) -> None:
        self._ocr_runner = ocr_runner

    def run(self, registry: IssuerRegistry, rule_id: str, pdf_path: Path) -> CommandResult:
        if not pdf_path.is_file():
            return CommandResult(success=False, error=f"PDF not found: {pdf_path}")

        rule = _find_rule(registry, rule_id)
        if rule is None:
            return CommandResult(success=False, error=f"rule {rule_id!r} not found")

        ocr_result = self._ocr_runner.run(pdf_path)
        source = SourceMetadata(source_kind="scan", original_filename=pdf_path.name)
        match_result = evaluate_match(rule, ocr_result.ocr_text, source)
        clause_lines = _format_clause_lines(rule, ocr_result.ocr_text, source)

        header = f"Rule: {rule.id} (v{rule.version}, priority {rule.priority})"
        clause_section = "Match clauses:\n" + "\n".join(clause_lines) if clause_lines else "Match clauses: (none)"

        if not match_result.matched:
            body = "\n".join([header, clause_section, "Result: NO MATCH"])
            return CommandResult(success=False, error=body)

        pinned = apply_extract(rule, ocr_result.ocr_text, source, match_result.captures)
        if pinned is None:
            body = "\n".join(
                [
                    header,
                    clause_section,
                    "Result: MATCH",
                    "Extraction failed (transform error or missing capture)",
                ]
            )
            return CommandResult(success=False, error=body)

        extraction_lines = ["Extraction:"]
        for field_name in sorted(pinned.keys()):
            extraction_lines.append(f"  {field_name}: {pinned[field_name]!r}")
        body = "\n".join([header, clause_section, "Result: MATCH", *extraction_lines])
        return CommandResult(success=True, output=body)
