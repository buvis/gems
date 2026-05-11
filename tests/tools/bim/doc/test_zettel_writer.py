from __future__ import annotations

import re
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from bim.commands.doc.shared.settings_models import ZettelSettings
from bim.commands.doc.shared.zettel_helpers import compose_zettel_title
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
SAMPLE_ISSUER = "ČEZ a.s."
SAMPLE_DOC_TYPE = "invoice"
SAMPLE_DOC_NUMBER = "7102105594"
# Used by the ``num0_*`` variants in ``TestZettelWriterPerVariantFixtures`` so
# the snapshot suite genuinely exercises the ``doc_title`` fallback branch of
# ``compose_zettel_title`` (PRD 00035 success metric #7). Mirrors the constant
# used in ``dev/bin/gen_zettel_writer_fixtures.py``.
SAMPLE_DOC_TITLE = "Annual Statement 2021"
SAMPLE_TITLE = compose_zettel_title(
    issuer=SAMPLE_ISSUER, doc_type=SAMPLE_DOC_TYPE, doc_number=SAMPLE_DOC_NUMBER, doc_title=None
)
SAMPLE_INGESTED_AT = datetime(2026, 5, 4, 14, 30, 22, tzinfo=timezone(timedelta(hours=2)))
SAMPLE_OCR_TEXT = (
    "ČEZ a.s.\nFaktura č. 7102105594\nDatum vystavení: 11.03.2021\nObdobí: 02/2021\nCelkem k úhradě: 4 218,00 Kč\n"
)


def _frontmatter_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": 20210311083422,
        "title": SAMPLE_TITLE,
        "doc_type": SAMPLE_DOC_TYPE,
        "issuer": SAMPLE_ISSUER,
        "doc_number": SAMPLE_DOC_NUMBER,
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
        # are NOT rejected; that's an iCloud-resolved path component.
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
        # Naive datetimes are rejected; the spec mandates an offset.
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

    def test_summary_paragraph_present_when_provided(self, frontmatter: DocumentZettelFrontmatter) -> None:
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT, summary="A monthly electricity invoice.")
        # Exactly one blank line between H1 and the summary; no link line between them.
        assert body.startswith(f"# {SAMPLE_TITLE}\n\nA monthly electricity invoice.\n\n"), body[:200]
        # Summary appears before the OCR section.
        assert body.index("A monthly electricity invoice.") < body.index("## OCR text")

    def test_summary_paragraph_omitted_when_none(self, frontmatter: DocumentZettelFrontmatter) -> None:
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT, summary=None)
        # Exactly one blank line between H1 and ``## OCR text``; no link line between them.
        assert body.startswith(f"# {SAMPLE_TITLE}\n\n## OCR text\n"), body[:200]
        # No double-blank-line gap where the summary would be.
        assert "\n\n\n## OCR text" not in body

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
        # file-path is now a double-quoted Markdown link wrapping an absolute URL.
        # The URL inside, decoded, points at an absolute filesystem path with no
        # legacy ``~/`` prefix. Legitimate iCloud tildes inside path components
        # (``com~apple~CloudDocs``) are fine.
        link = str(meta["file-path"])
        match = re.match(r"^\[Open file\]\(file://(.+)\)$", link)
        assert match is not None, link
        decoded = urllib.parse.unquote(match.group(1))
        assert decoded.startswith("/"), decoded
        assert not decoded.startswith("~"), decoded
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

    def test_yaml_top_level_key_order_matches_spec_section_5(
        self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter
    ) -> None:
        """Field order must match dev/local/specs/bim-doc-architecture.md §5 exactly."""
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body, issuer_slug="cez-as")
        block = _frontmatter_block(target.read_text(encoding="utf-8"))
        # Top-level keys: lines that begin with a kebab-case key followed by ":".
        # Indented lines (list items, nested) are skipped.
        top_level_keys = [m.group(1) for m in re.finditer(r"^([a-z][a-z0-9\-]*):", block, re.MULTILINE)]
        assert top_level_keys == [
            "id",
            "title",
            "type",
            "doc-type",
            "issuer",
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
            "tags",
        ], top_level_keys

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
        # Either bare (PyYAML detects the hex letters) or quoted; both keep the value addressable
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

    def test_file_path_yaml_value_is_open_file_link(
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
        block = _frontmatter_block(text)

        # Raw scalar: file-path emitted as a double-quoted Markdown link.
        assert '\nfile-path: "[Open file](file://' in block, block

        # Parsed scalar: yaml-loaded value matches the link shape.
        parsed = yaml.safe_load(block)
        assert isinstance(parsed, dict)
        link = parsed["file-path"]
        match = re.match(r"^\[Open file\]\(file://(.+)\)$", link)
        assert match is not None, link

        # Round-trip: URL inside link decodes back to SAMPLE_FILE_PATH.
        assert urllib.parse.unquote(match.group(1)) == SAMPLE_FILE_PATH

        # Body carries no source-file link line.
        body_section = text.split("---\n", 2)[2]
        assert "[Open PDF]" not in body_section
        assert "[Open file]" not in body_section

    def test_yaml_writes_file_path_as_absolute(self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body, issuer_slug="cez-as")
        block = _frontmatter_block(target.read_text(encoding="utf-8"))
        # Raw scalar must be a double-quoted Markdown link with ``Open file`` text.
        match = re.search(r'^file-path: "\[Open file\]\(file://([^)]+)\)"$', block, re.MULTILINE)
        assert match is not None, block
        # URL inside the link round-trips to the absolute path the writer received.
        decoded = urllib.parse.unquote(match.group(1))
        assert decoded == SAMPLE_FILE_PATH
        # Decoded path is absolute; legitimate tildes inside path components are fine,
        # but the value does not start with a bare ``~/``.
        assert decoded.startswith("/"), decoded
        assert not decoded.startswith("~"), decoded

    def test_yaml_emits_ingested_at_with_offset(self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter) -> None:
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
        target = writer.write(frontmatter, body, issuer_slug="cez-as")
        block = _frontmatter_block(target.read_text(encoding="utf-8"))
        # PyYAML serialises tz-aware datetimes as ISO 8601 with offset using a
        # space separator (``2026-05-04 14:30:22+02:00``). Python 3.11+
        # ``datetime.fromisoformat`` parses both space- and T-separated forms.
        match = re.search(r"^ingested-at:\s*(.+)$", block, re.MULTILINE)
        assert match is not None, block
        value = match.group(1).strip().strip("'\"")
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


_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "zettel_writer"


def _fixture_name(has_number: bool, has_amount: bool, has_language: bool) -> str:
    """Mirror of ``dev/bin/gen_zettel_writer_fixtures.py:_fixture_name``.

    Naming scheme: ``num{0|1}_amt{0|1}_lang{0|1}.md``. Each flag indicates
    whether the corresponding optional field is *present* in that variant.
    """
    return f"num{int(has_number)}_amt{int(has_amount)}_lang{int(has_language)}.md"


class TestZettelWriterPerVariantFixtures:
    """Byte-for-byte snapshot coverage for every combination of optional doc fields.

    PRD success criterion 1 requires the writer to produce v1 YAML for every
    doc-type variant (with/without ``doc_number``, ``doc_amount``, ``doc_language``).
    The 8 = 2^3 combinations are pinned against stored fixture files under
    ``tests/tools/bim/doc/fixtures/zettel_writer/``; criteria 2 and 3 (no
    quoted numbers, no underscore keys) re-asserted per variant on top of the
    byte-for-byte check.

    Regenerate fixtures (after intentional writer changes) with::

        uv run python dev/bin/gen_zettel_writer_fixtures.py
    """

    _EXPECTED_KEY_ORDER = [
        "id",
        "title",
        "type",
        "doc-type",
        "issuer",
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
        "tags",
    ]

    @pytest.mark.parametrize("has_doc_number", [True, False])
    @pytest.mark.parametrize("has_doc_amount", [True, False])
    @pytest.mark.parametrize("has_doc_language", [True, False])
    def test_variant_serialisation_v1_invariants(
        self,
        tmp_path: Path,
        has_doc_number: bool,
        has_doc_amount: bool,
        has_doc_language: bool,
    ) -> None:
        overrides: dict[str, object] = {}
        if not has_doc_number:
            overrides["doc_number"] = None
            # Title comes from the ``doc_title`` fallback branch, which
            # mirrors what ``compose_zettel_title`` would produce in production
            # when extraction yields a title but no number. PRD 00035 metric #7.
            overrides["title"] = compose_zettel_title(
                issuer=SAMPLE_ISSUER,
                doc_type=SAMPLE_DOC_TYPE,
                doc_number=None,
                doc_title=SAMPLE_DOC_TITLE,
            )
        if not has_doc_amount:
            overrides["doc_amount"] = None
            overrides["doc_currency"] = None  # currency without amount makes no sense
        if not has_doc_language:
            overrides["doc_language"] = None

        fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(**overrides))
        writer = ZettelWriter(
            repo=None,
            vault_root=tmp_path,
            vault_documents_subdir="Zettelkasten/documents",
        )
        body = build_zettel_body(fm, SAMPLE_OCR_TEXT)
        target = writer.write(fm, body, issuer_slug="cez-as")
        actual = target.read_text(encoding="utf-8")
        block = _frontmatter_block(actual)

        # Criterion 1 (primary): byte-for-byte equality against the stored
        # snapshot fixture for this variant. Catches accidental whitespace,
        # list-item reordering, or quoting drift that property assertions miss.
        fixture_path = _FIXTURES_DIR / _fixture_name(has_doc_number, has_doc_amount, has_doc_language)
        expected = fixture_path.read_text(encoding="utf-8")
        assert actual == expected, (
            f"writer output drift vs {fixture_path.relative_to(Path(__file__).parent)}\n"
            f"--- expected\n{expected}\n--- actual\n{actual}\n"
            f"(regenerate with: uv run python dev/bin/gen_zettel_writer_fixtures.py)"
        )

        # The remaining assertions are intentionally redundant with the
        # byte-for-byte check above. They produce a clearer failure message
        # naming which invariant broke (key order, quoted numbers,
        # underscore keys, ingested-at parse, variant shape) and survive a
        # well-meaning fixture regeneration that bakes in a regression. Keep
        # them as defence-in-depth.

        # Criterion 1 (invariant): all 18 spec §5 keys present (None values
        # serialise as ``null``/``~`` but the key is still emitted).
        top_level_keys = [m.group(1) for m in re.finditer(r"^([a-z][a-z0-9\-]*):", block, re.MULTILINE)]
        assert top_level_keys == self._EXPECTED_KEY_ORDER, top_level_keys

        # Criterion 2: no line of the form ``<key>: "<digit>`` or ``<key>: '<digit>``.
        assert re.search(r"^[A-Za-z][A-Za-z0-9\-]*: [\"']\d", block, re.MULTILINE) is None, block

        # Criterion 3: no underscore-style frontmatter key.
        assert re.search(r"^[a-z]+_", block, re.MULTILINE) is None, block

        # Criterion 5 (proxy): ingested-at parses with fromisoformat and is tz-aware.
        match = re.search(r"^ingested-at:\s*(.+)$", block, re.MULTILINE)
        assert match is not None, block
        parsed = datetime.fromisoformat(match.group(1).strip().strip("'\""))
        assert parsed.tzinfo is not None, parsed

        # Variant-specific shape:
        # - doc-number bare int when present, ``null`` when absent
        if has_doc_number:
            assert "doc-number: 7102105594\n" in block
        else:
            assert "doc-number: null" in block or "doc-number: ~" in block
        # - doc-amount numeric when present, ``null`` when absent
        if has_doc_amount:
            assert re.search(r"^doc-amount:\s*4218(\.0)?\s*$", block, re.MULTILINE) is not None, block
        else:
            assert "doc-amount: null" in block or "doc-amount: ~" in block
        # - doc-language ``cs`` when present, ``null`` when absent
        if has_doc_language:
            assert "doc-language: cs\n" in block
        else:
            assert "doc-language: null" in block or "doc-language: ~" in block
