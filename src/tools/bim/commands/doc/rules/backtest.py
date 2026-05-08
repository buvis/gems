"""``bim doc rules backtest`` — walk archive, count per-rule matches per folder.

Read-only: never writes zettels, never moves files. OCRs PDFs on demand.
Surfaces unexpected cross-folder matches as a hint that a rule is too loose.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from buvis.pybase.result import CommandResult

from bim.commands.doc.shared.rules.matcher import evaluate_match
from bim.commands.doc.shared.rules.models import Rule, SourceMetadata

if TYPE_CHECKING:
    from bim.commands.doc.shared.issuers import IssuerRegistry
    from bim.commands.doc.shared.ocr import OCRResult
    from bim.commands.doc.shared.progress import ProgressReporter

__all__ = ["CommandRulesBacktest"]


class _OCRRunnerProto(Protocol):
    def run(self, pdf_path: Path) -> OCRResult: ...


def _collect_rules(
    registry: IssuerRegistry,
    *,
    rule_id: str | None,
    issuer_slug: str | None,
) -> list[tuple[Rule, str]] | None:
    """Return ``[(rule, owning_slug), ...]`` filtered by ``rule_id`` and ``issuer_slug``.

    Returns ``None`` when ``rule_id`` was supplied but matches nothing.
    """
    out: list[tuple[Rule, str]] = []
    rule_id_seen = False
    for slug, entry in registry.issuers.items():
        if issuer_slug is not None and slug != issuer_slug:
            continue
        for rule in entry.rules:
            if rule_id is not None:
                if rule.id != rule_id:
                    continue
                rule_id_seen = True
            out.append((rule, slug))
    if rule_id is not None and not rule_id_seen:
        return None
    return out


def _walk_pdfs(business_root: Path) -> list[tuple[Path, str]]:
    """Return ``[(pdf_path, owning_folder_slug)]`` for every ``*.pdf`` under each issuer subdir."""
    if not business_root.is_dir():
        return []
    pdfs: list[tuple[Path, str]] = []
    for issuer_dir in sorted(business_root.iterdir()):
        if not issuer_dir.is_dir():
            continue
        for pdf in sorted(issuer_dir.glob("*.pdf")):
            pdfs.append((pdf, issuer_dir.name))
    return pdfs


class CommandRulesBacktest:
    """Backtest rules against the existing archive."""

    def __init__(self, *, ocr_runner: _OCRRunnerProto) -> None:
        self._ocr_runner = ocr_runner

    def run(
        self,
        registry: IssuerRegistry,
        business_root: Path,
        *,
        rule_id: str | None = None,
        issuer_slug: str | None = None,
        progress: ProgressReporter | None = None,
    ) -> CommandResult:
        rules = _collect_rules(registry, rule_id=rule_id, issuer_slug=issuer_slug)
        if rules is None:
            return CommandResult(success=False, error=f"rule {rule_id!r} not found")

        pdfs = _walk_pdfs(business_root)

        counts: dict[str, dict[str, int]] = {rule.id: {} for rule, _ in rules}
        owning: dict[str, str] = {rule.id: slug for rule, slug in rules}

        total = len(pdfs)
        for index, (pdf_path, folder_slug) in enumerate(pdfs, start=1):
            if progress is not None:
                progress.stage(f"[{index}/{total}] {folder_slug}/{pdf_path.name}")
            ocr_result = self._ocr_runner.run(pdf_path)
            source = SourceMetadata(source_kind="scan", original_filename=pdf_path.name)
            for rule, _owner in rules:
                match_result = evaluate_match(rule, ocr_result.ocr_text, source)
                if not match_result.matched:
                    continue
                bucket = counts.setdefault(rule.id, {})
                bucket[folder_slug] = bucket.get(folder_slug, 0) + 1

        folders_seen = {slug for _, slug in pdfs}
        lines = [f"Tested against {len(pdfs)} PDF(s) in {len(folders_seen)} issuer folder(s)."]
        for rule, _ in rules:
            lines.append("")
            lines.append(f"Rule: {rule.id}")
            rule_counts = counts.get(rule.id, {})
            if not rule_counts:
                lines.append("  (no matches)")
                continue
            owner = owning[rule.id]
            for folder in sorted(rule_counts.keys()):
                count = rule_counts[folder]
                glyph = "✓" if folder == owner else "⚠ unexpected"
                lines.append(f"  {count} in {folder}/ {glyph}")
        return CommandResult(success=True, output="\n".join(lines))
