"""Unit tests for the per-PDF audit check functions.

Each check is pure: no console I/O, no file mutation. They return lists
of ``PdfFinding`` (empty list = clean) and, in the case of
``check_zettel_exists``, an additional list of legacy-layout zettel paths
(per the PRD 00036 contract).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from bim.commands.doc.audit.pdf_checks import (
    check_doc_type_valid,
    check_filename_canonical,
    check_issuer_registered,
    check_ocr,
    check_state_db_entry,
    check_zettel_exists,
    derive_zettel_filename,
    resolve_zettel_paths,
)
from bim.commands.doc.shared.issuers import IssuerEntry, IssuerRegistry
from bim.commands.doc.shared.state_db import (
    ProcessedRow,
    open_state_db,
)


def _make_registry(
    *,
    doc_types: list[str] | None = None,
    issuers: dict[str, IssuerEntry] | None = None,
) -> IssuerRegistry:
    return IssuerRegistry(
        version=1,
        doc_types=doc_types if doc_types is not None else ["invoice", "statement"],
        reserved_slugs=[],
        issuers=issuers
        if issuers is not None
        else {
            "cez-as": IssuerEntry(slug="cez-as", display_name="ČEZ a.s."),
        },
    )


CANONICAL_NAME = "20260101000000-cez-as-foo.invoice.pdf"


class TestDeriveZettelFilename:
    def test_strips_lowercase_pdf(self) -> None:
        assert derive_zettel_filename(Path("/tmp/Foo.pdf")) == "Foo.md"

    def test_strips_uppercase_pdf(self) -> None:
        assert derive_zettel_filename(Path("/tmp/Foo.PDF")) == "Foo.md"

    def test_strips_mixed_case_pdf(self) -> None:
        assert derive_zettel_filename(Path("/tmp/Foo.Pdf")) == "Foo.md"

    def test_preserves_other_extensions(self) -> None:
        # Non-PDF leaf names get .md appended, leaving the original ext alone.
        assert derive_zettel_filename(Path("/tmp/Foo.txt")) == "Foo.txt.md"

    def test_canonical_pdf_filename(self) -> None:
        assert derive_zettel_filename(Path(f"/tmp/{CANONICAL_NAME}")) == "20260101000000-cez-as-foo.invoice.md"


class TestResolveZettelPaths:
    def test_returns_per_issuer_and_legacy(self, tmp_path: Path) -> None:
        pdf = tmp_path / "business" / "cez-as" / CANONICAL_NAME
        per_issuer, legacy = resolve_zettel_paths(
            pdf,
            folder_slug="cez-as",
            vault_root=tmp_path / "vault",
            vault_documents_subdir="Zettelkasten/documents",
        )
        basename = "20260101000000-cez-as-foo.invoice.md"
        assert per_issuer == tmp_path / "vault" / "Zettelkasten/documents" / "cez-as" / basename
        assert legacy == tmp_path / "vault" / "Zettelkasten/documents" / basename


class TestCheckFilenameCanonical:
    def test_canonical_passes(self, tmp_path: Path) -> None:
        pdf = tmp_path / "cez-as" / CANONICAL_NAME
        assert check_filename_canonical(pdf, "cez-as") == []

    def test_non_canonical_emits_finding(self, tmp_path: Path) -> None:
        pdf = tmp_path / "cez-as" / "scan.pdf"
        findings = check_filename_canonical(pdf, "cez-as")
        assert len(findings) == 1
        assert findings[0].code == "non_canonical_filename"
        assert findings[0].pdf_path == str(pdf)
        assert findings[0].issuer_slug == "cez-as"
        assert findings[0].doc_type is None

    def test_empty_folder_slug_coerced_to_none(self, tmp_path: Path) -> None:
        pdf = tmp_path / "scan.pdf"
        findings = check_filename_canonical(pdf, "")
        assert len(findings) == 1
        assert findings[0].issuer_slug is None

    def test_none_folder_slug_passes_through(self, tmp_path: Path) -> None:
        pdf = tmp_path / "scan.pdf"
        findings = check_filename_canonical(pdf, None)
        assert len(findings) == 1
        assert findings[0].issuer_slug is None


class TestCheckIssuerRegistered:
    def test_registered_passes(self, tmp_path: Path) -> None:
        registry = _make_registry()
        pdf = tmp_path / "cez-as" / CANONICAL_NAME
        assert check_issuer_registered("cez-as", registry, pdf) == []

    def test_unknown_issuer_emits_finding(self, tmp_path: Path) -> None:
        registry = _make_registry()
        pdf = tmp_path / "cez" / "scan.pdf"
        findings = check_issuer_registered("cez", registry, pdf)
        assert len(findings) == 1
        assert findings[0].code == "unknown_issuer"
        assert findings[0].issuer_slug == "cez"
        assert findings[0].pdf_path == str(pdf)
        assert findings[0].detail == "folder: 'cez'"

    def test_empty_folder_slug_emits_finding(self, tmp_path: Path) -> None:
        registry = _make_registry()
        pdf = tmp_path / "scan.pdf"
        findings = check_issuer_registered("", registry, pdf)
        assert len(findings) == 1
        assert findings[0].code == "unknown_issuer"
        assert findings[0].issuer_slug is None


class TestCheckDocTypeValid:
    def test_valid_doc_type_passes(self, tmp_path: Path) -> None:
        registry = _make_registry(doc_types=["invoice", "statement"])
        pdf = tmp_path / "cez-as" / CANONICAL_NAME
        assert check_doc_type_valid(pdf, "cez-as", registry) == []

    def test_invalid_doc_type_emits_finding(self, tmp_path: Path) -> None:
        # Restrict registry to only "statement"; canonical name uses "invoice".
        registry = _make_registry(doc_types=["statement"])
        pdf = tmp_path / "cez-as" / CANONICAL_NAME
        findings = check_doc_type_valid(pdf, "cez-as", registry)
        assert len(findings) == 1
        assert findings[0].code == "invalid_doc_type"
        assert findings[0].doc_type == "invoice"
        assert findings[0].issuer_slug == "cez-as"
        assert findings[0].detail == "doc_type: 'invoice'"

    def test_non_canonical_filename_returns_empty(self, tmp_path: Path) -> None:
        registry = _make_registry()
        pdf = tmp_path / "cez-as" / "random.pdf"
        # non-canonical => filename check already flags it; doc_type silent.
        assert check_doc_type_valid(pdf, "cez-as", registry) == []


class TestCheckZettelExists:
    @pytest.fixture
    def setup(self, tmp_path: Path) -> dict[str, Path]:
        vault = tmp_path / "vault"
        docs = vault / "Zettelkasten/documents"
        docs.mkdir(parents=True)
        per_issuer_dir = docs / "cez-as"
        per_issuer_dir.mkdir()
        pdf = tmp_path / "business" / "cez-as" / CANONICAL_NAME
        pdf.parent.mkdir(parents=True)
        pdf.touch()
        basename = "20260101000000-cez-as-foo.invoice.md"
        return {
            "vault": vault,
            "docs": docs,
            "per_issuer": per_issuer_dir / basename,
            "legacy": docs / basename,
            "pdf": pdf,
        }

    def test_clean_zettel_per_issuer_returns_empty(self, setup: dict[str, Path]) -> None:
        setup["per_issuer"].touch()
        findings, legacy = check_zettel_exists(setup["pdf"], "cez-as", setup["vault"], "Zettelkasten/documents")
        assert findings == []
        assert legacy == []

    def test_legacy_layout_zettel_returns_legacy_path(self, setup: dict[str, Path]) -> None:
        setup["legacy"].touch()
        findings, legacy = check_zettel_exists(setup["pdf"], "cez-as", setup["vault"], "Zettelkasten/documents")
        assert findings == []
        assert legacy == [str(setup["legacy"])]

    def test_missing_zettel_returns_finding(self, setup: dict[str, Path]) -> None:
        findings, legacy = check_zettel_exists(setup["pdf"], "cez-as", setup["vault"], "Zettelkasten/documents")
        assert len(findings) == 1
        assert findings[0].code == "missing_zettel"
        assert findings[0].issuer_slug == "cez-as"
        assert findings[0].pdf_path == str(setup["pdf"])
        assert legacy == []

    def test_per_issuer_takes_precedence_over_legacy(self, setup: dict[str, Path]) -> None:
        setup["per_issuer"].touch()
        setup["legacy"].touch()
        findings, legacy = check_zettel_exists(setup["pdf"], "cez-as", setup["vault"], "Zettelkasten/documents")
        assert findings == []
        assert legacy == []

    def test_empty_folder_slug_only_checks_legacy(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        docs = vault / "Zettelkasten/documents"
        docs.mkdir(parents=True)
        pdf = tmp_path / "scan.pdf"
        pdf.touch()
        # No legacy file -> missing_zettel.
        findings, legacy = check_zettel_exists(pdf, "", vault, "Zettelkasten/documents")
        assert len(findings) == 1
        assert findings[0].code == "missing_zettel"
        assert findings[0].issuer_slug is None
        assert legacy == []

    def test_empty_folder_slug_finds_legacy(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        docs = vault / "Zettelkasten/documents"
        docs.mkdir(parents=True)
        pdf = tmp_path / "scan.pdf"
        pdf.touch()
        legacy_path = docs / "scan.md"
        legacy_path.touch()
        findings, legacy = check_zettel_exists(pdf, "", vault, "Zettelkasten/documents")
        assert findings == []
        assert legacy == [str(legacy_path)]


class TestCheckOcr:
    def test_missing_text_emits_missing_ocr(self, tmp_path: Path) -> None:
        pdf = tmp_path / "scan.pdf"
        findings = check_ocr(pdf, 0.7, lambda _p: (False, None), "cez-as")
        assert len(findings) == 1
        assert findings[0].code == "missing_ocr"
        assert findings[0].issuer_slug == "cez-as"
        assert findings[0].pdf_path == str(pdf)

    def test_low_confidence_emits_finding_with_detail(self, tmp_path: Path) -> None:
        pdf = tmp_path / "scan.pdf"
        findings = check_ocr(pdf, 0.7, lambda _p: (True, 0.5), "cez-as")
        assert len(findings) == 1
        assert findings[0].code == "low_ocr_confidence"
        assert findings[0].detail is not None
        assert "0.50" in findings[0].detail

    def test_high_confidence_clean(self, tmp_path: Path) -> None:
        pdf = tmp_path / "scan.pdf"
        assert check_ocr(pdf, 0.7, lambda _p: (True, 0.9), "cez-as") == []

    def test_none_confidence_with_text_clean(self, tmp_path: Path) -> None:
        pdf = tmp_path / "scan.pdf"
        # Has text but confidence not computable: not a finding.
        assert check_ocr(pdf, 0.7, lambda _p: (True, None), "cez-as") == []

    def test_empty_folder_slug_coerced_to_none(self, tmp_path: Path) -> None:
        pdf = tmp_path / "scan.pdf"
        findings = check_ocr(pdf, 0.7, lambda _p: (False, None), "")
        assert len(findings) == 1
        assert findings[0].issuer_slug is None


class TestCheckStateDbEntry:
    def test_missing_entry_emits_finding(self, tmp_path: Path) -> None:
        pdf = tmp_path / "cez-as" / CANONICAL_NAME
        with open_state_db(tmp_path / "s.db") as db:
            sha = "0" * 64
            findings = check_state_db_entry(pdf, sha, db, "cez-as")
        assert len(findings) == 1
        assert findings[0].code == "missing_state_db_entry"
        assert findings[0].issuer_slug == "cez-as"
        assert findings[0].pdf_path == str(pdf)

    def test_present_entry_clean(self, tmp_path: Path) -> None:
        pdf = tmp_path / "cez-as" / CANONICAL_NAME
        with open_state_db(tmp_path / "s.db") as db:
            sha = "a" * 64
            db.record_processed(
                ProcessedRow(
                    sha256=sha,
                    canonical_filename=CANONICAL_NAME,
                    issuer_slug="cez-as",
                    doc_type="invoice",
                    processed_at=datetime.now(timezone.utc),
                    extraction_method="test",
                )
            )
            assert check_state_db_entry(pdf, sha, db, "cez-as") == []

    def test_empty_folder_slug_coerced_to_none(self, tmp_path: Path) -> None:
        pdf = tmp_path / "scan.pdf"
        with open_state_db(tmp_path / "s.db") as db:
            findings = check_state_db_entry(pdf, "0" * 64, db, "")
        assert findings[0].issuer_slug is None
