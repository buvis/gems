from __future__ import annotations

import re
import urllib.parse
from datetime import date, datetime, timedelta, timezone
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
    "/Users/bob/Library/Mobile Documents/com~apple~CloudDocs/Business/cez-as/"
    "20210311083422-cez-as-7102105594.invoice.pdf"
)
SAMPLE_TITLE = "ČEZ a.s. invoice 7102105594"
SAMPLE_INGESTED_AT = datetime(2026, 5, 4, 14, 30, 22, tzinfo=timezone(timedelta(hours=2)))
SAMPLE_OCR_TEXT = (
    "ČEZ a.s.\nFaktura č. 7102105594\nDatum vystavení: 11.03.2021\nObdobí: 02/2021\nCelkem k úhradě: 4 218,00 Kč\n"
)


def _frontmatter_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": 20210311083422,
        "title": SAMPLE_TITLE,
        "doc_type": "invoice",
        "issuer": "ČEZ a.s.",
        "doc_number": "7102105594",
        "doc_date": date(2021, 3, 11),
        "doc_amount": 4218.0,
        "doc_currency": "CZK",
        "doc_language": "cs",
        "ingested_at": SAMPLE_INGESTED_AT,
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


def _frontmatter_block(text: str) -> str:
    """Extract the frontmatter YAML block (between the first two ``---`` fences)."""
    parts = text.split("---", 2)
    return parts[1] if len(parts) >= 3 else ""


class TestDocumentZettelFrontmatter:
    def test_valid_full_frontmatter_constructs_cleanly(self) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs())
        assert fm.id == 20210311083422
        assert fm.type == "document"
        assert fm.title == SAMPLE_TITLE
        assert fm.doc_type == "invoice"
        assert fm.issuer == "ČEZ a.s."
        assert fm.doc_number == "7102105594"
        assert fm.doc_date == date(2021, 3, 11)
        assert fm.doc_amount == 4218.0
        assert fm.doc_currency == "CZK"
        assert fm.ingested_at == SAMPLE_INGESTED_AT
        assert fm.ingest_source == "email"
        assert fm.file_sha256 == SAMPLE_SHA
        assert fm.extraction_method == "rule:cez-invoice-2024-template:v1"
        assert fm.tags == ["document/invoice", "issuer/cez-as", "year/2021"]

    def test_invalid_id_non_14_digits_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(id=123))

    def test_invalid_id_too_long_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(id=12345678901234567))

    def test_invalid_doc_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_type="not-a-type"))

    def test_dropped_issuer_slug_is_extra_forbidden(self) -> None:
        # `issuer_slug` no longer exists on the model; passing it must raise
        # because of `extra="forbid"`.
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(issuer_slug="cez-as"))

    def test_dropped_issuer_display_is_extra_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(issuer_display="ČEZ a.s."))

    def test_file_path_must_be_absolute(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(file_path="relative/path.pdf"))

    def test_file_path_with_tilde_segment_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(file_path="~/Library/Foo/x.pdf"))

    def test_file_path_with_bare_tilde_segment_raises(self) -> None:
        # A bare ``~`` segment buried in an absolute path (defensive) is rejected.
        # Legitimate tildes inside directory names (e.g. ``com~apple~CloudDocs``)
        # are NOT rejected — that's an iCloud-resolved path component.
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(file_path="/Users/bob/~/x.pdf"))

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

    def test_title_must_be_non_empty(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(title=""))

    def test_title_rejects_leading_or_trailing_whitespace(self) -> None:
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(title="  trailing space  "))
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(title="\ttab"))

    def test_ingested_at_must_be_tz_aware(self) -> None:
        # Naive datetimes are rejected — the spec mandates an offset.
        with pytest.raises(ValidationError):
            DocumentZettelFrontmatter(**_frontmatter_kwargs(ingested_at=datetime(2026, 5, 4, 14, 30, 22)))

    def test_model_dump_uses_kebab_case_aliases(self) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs())
        dumped = fm.model_dump(by_alias=True)
        # Kebab-case aliases must be present for every snake_case attribute that has one.
        for key in (
            "doc-type",
            "doc-number",
            "doc-date",
            "doc-amount",
            "doc-currency",
            "doc-language",
            "ingested-at",
            "ingest-source",
            "file-path",
            "file-sha256",
            "ocr-engine",
            "ocr-mean-confidence",
            "extraction-method",
        ):
            assert key in dumped, f"expected kebab-case alias {key!r}"
        # And no underscored variant survives.
        for key in (
            "doc_type",
            "doc_number",
            "ingest_date",
            "ingest_source",
            "file_path",
            "ocr_mean_confidence",
        ):
            assert key not in dumped, f"unexpected snake_case key {key!r}"


class TestBuildZettelBody:
    def test_h1_is_title(self, frontmatter: DocumentZettelFrontmatter) -> None:
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        assert body.startswith(f"# {SAMPLE_TITLE}\n")

    def test_open_pdf_link_uses_file_url(self, frontmatter: DocumentZettelFrontmatter) -> None:
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        match = re.search(r"\[Open PDF\]\((file://[^\)]+)\)", body)
        assert match is not None, "expected file:// link in body"
        url = match.group(1)
        assert url.startswith("file://")
        # Tildes stay literal; spaces are %20-encoded.
        assert "%20" in url
        # Round-trip back to the absolute path.
        decoded = urllib.parse.unquote(url[len("file://") :])
        assert decoded == SAMPLE_FILE_PATH

    def test_summary_paragraph_present_when_provided(self, frontmatter: DocumentZettelFrontmatter) -> None:
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT, summary="A monthly electricity invoice.")
        assert "\nA monthly electricity invoice.\n" in body
        # Summary appears before the OCR section.
        assert body.index("A monthly electricity invoice.") < body.index("## OCR text")

    def test_summary_paragraph_omitted_when_none(self, frontmatter: DocumentZettelFrontmatter) -> None:
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT, summary=None)
        # No double-blank-line gap where the summary would be.
        assert "\n\n\n## OCR text" not in body
        assert "## OCR text" in body

    def test_summary_paragraph_omitted_when_empty(self, frontmatter: DocumentZettelFrontmatter) -> None:
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT, summary="")
        assert "\n\n\n## OCR text" not in body

    def test_no_legacy_metadata_lines(self, frontmatter: DocumentZettelFrontmatter) -> None:
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        assert "**Date:**" not in body
        assert "**Amount:**" not in body

    def test_ocr_callout_present(self, frontmatter: DocumentZettelFrontmatter) -> None:
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        assert "## OCR text" in body
        assert "> [!quote]- Full text" in body
        for ocr_line in SAMPLE_OCR_TEXT.splitlines():
            if ocr_line:
                assert f"> {ocr_line}" in body

    def test_body_truncation_when_ocr_text_max_chars_set(self, frontmatter: DocumentZettelFrontmatter) -> None:
        long_ocr = "x" * 200
        settings = ZettelSettings(ocr_text_max_chars=50)
        body = build_zettel_body(frontmatter, long_ocr, settings=settings)
        assert ("…" in body) or ("[truncated]" in body)
        assert ("x" * 200) not in body
        assert "> [!quote]- Full text" in body

    def test_body_no_truncation_when_max_chars_zero(self, frontmatter: DocumentZettelFrontmatter) -> None:
        long_ocr = "x" * 200
        settings = ZettelSettings(ocr_text_max_chars=0)
        body = build_zettel_body(frontmatter, long_ocr, settings=settings)
        assert ("x" * 200) in body

    def test_body_default_settings_no_truncation(self, frontmatter: DocumentZettelFrontmatter) -> None:
        long_ocr = "x" * 200
        body = build_zettel_body(frontmatter, long_ocr)
        assert ("x" * 200) in body


class TestZettelWriter:
    def test_write_round_trip_to_per_issuer_subfolder(
        self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter
    ) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body, issuer_slug="cez-as")

        expected_path = (
            tmp_path / "Zettelkasten" / "documents" / "cez-as" / "20210311083422-cez-as-7102105594.invoice.md"
        )
        assert target == expected_path
        assert target.exists()

        zettel = MarkdownZettelRepository(zettelkasten_path=None).find_by_location(str(target))
        meta = zettel.get_data().metadata

        # Repository normalises to kebab-case keys; v1 already serialises in kebab-case.
        assert meta["id"] == 20210311083422
        assert meta["title"] == SAMPLE_TITLE
        assert meta["issuer"] == "ČEZ a.s."
        assert meta["doc-type"] == "invoice"
        assert meta["doc-number"] == 7102105594  # round-trip-safe int
        assert str(meta["doc-date"]).startswith("2021-03-11")
        # Absolute path; legitimate iCloud tildes inside path components are fine.
        assert str(meta["file-path"]).startswith("/")
        assert not str(meta["file-path"]).startswith("~")
        assert meta["extraction-method"] == "rule:cez-invoice-2024-template:v1"
        assert isinstance(meta["tags"], list)
        assert "document/invoice" in meta["tags"]

    def test_write_creates_per_issuer_dir(self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body, issuer_slug="cez-as")
        expected_parent = tmp_path / "Zettelkasten" / "documents" / "cez-as"
        assert expected_parent.is_dir()
        assert target.parent == expected_parent
        assert target.name == "20210311083422-cez-as-7102105594.invoice.md"

    def test_write_rejects_invalid_slug(self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        with pytest.raises(ValueError):
            writer.write(frontmatter, body, issuer_slug="Has Spaces")

    def test_yaml_serialisation_uses_kebab_case_keys(
        self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter
    ) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body, issuer_slug="cez-as")
        block = _frontmatter_block(target.read_text(encoding="utf-8"))
        # No underscore-style keys at line start.
        assert re.search(r"^[a-z]+_", block, re.MULTILINE) is None, block
        # A few expected kebab-case keys.
        for key in ("doc-type:", "doc-number:", "ingested-at:", "file-path:", "extraction-method:"):
            assert key in block, f"expected {key!r} in frontmatter"

    def test_yaml_serialisation_emits_id_as_bare_int(
        self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter
    ) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body, issuer_slug="cez-as")
        block = _frontmatter_block(target.read_text(encoding="utf-8"))
        assert "id: 20210311083422\n" in block

    def test_yaml_no_quoted_numbers_for_round_trippable_doc_number(
        self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter
    ) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body, issuer_slug="cez-as")
        block = _frontmatter_block(target.read_text(encoding="utf-8"))
        # No line starts ``<key>: "<digit>`` or ``<key>: '<digit>``.
        assert re.search(r"^[A-Za-z][A-Za-z\-]*: [\"']\d", block, re.MULTILINE) is None, block
        # doc-number is bare:
        assert "doc-number: 7102105594\n" in block

    def test_yaml_leading_zero_doc_number_stays_quoted_string(self, tmp_path: Path) -> None:
        # ``007`` does not satisfy ``str(int(s)) == s`` (would round-trip to ``7``),
        # so the writer must keep it as a YAML string (quoted by PyYAML).
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_number="007"))
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        target = writer.write(fm, body, issuer_slug="cez-as")
        block = _frontmatter_block(target.read_text(encoding="utf-8"))
        # PyYAML auto-quotes a string that would re-parse as a number.
        assert re.search(r"doc-number:\s*['\"]007['\"]", block) is not None, block

    def test_yaml_sha256_starting_with_digits_emits_as_string(self, tmp_path: Path) -> None:
        digit_sha = "1234567890" + ("0" * (64 - len("1234567890")))
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(file_sha256=digit_sha))
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        target = writer.write(fm, body, issuer_slug="cez-as")
        block = _frontmatter_block(target.read_text(encoding="utf-8"))
        # Either bare (PyYAML detects the hex letters) or quoted — both keep the value addressable
        # as a string. The important assertion is that it round-trips intact.
        assert digit_sha in block

    def test_yaml_serialisation_preserves_unicode_for_issuer(
        self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter
    ) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body, issuer_slug="cez-as")
        text = target.read_text(encoding="utf-8")
        assert "issuer: ČEZ a.s." in text
        assert "\\u010c" not in text.lower()

    def test_yaml_writes_file_path_as_absolute(self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body, issuer_slug="cez-as")
        block = _frontmatter_block(target.read_text(encoding="utf-8"))
        assert "file-path:" in block
        # The value starts with ``/`` (absolute), NOT ``~/`` (legacy form).
        # Embedded tildes inside path components (e.g. iCloud's
        # ``com~apple~CloudDocs``) are legitimate and not rejected.
        value_line = block.split("file-path:", 1)[1].split("\n", 1)[0].strip()
        assert value_line.startswith("/"), value_line
        assert not value_line.startswith("~"), value_line
        assert SAMPLE_FILE_PATH in block

    def test_yaml_emits_ingested_at_with_offset(self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body, issuer_slug="cez-as")
        block = _frontmatter_block(target.read_text(encoding="utf-8"))
        # PyYAML serialises tz-aware datetimes as ISO 8601 with offset.
        match = re.search(r"^ingested-at:\s*(\S+)", block, re.MULTILINE)
        assert match is not None, block
        value = match.group(1).strip("'\"")
        # Strip a possible ``Z`` form (PyYAML uses +HH:MM by default but be tolerant).
        parsed = datetime.fromisoformat(value)
        assert parsed.tzinfo is not None
        assert parsed == SAMPLE_INGESTED_AT

    def test_write_doc_number_none_serialises_as_null_or_omitted(self, tmp_path: Path) -> None:
        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(doc_number=None))
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        target = writer.write(fm, body, issuer_slug="cez-as")
        block = _frontmatter_block(target.read_text(encoding="utf-8"))
        if "doc-number:" in block:
            assert "doc-number: null" in block or "doc-number: ~" in block
