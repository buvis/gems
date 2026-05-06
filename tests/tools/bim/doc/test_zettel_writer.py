from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from bim.commands.doc.shared.settings_models import ZettelSettings
from bim.commands.doc.shared.zettel_writer import (
    DocumentZettelFrontmatter,
    ZettelWriter,
    build_zettel_body,
)
from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository import (
    MarkdownZettelRepository,
)
from pydantic import ValidationError

SAMPLE_SHA = "3f4a8c2b91e7d5" + ("0" * (64 - len("3f4a8c2b91e7d5")))
SAMPLE_FILE_PATH = (
    "~/Library/Mobile Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf"
)
SAMPLE_OCR_TEXT = (
    "ČEZ a.s.\nFaktura č. 7102105594\nDatum vystavení: 11.03.2021\nObdobí: 02/2021\nCelkem k úhradě: 4 218,00 Kč\n"
)


def _frontmatter_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "20210311083422",
        "doc_type": "invoice",
        "issuer_slug": "cez-as",
        "issuer_display": "ČEZ a.s.",
        "doc_number": "7102105594",
        "doc_date": date(2021, 3, 11),
        "doc_amount": 4218.0,
        "doc_currency": "CZK",
        "doc_language": "cs",
        "ingest_date": date(2026, 5, 4),
        "ingest_source": "email",
        "file_path": SAMPLE_FILE_PATH,
        "file_sha256": SAMPLE_SHA,
        "ocr_engine": "tesseract",
        "ocr_mean_confidence": 0.91,
        "extraction_method": "rule:cez-invoice-2024-template:v1",
        "tags": ["document/invoice", "issuer/cez-as", "year/2021"],
    }
    base.update(overrides)
    return base


@pytest.fixture
def frontmatter() -> DocumentZettelFrontmatter:
    return DocumentZettelFrontmatter(**_frontmatter_kwargs())


class TestDocumentZettelFrontmatter:
    def test_valid_full_frontmatter_constructs_cleanly(self) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs())
        assert fm.id == "20210311083422"
        assert fm.type == "document"
        assert fm.doc_type == "invoice"
        assert fm.issuer_slug == "cez-as"
        assert fm.issuer_display == "ČEZ a.s."
        assert fm.doc_number == "7102105594"
        assert fm.doc_date == date(2021, 3, 11)
        assert fm.doc_amount == 4218.0
        assert fm.doc_currency == "CZK"
        assert fm.ingest_source == "email"
        assert fm.file_sha256 == SAMPLE_SHA
        assert fm.extraction_method == "rule:cez-invoice-2024-template:v1"
        assert fm.tags == ["document/invoice", "issuer/cez-as", "year/2021"]

    def test_invalid_id_non_14_digits_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(id="abc"))

    def test_invalid_doc_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_type="not-a-type"))

    def test_invalid_issuer_slug_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(issuer_slug="Has Spaces"))

    def test_file_path_must_start_with_tilde_slash(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(file_path="/absolute/path.pdf"))

    def test_invalid_file_sha256_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(file_sha256="abc"))

    def test_invalid_file_sha256_non_hex_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(file_sha256="z" * 64))

    def test_invalid_ingest_source_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(ingest_source="random"))

    def test_extraction_method_validates_known_patterns(self) -> None:
        for method in (
            "manual",
            "filename",
            "llm:qwen2.5",
            # Ollama canonical model id is name:tag — must round-trip through validation.
            "llm:qwen2.5:7b-instruct",
            "llm:llama2:13b",
            "rule:foo:v1",
            "rule+llm:foo:v1",
        ):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(extraction_method=method))

        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(extraction_method="banana"))

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(unexpected_field="x"))

    def test_doc_number_can_be_none(self) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_number=None))
        assert fm.doc_number is None


class TestBuildZettelBody:
    def test_body_contains_header_and_link_and_callout(self, frontmatter: DocumentZettelFrontmatter) -> None:
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        assert "# Invoice 7102105594 — ČEZ a.s." in body
        assert f"[Open PDF]({SAMPLE_FILE_PATH})" in body
        assert "> [!quote]- Full text" in body
        assert "**Date:** 2021-03-11" in body
        # Czech-locale: thousands separated by NBSP, trailing .0 dropped
        assert "**Amount:** 4\xa0218 CZK" in body

        # OCR text lines should be `> `-prefixed inside the callout
        for ocr_line in SAMPLE_OCR_TEXT.splitlines():
            if ocr_line:
                assert f"> {ocr_line}" in body

    def test_body_omits_amount_line_when_amount_none(self) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_amount=None, doc_currency=None))
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        assert "**Amount:**" not in body

    def test_body_omits_doc_number_in_header_when_none(self) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_number=None))
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        assert "# Invoice — ČEZ a.s." in body

    def test_body_truncation_when_ocr_text_max_chars_set(self, frontmatter: DocumentZettelFrontmatter) -> None:
        long_ocr = "x" * 200
        settings = ZettelSettings(ocr_text_max_chars=50)
        body = build_zettel_body(frontmatter, long_ocr, settings)
        assert ("…" in body) or ("[truncated]" in body)
        # Truncated body should not contain the full 200-char run
        assert ("x" * 200) not in body
        # But the callout structure should remain
        assert "> [!quote]- Full text" in body

    def test_body_no_truncation_when_max_chars_zero(self, frontmatter: DocumentZettelFrontmatter) -> None:
        long_ocr = "x" * 200
        settings = ZettelSettings(ocr_text_max_chars=0)
        body = build_zettel_body(frontmatter, long_ocr, settings)
        assert ("x" * 200) in body

    def test_body_default_settings_no_truncation(self, frontmatter: DocumentZettelFrontmatter) -> None:
        long_ocr = "x" * 200
        body = build_zettel_body(frontmatter, long_ocr)
        assert ("x" * 200) in body


class TestZettelWriter:
    def test_write_round_trip_preserves_all_metadata_and_paths(
        self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter
    ) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body)

        expected_path = tmp_path / "Zettelkasten" / "documents" / "20210311083422-cez-as-7102105594.invoice.md"
        assert target == expected_path
        assert target.exists()

        zettel = MarkdownZettelRepository(zettelkasten_path=None).find_by_location(str(target))
        meta = zettel.get_data().metadata

        # MarkdownZettelRepository normalises frontmatter keys to kebab-case
        # via StringOperator.as_note_field_name, so doc_number → doc-number etc.
        assert meta["id"] == "20210311083422"
        assert meta["doc-number"] == "7102105594"
        # doc_date may come back as a date object or as a string depending on parser
        assert str(meta["doc-date"]).startswith("2021-03-11")
        assert str(meta["file-path"]).startswith("~/")
        assert meta["doc-type"] == "invoice"
        assert meta["extraction-method"] == "rule:cez-invoice-2024-template:v1"
        assert isinstance(meta["tags"], list)
        assert "document/invoice" in meta["tags"]

    def test_write_creates_parent_dir(self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter) -> None:
        subdir = "deep/nested/path"
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir=subdir,
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body)

        expected_parent = tmp_path / "deep" / "nested" / "path"
        assert expected_parent.exists()
        assert expected_parent.is_dir()
        assert target.parent == expected_parent
        assert target.exists()
        assert target.name == "20210311083422-cez-as-7102105594.invoice.md"

    def test_yaml_serialization_quotes_id_and_doc_number(
        self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter
    ) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body)

        text = target.read_text(encoding="utf-8")
        assert 'id: "20210311083422"' in text
        assert 'doc_number: "7102105594"' in text
        assert "doc_date: 2021-03-11" in text
        # Date must NOT be quoted
        assert 'doc_date: "2021-03-11"' not in text

    def test_yaml_serialization_preserves_unicode_for_issuer_display(
        self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter
    ) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body)

        text = target.read_text(encoding="utf-8")
        assert "issuer_display: ČEZ a.s." in text
        # No \u00xx escape sequences for the C-with-caron character
        assert "\\u010c" not in text.lower()

    def test_yaml_serialization_writes_file_path_as_tilde_string(
        self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter
    ) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body)

        text = target.read_text(encoding="utf-8")
        # Path is written with the literal tilde, NOT expanded to /Users/...
        assert "file_path:" in text
        assert "~/" in text
        # Sanity-check no expansion happened in the frontmatter block
        frontmatter_block = text.split("---", 2)[1]
        assert "/Users/" not in frontmatter_block

    def test_write_doc_number_none_serializes_as_null_or_omitted(self, tmp_path: Path) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_number=None))
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        target = writer.write(fm, body)

        text = target.read_text(encoding="utf-8")
        # Either field is omitted or serialized as null — both acceptable
        if "doc_number:" in text:
            assert "doc_number: null" in text or "doc_number: ~" in text


class TestAmountFormatting:
    """doc_amount renders with Czech-locale thousands separator (NBSP)."""

    def test_integer_amount_drops_trailing_zero(self, frontmatter: DocumentZettelFrontmatter) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_amount=4218.0, doc_currency="CZK"))
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        assert "**Amount:** 4\xa0218 CZK" in body

    def test_two_decimal_amount_kept(self, frontmatter: DocumentZettelFrontmatter) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_amount=1234.56, doc_currency="EUR"))
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        assert "**Amount:** 1\xa0234.56 EUR" in body

    def test_one_decimal_amount_padded_to_two(self, frontmatter: DocumentZettelFrontmatter) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_amount=1234.5, doc_currency="EUR"))
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        assert "**Amount:** 1\xa0234.50 EUR" in body

    def test_small_amount_no_separator(self, frontmatter: DocumentZettelFrontmatter) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_amount=5.0, doc_currency="CZK"))
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        assert "**Amount:** 5 CZK" in body

    def test_large_amount_multiple_separators(self, frontmatter: DocumentZettelFrontmatter) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_amount=1234567.0, doc_currency="CZK"))
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        assert "**Amount:** 1\xa0234\xa0567 CZK" in body

    def test_negative_integer_amount_keeps_minus_sign(self, frontmatter: DocumentZettelFrontmatter) -> None:
        # Credit notes / corrective invoices carry a negative ``doc_amount``;
        # the formatter strips the minus before grouping, then re-prepends it
        # so the NBSP separators land between digits, not between the sign
        # and the leading digit.
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_amount=-4218.0, doc_currency="CZK"))
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        assert "**Amount:** -4\xa0218 CZK" in body

    def test_negative_fractional_amount_keeps_minus_and_decimals(self, frontmatter: DocumentZettelFrontmatter) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_amount=-1234.5, doc_currency="EUR"))
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        assert "**Amount:** -1\xa0234.50 EUR" in body
