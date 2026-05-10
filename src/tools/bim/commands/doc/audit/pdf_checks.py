"""Per-PDF audit check functions (one per row of PRD 00037 §9 audit table).

Each function is pure and returns ``list[PdfFinding]`` (empty = clean).
``OcrQualityReader`` is a DI seam so the orchestrator owns the adapter.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from bim.commands.doc.audit.models import PdfFinding
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.naming import CANONICAL_REGEX
from bim.commands.doc.shared.state_db import StateDB

__all__ = [
    "OcrQualityReader",
    "check_doc_type_valid",
    "check_filename_canonical",
    "check_issuer_registered",
    "check_ocr",
    "check_state_db_entry",
    "check_zettel_exists",
    "derive_zettel_filename",
    "resolve_zettel_paths",
]


# (has_text, mean_confidence_or_None) -- None confidence means "not computable".
OcrQualityReader = Callable[[Path], "tuple[bool, float | None]"]


def derive_zettel_filename(pdf_path: Path) -> str:
    """Mirror ``ZettelWriter._derive_basename``: strip ``.pdf`` (case-insensitive),
    append ``.md``.
    """
    leaf = pdf_path.name
    if leaf.lower().endswith(".pdf"):
        leaf = leaf[: -len(".pdf")]
    return f"{leaf}.md"


def resolve_zettel_paths(
    pdf_path: Path,
    folder_slug: str,
    vault_root: Path,
    vault_documents_subdir: str,
) -> tuple[Path, Path]:
    """Return ``(per_issuer_path, legacy_flat_path)`` for the given PDF."""
    basename = derive_zettel_filename(pdf_path)
    base_dir = vault_root / vault_documents_subdir
    return (base_dir / folder_slug / basename, base_dir / basename)


def _coerce_slug(folder_slug: str | None) -> str | None:
    if folder_slug is None or folder_slug == "":
        return None
    return folder_slug


def check_filename_canonical(pdf_path: Path, folder_slug: str | None) -> list[PdfFinding]:
    """Flag PDFs whose basename does not match :data:`CANONICAL_REGEX`."""
    if CANONICAL_REGEX.match(pdf_path.name):
        return []
    return [
        PdfFinding(
            pdf_path=str(pdf_path),
            issuer_slug=_coerce_slug(folder_slug),
            doc_type=None,
            code="non_canonical_filename",
        )
    ]


def check_issuer_registered(folder_slug: str, registry: IssuerRegistry, pdf_path: Path) -> list[PdfFinding]:
    """Flag PDFs whose containing folder slug is not registered in
    ``issuers.yml``. An empty folder slug (PDF directly under the
    business root) is treated as unknown.
    """
    if folder_slug != "" and folder_slug in registry.issuers:
        return []
    return [
        PdfFinding(
            pdf_path=str(pdf_path),
            issuer_slug=_coerce_slug(folder_slug),
            doc_type=None,
            code="unknown_issuer",
            detail=f"folder: {folder_slug!r}",
        )
    ]


def check_doc_type_valid(pdf_path: Path, folder_slug: str | None, registry: IssuerRegistry) -> list[PdfFinding]:
    """Flag PDFs whose canonical-filename ``doc_type`` slot is not in the
    registry's allowed ``doc_types``. Non-canonical filenames return
    ``[]`` so the same PDF is not flagged twice.
    """
    match = CANONICAL_REGEX.match(pdf_path.name)
    if match is None:
        return []
    doc_type = match.group("doc_type")
    if doc_type in registry.doc_types:
        return []
    return [
        PdfFinding(
            pdf_path=str(pdf_path),
            issuer_slug=_coerce_slug(folder_slug),
            doc_type=doc_type,
            code="invalid_doc_type",
            detail=f"doc_type: {doc_type!r}",
        )
    ]


def check_zettel_exists(
    pdf_path: Path,
    folder_slug: str,
    vault_root: Path,
    vault_documents_subdir: str,
) -> tuple[list[PdfFinding], list[str]]:
    """Verify that a zettel exists for ``pdf_path``.

    Returns ``(findings, legacy_paths)``. ``legacy_paths`` is the
    PRD 00036 contract: any zettel found at the legacy flat layout
    (``<docs>/<basename>``) instead of the per-issuer layout
    (``<docs>/<slug>/<basename>``) is reported separately so callers
    can drive a migration. When ``folder_slug`` is empty the per-issuer
    probe is skipped and only the legacy path is checked.
    """
    per_issuer, legacy = resolve_zettel_paths(pdf_path, folder_slug, vault_root, vault_documents_subdir)
    if folder_slug != "" and per_issuer.is_file():
        return ([], [])
    if legacy.is_file():
        return ([], [str(legacy)])
    return (
        [
            PdfFinding(
                pdf_path=str(pdf_path),
                issuer_slug=_coerce_slug(folder_slug),
                doc_type=None,
                code="missing_zettel",
            )
        ],
        [],
    )


def check_ocr(
    pdf_path: Path,
    low_confidence_threshold: float,
    ocr_quality_reader: OcrQualityReader,
    folder_slug: str | None,
) -> list[PdfFinding]:
    """Flag PDFs without OCR text or with mean confidence below the
    threshold. ``confidence is None`` with text present is treated as
    "not assessable" -- not itself an audit failure.
    """
    has_text, confidence = ocr_quality_reader(pdf_path)
    if not has_text:
        return [
            PdfFinding(
                pdf_path=str(pdf_path),
                issuer_slug=_coerce_slug(folder_slug),
                doc_type=None,
                code="missing_ocr",
            )
        ]
    if confidence is not None and confidence < low_confidence_threshold:
        return [
            PdfFinding(
                pdf_path=str(pdf_path),
                issuer_slug=_coerce_slug(folder_slug),
                doc_type=None,
                code="low_ocr_confidence",
                detail=f"mean_confidence: {confidence:.2f}",
            )
        ]
    return []


def check_state_db_entry(
    pdf_path: Path,
    sha256_hex: str,
    state_db: StateDB,
    folder_slug: str | None,
) -> list[PdfFinding]:
    """Flag PDFs whose sha256 is not recorded in the state DB's
    ``processed`` table.
    """
    if state_db.dedup(sha256_hex).is_duplicate:
        return []
    return [
        PdfFinding(
            pdf_path=str(pdf_path),
            issuer_slug=_coerce_slug(folder_slug),
            doc_type=None,
            code="missing_state_db_entry",
        )
    ]
