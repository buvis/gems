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
    """Normalize datetime for comparison (strip microseconds, ensure UTC)."""
    if isinstance(val, datetime):
        return val.replace(microsecond=0, tzinfo=timezone.utc)
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
        # Skip date/id: Python has a bug in _get_date_from_file (uses len(fmt_string) instead of digit count).
        # Rust parses correctly; Python gives 10:03:00 instead of 10:30:00.
        _compare_metadata(py_data.metadata, rust_data.metadata, skip_keys={"date", "id"})
        _compare_sections(py_data.sections, rust_data.sections)

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
        # Tags should be deduplicated and sorted
        assert rust_data.metadata["tags"] == ["alpha", "beta", "zebra"]

    def test_multiple_sections(self):
        py_data, rust_data = self._parse_both("multiple_sections.md")
        _compare_metadata(py_data.metadata, rust_data.metadata)
        _compare_sections(py_data.sections, rust_data.sections)


class TestLoadAllParity:
    """Test that load_all produces same results as parsing files individually."""

    def test_load_all_matches_individual_parse(self):
        rust_bulk = load_all(str(FIXTURES_DIR))
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
