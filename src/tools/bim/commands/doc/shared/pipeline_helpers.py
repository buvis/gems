"""Private helpers for the bim doc ingest pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast

from buvis.pybase.result import CommandResult

from bim.commands.doc.shared.zettel_helpers import build_zettel_tags, compose_zettel_title
from bim.commands.doc.shared.zettel_writer import DocumentZettelFrontmatter, IngestSource

if TYPE_CHECKING:
    from bim.commands.doc.shared.classifier import ClassifyResult
    from bim.commands.doc.shared.extractor import ExtractResult
    from bim.commands.doc.shared.ocr import OCRResult
    from bim.commands.doc.shared.rules.models import RuleResult
    from bim.commands.doc.shared.triage import TriageProposal
    from bim.params.doc_ingest import IngestParams

__all__ = [
    "ClassifyStage",
    "ExtractStage",
    "FilingContext",
    "PromoteFrontmatterContext",
    "RuleStage",
    "TriageContext",
    "build_filing_frontmatter",
    "build_filing_result",
    "build_promote_frontmatter",
    "retry_llm_call",
]

T = TypeVar("T")


@dataclass(frozen=True)
class TriageContext:
    params: IngestParams
    sha: str
    ocr_result: OCRResult
    classify_result: ClassifyResult | None
    extract_result: ExtractResult | None
    reasons: list[str]
    issuer_slug: str
    issuer_display: str


@dataclass(frozen=True)
class PromoteFrontmatterContext:
    """Resolved inputs for :func:`build_promote_frontmatter`.

    Promote-side analog of :class:`FilingContext`. Holds resolved values
    (primitives plus the human-approved ``TriageProposal``) with no
    dependency on ``CommandPromote``-private types, so the helper can be
    called from both production code and the cross-path consistency test.
    """

    proposal: TriageProposal
    issuer_display: str
    issuer_slug: str
    zk_timestamp: str
    target_pdf: Path
    sha: str
    ocr_engine: str
    ocr_mean_confidence: float | None


@dataclass(frozen=True)
class FilingContext:
    params: IngestParams
    sha: str
    ocr_result: OCRResult
    classify_result: ClassifyResult
    extract_result: ExtractResult
    issuer_slug: str
    issuer_display: str
    extraction_method: str


@dataclass(frozen=True)
class RuleStage:
    ocr_result: OCRResult
    rule_result: RuleResult
    extraction_method: str
    use_pinned: bool


@dataclass(frozen=True)
class ClassifyStage:
    classify_result: ClassifyResult | None
    issuer_slug: str
    issuer_display: str
    triage_reasons: list[str]


@dataclass(frozen=True)
class ExtractStage:
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
    ctx: FilingContext,
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


def build_promote_frontmatter(ctx: PromoteFrontmatterContext) -> DocumentZettelFrontmatter | CommandResult:
    """Build a v1 frontmatter for a human-approved triage proposal.

    Mirror of :func:`build_filing_frontmatter` for the promote code path.
    Inputs are bundled in :class:`PromoteFrontmatterContext` (resolved
    primitives plus the approved ``TriageProposal``, no dependency on
    ``CommandPromote``-private types); both production
    ``CommandPromote._build_frontmatter`` and the cross-path consistency
    test call this function directly to pin PRD criterion 8 (same logical
    document, same frontmatter).
    """
    proposal = ctx.proposal
    title = proposal.zettel_preview.title
    if not title:
        try:
            title = compose_zettel_title(
                issuer=ctx.issuer_display,
                doc_type=proposal.document.type,
                doc_number=proposal.document.number,
                doc_title=proposal.document.title,
            )
        except ValueError as exc:
            return CommandResult(success=False, error=f"compose title failed: {exc}")
    try:
        return DocumentZettelFrontmatter(
            id=int(ctx.zk_timestamp),
            title=title,
            doc_type=proposal.document.type,
            issuer=ctx.issuer_display,
            doc_number=proposal.document.number,
            # Fall back to the proposal's ``ingested_at.date()`` (not
            # ``date.today()``) so a date-less document promoted N days
            # after triage produces the same ``doc-date`` as its filing-path
            # counterpart. Mirrors ``build_filing_frontmatter``'s
            # ``ingested_at.date()`` fallback. PRD 00035 success metric #8.
            doc_date=proposal.document.date or proposal.zettel_preview.ingested_at.date(),
            doc_amount=proposal.document.amount,
            doc_currency=proposal.document.currency,
            doc_language=proposal.document.language,
            ingested_at=proposal.zettel_preview.ingested_at,
            ingest_source=cast(IngestSource, proposal.source.kind),
            file_path=str(ctx.target_pdf.expanduser().resolve()),
            file_sha256=ctx.sha,
            ocr_engine=ctx.ocr_engine,
            ocr_mean_confidence=ctx.ocr_mean_confidence,
            extraction_method="manual",
            tags=build_zettel_tags(proposal.document.type, ctx.issuer_slug, proposal.document.date),
        )
    except Exception as exc:
        return CommandResult(success=False, error=f"frontmatter validation failed: {exc}")


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
