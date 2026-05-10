"""Cross-path consistency test for PRD 00035 success criterion 8.

Drives the same logical document through the pipeline (ingest) and promote
frontmatter builders and asserts the resulting v1 frontmatter is equivalent
modulo ``extraction-method`` (which legitimately differs by design — ingest
records the LLM/rule that produced the values; promote always records
``manual`` because a human approved the triage proposal).

Both production code paths funnel through the helpers in
``bim.commands.doc.shared.pipeline_helpers``: ``build_filing_frontmatter``
for ingest, ``build_promote_frontmatter`` for promote. This test calls those
helpers directly so any drift in either production path is caught.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from bim.commands.doc.shared.classifier import ClassifyResult
from bim.commands.doc.shared.extractor import ExtractResult
from bim.commands.doc.shared.ocr import OCRResult
from bim.commands.doc.shared.pipeline_helpers import (
    _FilingContext,
    _PromoteFrontmatterContext,
    build_filing_frontmatter,
    build_promote_frontmatter,
)
from bim.commands.doc.shared.triage import (
    DocumentProposal,
    IssuerProposal,
    OCRProposal,
    SourceProposal,
    TriageProposal,
    ZettelPreview,
)
from bim.commands.doc.shared.zettel_writer import DocumentZettelFrontmatter
from bim.params.doc_ingest import IngestParams

# Logical document fields used by both code paths. A single source of truth so
# any drift between ingest and promote constructions is caught.
ISSUER_SLUG = "cez-as"
ISSUER_DISPLAY = "ČEZ a.s."
DOC_TYPE = "invoice"
DOC_NUMBER = "7102105594"
DOC_DATE = date(2021, 3, 11)
DOC_AMOUNT = 4218.0
DOC_CURRENCY = "CZK"
DOC_LANGUAGE = "cs"
INGESTED_AT = datetime(2026, 5, 4, 14, 30, 22, tzinfo=timezone(timedelta(hours=2)))
INGEST_SOURCE = "email"
ZK_TIMESTAMP = "20210311083422"
SHA = "3f4a8c2b91e7d5" + ("0" * (64 - len("3f4a8c2b91e7d5")))
OCR_ENGINE = "tesseract"
OCR_MEAN_CONFIDENCE = 0.91
TARGET_PDF = Path("/Users/bob/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf")


def _build_ingest_frontmatter(extraction_method: str, doc_date: date | None = DOC_DATE) -> DocumentZettelFrontmatter:
    """Construct frontmatter via the pipeline (ingest) code path."""
    ctx = _FilingContext(
        params=IngestParams(
            staging_path=Path("/tmp/staging/input.pdf"),
            source=INGEST_SOURCE,
        ),
        sha=SHA,
        ocr_result=OCRResult(
            ocr_text="ČEZ a.s.\nFaktura č. 7102105594\n",
            pdf_path=Path("/tmp/unused.pdf"),
            was_redone=False,
            original_backup_path=None,
            mean_confidence=OCR_MEAN_CONFIDENCE,
            pages=2,
        ),
        classify_result=ClassifyResult(
            issuer_slug=ISSUER_SLUG,
            issuer_display=ISSUER_DISPLAY,
            doc_type=DOC_TYPE,
            language=DOC_LANGUAGE,
            confidence=0.95,
        ),
        extract_result=ExtractResult(
            doc_type=DOC_TYPE,
            number=DOC_NUMBER,
            date=doc_date,
            amount=DOC_AMOUNT,
            currency=DOC_CURRENCY,
        ),
        issuer_slug=ISSUER_SLUG,
        issuer_display=ISSUER_DISPLAY,
        extraction_method=extraction_method,
    )
    return build_filing_frontmatter(
        ctx,
        zk_timestamp=ZK_TIMESTAMP,
        target_pdf=TARGET_PDF,
        ingested_at=INGESTED_AT,
        ocr_engine=OCR_ENGINE,
    )


def _build_proposal(doc_date: date | None = DOC_DATE) -> TriageProposal:
    """Synthesise the TriageProposal a human-approved triage would yield for the logical document."""
    # ``year/...`` tag mirrors what the ingest path's ``build_zettel_tags``
    # emits when ``doc_date`` is ``None`` (the helper omits the year tag in
    # that case). Keeping these in sync is part of what the consistency
    # test guards.
    tags = [f"document/{DOC_TYPE}", f"issuer/{ISSUER_SLUG}"]
    if doc_date is not None:
        tags.append(f"year/{doc_date.year}")
    return TriageProposal(
        approved=True,
        register_issuer=False,
        issuer=IssuerProposal(slug=ISSUER_SLUG, display_name=ISSUER_DISPLAY, confidence=0.95),
        document=DocumentProposal(
            type=DOC_TYPE,
            number=DOC_NUMBER,
            date=doc_date,
            amount=DOC_AMOUNT,
            currency=DOC_CURRENCY,
            language=DOC_LANGUAGE,
        ),
        source=SourceProposal(kind=INGEST_SOURCE, staging_path=Path("/tmp/staging/input.pdf"), sha256=SHA),
        ocr=OCRProposal(engine=OCR_ENGINE, languages=[DOC_LANGUAGE], mean_confidence=OCR_MEAN_CONFIDENCE, pages=2),
        triage_reasons=["low_confidence_classify"],
        zettel_preview=ZettelPreview(
            id=ZK_TIMESTAMP,
            title=f"{ISSUER_DISPLAY} {DOC_TYPE} {DOC_NUMBER}",
            ingested_at=INGESTED_AT,
            tags=tags,
        ),
    )


def _build_promote_frontmatter(doc_date: date | None = DOC_DATE) -> DocumentZettelFrontmatter:
    """Construct frontmatter via the production promote helper.

    Drives ``build_promote_frontmatter`` directly (the same helper that
    ``CommandPromote._build_frontmatter`` calls), so drift in the production
    promote path surfaces here.
    """
    proposal = _build_proposal(doc_date=doc_date)
    ctx = _PromoteFrontmatterContext(
        proposal=proposal,
        issuer_display=ISSUER_DISPLAY,
        issuer_slug=ISSUER_SLUG,
        zk_timestamp=ZK_TIMESTAMP,
        target_pdf=TARGET_PDF,
        sha=SHA,
        ocr_engine=OCR_ENGINE,
        ocr_mean_confidence=OCR_MEAN_CONFIDENCE,
        # ``ingest_today`` deliberately differs from ``INGESTED_AT.date()`` so
        # any code path that uses ``date.today()`` / ``ingest_today`` for the
        # ``doc-date`` fallback (instead of the proposal's ``ingested_at``)
        # produces a divergent value here and is caught by the no-date
        # parametrize variant. See PRD 00035 success metric #8.
        ingest_today=date(2099, 1, 1),
    )
    result = build_promote_frontmatter(ctx)
    assert isinstance(result, DocumentZettelFrontmatter), result
    return result


class TestPipelinePromoteFrontmatterConsistency:
    def test_equivalent_inputs_produce_equivalent_frontmatter_modulo_extraction_method(self) -> None:
        """PRD 00035 criterion 8: equivalent inputs through both paths yield equivalent frontmatter."""
        fm_ingest = _build_ingest_frontmatter(extraction_method="rule:cez-invoice-2024-template:v1")
        fm_promote = _build_promote_frontmatter()

        ingest_dump = fm_ingest.model_dump(by_alias=True, mode="python")
        promote_dump = fm_promote.model_dump(by_alias=True, mode="python")

        # extraction-method legitimately differs by design.
        ingest_method = ingest_dump.pop("extraction-method")
        promote_method = promote_dump.pop("extraction-method")
        assert ingest_method == "rule:cez-invoice-2024-template:v1"
        assert promote_method == "manual"

        # Everything else must match exactly.
        assert ingest_dump == promote_dump

    def test_field_order_is_identical_across_paths(self) -> None:
        """Both paths must declare keys in the same order (deterministic on-disk shape)."""
        fm_ingest = _build_ingest_frontmatter(extraction_method="manual")
        fm_promote = _build_promote_frontmatter()

        # Pydantic preserves declaration order; both call the same model.
        assert list(fm_ingest.model_dump(by_alias=True).keys()) == list(fm_promote.model_dump(by_alias=True).keys())

    @pytest.mark.parametrize(
        "extraction_method",
        ["llm:qwen2.5:7b-instruct", "rule:cez-invoice-2024-template:v1", "rule+llm:cez-partial:v2"],
    )
    def test_consistency_holds_for_every_ingest_extraction_method(self, extraction_method: str) -> None:
        """Whatever extraction-method ingest records, promote's manual still matches everything else."""
        fm_ingest = _build_ingest_frontmatter(extraction_method=extraction_method)
        fm_promote = _build_promote_frontmatter()

        ingest_dump = fm_ingest.model_dump(by_alias=True, mode="python")
        promote_dump = fm_promote.model_dump(by_alias=True, mode="python")

        ingest_dump.pop("extraction-method")
        promote_dump.pop("extraction-method")

        assert ingest_dump == promote_dump

    @pytest.mark.parametrize(
        "doc_date",
        [DOC_DATE, None],
        ids=["date-present", "date-none"],
    )
    def test_consistency_holds_when_doc_date_is_missing(self, doc_date: date | None) -> None:
        """PRD 00035 criterion 8: equivalence must also hold when ``doc_date`` is missing.

        For date-less documents, both helpers must fall back to the same
        value. The filing helper uses ``ingested_at.date()``; the promote
        helper used to use ``date.today()`` (via ``ctx.ingest_today``), which
        produced a different ``doc-date`` whenever the document was promoted
        on a different day from the one it was ingested. This parametrize
        variant pins the behaviour: both paths fall back to the proposal's
        ``ingested_at.date()``.

        ``ingest_today`` in the promote context is set to ``date(2099, 1, 1)``
        (clearly synthetic) so a regression that re-introduces the
        ``date.today()``/``ingest_today`` fallback would diverge here even
        when run on the same day as ``INGESTED_AT.date()``.
        """
        fm_ingest = _build_ingest_frontmatter(extraction_method="manual", doc_date=doc_date)
        fm_promote = _build_promote_frontmatter(doc_date=doc_date)

        ingest_dump = fm_ingest.model_dump(by_alias=True, mode="python")
        promote_dump = fm_promote.model_dump(by_alias=True, mode="python")

        ingest_dump.pop("extraction-method")
        promote_dump.pop("extraction-method")

        assert ingest_dump == promote_dump
        # Sanity: the no-date variant should resolve ``doc-date`` from the
        # ingested-at datetime, not from ``date.today()`` or ``ingest_today``.
        if doc_date is None:
            assert promote_dump["doc-date"] == INGESTED_AT.date()
