"""One-shot generator for ZettelWriter byte-for-byte fixtures.

Produces 8 expected zettel outputs under
``tests/tools/bim/doc/fixtures/zettel_writer/``, one per combination of
optional ``doc_number`` / ``doc_amount`` / ``doc_language`` presence.

Run from project root: ``uv run python dev/bin/gen_zettel_writer_fixtures.py``

The fixture inputs mirror the constants used in
``tests/tools/bim/doc/test_zettel_writer.py`` so the regenerated values are
byte-identical to what the test will produce when calling the writer.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from bim.commands.doc.shared.zettel_helpers import compose_zettel_title
from bim.commands.doc.shared.zettel_writer import (
    DocumentZettelFrontmatter,
    ZettelWriter,
    build_zettel_body,
)

SAMPLE_SHA = "3f4a8c2b91e7d5" + ("0" * (64 - len("3f4a8c2b91e7d5")))
SAMPLE_FILE_PATH = (
    "/Users/bob/Library/Mobile Documents/com~apple~CloudDocs/Business/cez-as/"
    "20210311083422-cez-as-7102105594.invoice.pdf"
)
SAMPLE_ISSUER = "ČEZ a.s."
SAMPLE_DOC_TYPE = "invoice"
SAMPLE_DOC_NUMBER = "7102105594"
# Used for the ``num0_*`` variants where ``doc_number`` is absent — exercises
# the ``doc_title`` fallback branch of ``compose_zettel_title`` so PRD 00035
# success metric #7 is genuinely covered by the snapshot suite (not only by
# the unit test in ``test_zettel_helpers.py``).
SAMPLE_DOC_TITLE = "Annual Statement 2021"
SAMPLE_INGESTED_AT = datetime(2026, 5, 4, 14, 30, 22, tzinfo=timezone(timedelta(hours=2)))
SAMPLE_OCR_TEXT = (
    "ČEZ a.s.\nFaktura č. 7102105594\nDatum vystavení: 11.03.2021\nObdobí: 02/2021\nCelkem k úhradě: 4 218,00 Kč\n"
)


def _frontmatter_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": 20210311083422,
        "title": compose_zettel_title(
            issuer=SAMPLE_ISSUER, doc_type=SAMPLE_DOC_TYPE, doc_number=SAMPLE_DOC_NUMBER, doc_title=None
        ),
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


def _fixture_name(has_number: bool, has_amount: bool, has_language: bool) -> str:
    return f"num{int(has_number)}_amt{int(has_amount)}_lang{int(has_language)}.md"


def _write_one_fixture(out_dir: Path, has_number: bool, has_amount: bool, has_language: bool) -> Path:
    overrides: dict[str, object] = {}
    if not has_number:
        overrides["doc_number"] = None
        # Title now comes from the ``doc_title`` fallback branch — exercises
        # PRD 00035 success metric #7 in the snapshot suite.
        overrides["title"] = compose_zettel_title(
            issuer=SAMPLE_ISSUER,
            doc_type=SAMPLE_DOC_TYPE,
            doc_number=None,
            doc_title=SAMPLE_DOC_TITLE,
        )
    if not has_amount:
        overrides["doc_amount"] = None
        overrides["doc_currency"] = None
    if not has_language:
        overrides["doc_language"] = None

    fm = DocumentZettelFrontmatter(**_frontmatter_kwargs(**overrides))
    body = build_zettel_body(fm, SAMPLE_OCR_TEXT)

    with TemporaryDirectory() as tmp_root:
        writer = ZettelWriter(
            repo=None,
            vault_root=Path(tmp_root),
            vault_documents_subdir="Zettelkasten/documents",
        )
        target = writer.write(fm, body, issuer_slug="cez-as")
        text = target.read_text(encoding="utf-8")

    fixture_path = out_dir / _fixture_name(has_number, has_amount, has_language)
    fixture_path.write_text(text, encoding="utf-8")
    return fixture_path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    out_dir = repo_root / "tests" / "tools" / "bim" / "doc" / "fixtures" / "zettel_writer"
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for has_number in (True, False):
        for has_amount in (True, False):
            for has_language in (True, False):
                path = _write_one_fixture(out_dir, has_number, has_amount, has_language)
                written.append(path)

    print(f"Wrote {len(written)} fixtures to {out_dir.relative_to(repo_root)}:")
    for p in sorted(written):
        print(f"  - {p.name}")


if __name__ == "__main__":
    main()
