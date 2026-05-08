"""Private helpers for the bim doc ingest pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from buvis.pybase.result import CommandResult

from bim.commands.doc.shared.zettel_helpers import build_zettel_tags, compose_zettel_title
from bim.commands.doc.shared.zettel_writer import DocumentZettelFrontmatter

if TYPE_CHECKING:
    from bim.commands.doc.shared.classifier import ClassifyResult
    from bim.commands.doc.shared.extractor import ExtractResult
    from bim.commands.doc.shared.ocr import OCRResult
    from bim.commands.doc.shared.rules.models import RuleResult
    from bim.params.doc_ingest import IngestParams

__all__ = [
    "_ClassifyStage",
    "_ExtractStage",
    "_FilingContext",
    "_RuleStage",
    "_TriageContext",
    "build_filing_frontmatter",
    "build_filing_result",
    "retry_llm_call",
]

T = TypeVar("T")


@dataclass(frozen=True)
class _TriageContext:
    params: IngestParams
    sha: str
    ocr_result: OCRResult
    classify_result: ClassifyResult | None
    extract_result: ExtractResult | None
    reasons: list[str]
    issuer_slug: str
    issuer_display: str


@dataclass(frozen=True)
class _FilingContext:
    params: IngestParams
    sha: str
    ocr_result: OCRResult
    classify_result: ClassifyResult
    extract_result: ExtractResult
    issuer_slug: str
    issuer_display: str
    extraction_method: str


@dataclass(frozen=True)
class _RuleStage:
    ocr_result: OCRResult
    rule_result: RuleResult
    extraction_method: str
    use_pinned: bool


@dataclass(frozen=True)
class _ClassifyStage:
    classify_result: ClassifyResult | None
    issuer_slug: str
    issuer_display: str
    triage_reasons: list[str]


@dataclass(frozen=True)
class _ExtractStage:
    extract_result: ExtractResult | None
    triage_reasons: list[str]


def retry_llm_call(
    *,
    func: Callable[[str], T],
    primary_model: str,
    fallback_model: str,
    max_retries: int,
    is_transient: Callable[[Exception], bool],
) -> T:
    attempts = 0
    while attempts < 1 + max_retries:
        try:
            return func(primary_model)
        except Exception as exc:
            if not is_transient(exc):
                raise
            attempts += 1

    return func(fallback_model)


def build_filing_frontmatter(
    ctx: _FilingContext,
    *,
    zk_timestamp: str,
    target_pdf: Path,
    ingested_at: datetime,
    ocr_engine: str,
) -> DocumentZettelFrontmatter:
    title = compose_zettel_title(
        issuer=ctx.issuer_display,
        doc_type=ctx.classify_result.doc_type,
        doc_number=ctx.extract_result.number,
        doc_title=ctx.extract_result.title,
    )
    return DocumentZettelFrontmatter(
        id=int(zk_timestamp),
        title=title,
        doc_type=ctx.classify_result.doc_type,
        issuer=ctx.issuer_display,
        doc_number=ctx.extract_result.number,
        doc_date=ctx.extract_result.date or ingested_at.date(),
        doc_amount=ctx.extract_result.amount,
        doc_currency=ctx.extract_result.currency,
        doc_language=ctx.classify_result.language,
        ingested_at=ingested_at,
        ingest_source=ctx.params.source,
        file_path=str(target_pdf.expanduser().resolve()),
        file_sha256=ctx.sha,
        ocr_engine=ocr_engine,
        ocr_mean_confidence=ctx.ocr_result.mean_confidence,
        extraction_method=ctx.extraction_method,
        tags=build_zettel_tags(ctx.classify_result.doc_type, ctx.issuer_slug, ctx.extract_result.date),
    )


def build_filing_result(
    *,
    outcome: str,
    zettel_path: Path,
    target_pdf: Path,
    canonical_filename: str,
    sha: str,
) -> CommandResult:
    return CommandResult(
        success=True,
        metadata={
            "outcome": outcome,
            "zettel_path": str(zettel_path),
            "pdf_path": str(target_pdf),
            "canonical_filename": canonical_filename,
            "sha256": sha,
        },
    )
