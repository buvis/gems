"""Cross-path consistency test for PRD 00035 success criterion 8.

Drives the same logical document through the pipeline (ingest) and promote
frontmatter builders and asserts the resulting v1 frontmatter is equivalent
modulo ``extraction-method`` (which legitimately differs by design — ingest
records the LLM/rule that produced the values; promote always records
``manual`` because a human approved the triage proposal).

The two paths construct ``DocumentZettelFrontmatter`` from different input
shapes (``_FilingContext`` vs ``TriageProposal``) but for equivalent inputs
the on-disk YAML must be the same.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from bim.commands.doc.shared.classifier import ClassifyResult
from bim.commands.doc.shared.extractor import ExtractResult
from bim.commands.doc.shared.ocr import OCRResult
from bim.commands.doc.shared.pipeline_helpers import _FilingContext, build_filing_frontmatter
from bim.commands.doc.shared.zettel_helpers import build_zettel_tags, compose_zettel_title
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


def _build_ingest_frontmatter(extraction_method: str) -> DocumentZettelFrontmatter:
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
            date=DOC_DATE,
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


def _build_promote_frontmatter() -> DocumentZettelFrontmatter:
    """Construct frontmatter via the promote code path (mirrors CommandPromote._build_frontmatter)."""
    title = compose_zettel_title(
        issuer=ISSUER_DISPLAY,
        doc_type=DOC_TYPE,
        doc_number=DOC_NUMBER,
        doc_title=None,
    )
    return DocumentZettelFrontmatter(
        id=int(ZK_TIMESTAMP),
        title=title,
        doc_type=DOC_TYPE,
        issuer=ISSUER_DISPLAY,
        doc_number=DOC_NUMBER,
        doc_date=DOC_DATE,
        doc_amount=DOC_AMOUNT,
        doc_currency=DOC_CURRENCY,
        doc_language=DOC_LANGUAGE,
        ingested_at=INGESTED_AT,
        ingest_source=INGEST_SOURCE,
        file_path=str(TARGET_PDF.expanduser().resolve()),
        file_sha256=SHA,
        ocr_engine=OCR_ENGINE,
        ocr_mean_confidence=OCR_MEAN_CONFIDENCE,
        extraction_method="manual",
        tags=build_zettel_tags(DOC_TYPE, ISSUER_SLUG, DOC_DATE),
    )


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
