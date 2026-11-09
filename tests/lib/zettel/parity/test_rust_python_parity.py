"""Parity tests: parse fixtures with both Python and Rust, compare results."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.services.zettel_factory import ZettelFactory
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser import (
    ZettelFileParser,
)

try:
    from buvis.pybase.zettel._core import load_all, parse_file

    HAS_RUST = True
except ImportError:
    HAS_RUST = False

FIXTURES_DIR = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.skipif(not HAS_RUST, reason="Rust _core not available")


def _rust_dict_to_zettel_data(raw: dict[str, Any]) -> ZettelData:
    data = ZettelData()
    data.metadata = dict(raw.get("metadata", {}))
    data.reference = dict(raw.get("reference", {}))
    data.sections = [(h, c) for h, c in raw.get("sections", [])]
    data.file_path = raw.get("file_path") or None
    return data


def _normalize_datetime(val: Any) -> Any:
    """Normalize datetime for comparison: the same instant in UTC, without microseconds.

    The Rust bridge hands aware dates to Python converted to UTC and reads naive
    dates as UTC, so an aware Python value is converted and a naive one is labelled.
    """
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(microsecond=0, tzinfo=timezone.utc)
        return val.astimezone(timezone.utc).replace(microsecond=0)
    return val


def _compare_metadata(py_meta: dict, rust_meta: dict, skip_keys: set[str] | None = None) -> None:
    """Compare metadata dicts from Python and Rust parsers."""
    skip = skip_keys or set()
    all_keys = set(py_meta.keys()) | set(rust_meta.keys()) - skip

    for key in all_keys:
        if key in skip:
            continue
        py_val = _normalize_datetime(py_meta.get(key))
        rust_val = _normalize_datetime(rust_meta.get(key))
        assert py_val == rust_val, f"metadata[{key!r}]: Python={py_val!r} vs Rust={rust_val!r}"


def _compare_sections(py_sections: list, rust_sections: list) -> None:
    """Compare sections from Python and Rust parsers."""
    assert len(py_sections) == len(rust_sections), (
        f"section count: Python={len(py_sections)} vs Rust={len(rust_sections)}"
    )
    for i, (py_sec, rust_sec) in enumerate(zip(py_sections, rust_sections)):
        assert py_sec[0] == rust_sec[0], f"section[{i}] heading: Python={py_sec[0]!r} vs Rust={rust_sec[0]!r}"
        assert py_sec[1].strip() == rust_sec[1].strip(), (
            f"section[{i}] content: Python={py_sec[1]!r} vs Rust={rust_sec[1]!r}"
        )


class TestParseFileParity:
    """Compare parse_file output between Python and Rust for each fixture."""

    def _parse_both(self, fixture_name: str) -> tuple[ZettelData, ZettelData]:
        path = FIXTURES_DIR / fixture_name
        py_data = ZettelFileParser.from_file(path)
        # Apply full Python pipeline (same as repo load path)
        py_zettel = Zettel(py_data)
        py_zettel.ensure_consistency()
        py_zettel.migrate()
        py_zettel.ensure_consistency()
        py_data = py_zettel.get_data()

        rust_raw = parse_file(str(path))
        rust_data = _rust_dict_to_zettel_data(rust_raw)

        return py_data, rust_data

    def test_simple_note(self):
        py_data, rust_data = self._parse_both("simple_note.md")
        _compare_metadata(py_data.metadata, rust_data.metadata)
        _compare_sections(py_data.sections, rust_data.sections)
        assert py_data.reference == rust_data.reference

    def test_note_with_backmatter(self):
        py_data, rust_data = self._parse_both("note_with_backmatter.md")
        _compare_metadata(py_data.metadata, rust_data.metadata)
        _compare_sections(py_data.sections, rust_data.sections)
        assert py_data.reference == rust_data.reference

    def test_date_title_from_filename(self):
        py_data, rust_data = self._parse_both("202401151030 Note from filename.md")
        _compare_metadata(py_data.metadata, rust_data.metadata)
        _compare_sections(py_data.sections, rust_data.sections)
        # Both read the filename digits as local time and derive the id from them.
        assert py_data.metadata["id"] == rust_data.metadata["id"] == 202401151030_00

    def test_default_id_follows_the_dates_own_offset_in_both_paths(self, tmp_path: Path):
        note = tmp_path / "offset-note.md"
        note.write_text("---\ntitle: Offset\ndate: 2024-09-13T12:00:00+02:00\n---\n\n# Offset\n", encoding="utf-8")

        py_zettel = Zettel(ZettelFileParser.from_file(note))
        py_zettel.ensure_consistency()
        rust_data = _rust_dict_to_zettel_data(parse_file(str(note)))

        assert py_zettel.get_data().metadata["id"] == 20240913120000
        assert rust_data.metadata["id"] == 20240913120000

    def test_migration(self):
        py_data, rust_data = self._parse_both("needs_migration.md")
        # After migration: zkn-id → id, tag → tags, type zettel → note
        _compare_metadata(py_data.metadata, rust_data.metadata)
        assert "id" in rust_data.metadata
        assert rust_data.metadata.get("type") == "note"
        assert isinstance(rust_data.metadata.get("tags"), list)

    def test_duplicate_tags(self):
        py_data, rust_data = self._parse_both("duplicate_tags.md")
        _compare_metadata(py_data.metadata, rust_data.metadata)
        # Tags are deduplicated and keep their written order, like the vault's notes
        assert rust_data.metadata["tags"] == ["zebra", "alpha", "beta"]

    def test_multiple_sections(self):
        py_data, rust_data = self._parse_both("multiple_sections.md")
        _compare_metadata(py_data.metadata, rust_data.metadata)
        _compare_sections(py_data.sections, rust_data.sections)


class TestReferenceOrderParity:
    """Verify Rust parser preserves reference key insertion order (IndexMap)."""

    def test_rust_preserves_reference_key_order(self):
        path = FIXTURES_DIR / "many_references.md"
        rust_raw = parse_file(str(path))
        rust_data = _rust_dict_to_zettel_data(rust_raw)

        expected_keys = [
            "zebra",
            "alpha",
            "middle",
            "beta",
            "source",
            "link",
            "parent",
            "category",
            "priority",
            "status",
        ]
        assert list(rust_data.reference.keys()) == expected_keys

    def test_rust_reference_order_matches_python(self):
        path = FIXTURES_DIR / "many_references.md"
        py_data = ZettelFileParser.from_file(path)
        rust_raw = parse_file(str(path))
        rust_data = _rust_dict_to_zettel_data(rust_raw)

        assert list(py_data.reference.keys()) == list(rust_data.reference.keys())

    def test_format_round_trip_preserves_reference_order(self):
        from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import (
            MarkdownZettelFormatter,
        )

        path = FIXTURES_DIR / "many_references.md"
        rust_raw = parse_file(str(path))
        rust_data = _rust_dict_to_zettel_data(rust_raw)

        formatted = MarkdownZettelFormatter.format(rust_data)

        # Re-parse the formatted output
        from buvis.pybase.zettel.infrastructure.persistence.file_parsers.parsers.markdown.markdown import (
            MarkdownZettelFileParser,
        )

        reparsed = MarkdownZettelFileParser.parse(formatted)
        assert list(reparsed.reference.keys()) == list(rust_data.reference.keys())


class TestLoadAllParity:
    """Test that load_all produces same results as parsing files individually."""

    def test_load_all_matches_individual_parse(self):
        rust_bulk, _errors = load_all(str(FIXTURES_DIR))
        fixture_files = sorted(FIXTURES_DIR.glob("*.md"))

        assert len(rust_bulk) == len(fixture_files)

        bulk_by_path = {}
        for raw in rust_bulk:
            fp = raw.get("file_path", "")
            bulk_by_path[fp] = _rust_dict_to_zettel_data(raw)

        for f in fixture_files:
            single_raw = parse_file(str(f))
            single_data = _rust_dict_to_zettel_data(single_raw)
            bulk_data = bulk_by_path[str(f)]

            _compare_metadata(single_data.metadata, bulk_data.metadata)
            _compare_sections(single_data.sections, bulk_data.sections)
            assert single_data.reference == bulk_data.reference


class TestZettelFactoryFromRust:
    """Test that ZettelFactory correctly handles from_rust flag."""

    def test_factory_preserves_from_rust(self):
        rust_raw = parse_file(str(FIXTURES_DIR / "simple_note.md"))
        rust_data = _rust_dict_to_zettel_data(rust_raw)
        zettel = Zettel(rust_data, from_rust=True)
        result = ZettelFactory.create(zettel)
        assert result.title == "Simple test note"
        assert result.id == 42
