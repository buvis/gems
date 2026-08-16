from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
    MarkdownZettelRepository,
    _rust_dict_to_zettel_data,
)

HAS_RUST = importlib.util.find_spec("buvis.pybase.zettel._core") is not None

MINIMAL_ZETTEL = """\
---
title: Test
type: note
---

## Content

Body text.
"""


class TestRustDictToZettelData:
    def test_converts_full_dict(self) -> None:
        raw = {
            "metadata": {"title": "Test", "id": "123"},
            "reference": {"parent": "[[456]]"},
            "sections": [("Content", "Body text.")],
            "file_path": "/tmp/test.md",
        }
        data = _rust_dict_to_zettel_data(raw)

        assert data.metadata["title"] == "Test"
        assert data.reference["parent"] == "[[456]]"
        assert data.sections == [("Content", "Body text.")]
        assert data.file_path == "/tmp/test.md"

    def test_converts_empty_dict(self) -> None:
        data = _rust_dict_to_zettel_data({})

        assert data.metadata == {}
        assert data.reference == {}
        assert data.sections == []
        assert data.file_path is None

    def test_converts_empty_file_path(self) -> None:
        data = _rust_dict_to_zettel_data({"file_path": ""})
        assert data.file_path is None


class TestFindByLocationPythonFallback:
    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
        False,
    )
    def test_find_by_location_python(self, tmp_path: Path) -> None:
        md_file = tmp_path / "note.md"
        md_file.write_text(MINIMAL_ZETTEL, encoding="utf-8")

        repo = MarkdownZettelRepository()
        zettel = repo.find_by_location(str(md_file))

        assert zettel is not None


class TestFindAllPythonFallback:
    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
        False,
    )
    def test_find_all_python(self, tmp_path: Path) -> None:
        md_file = tmp_path / "note.md"
        md_file.write_text(MINIMAL_ZETTEL, encoding="utf-8")

        repo = MarkdownZettelRepository()
        zettels = repo.find_all(str(tmp_path))

        assert len(zettels) == 1

    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
        False,
    )
    def test_find_all_python_with_filter(self, tmp_path: Path) -> None:
        match = tmp_path / "match.md"
        match.write_text(
            "---\ntitle: Match\ntype: note\n---\n\n## Content\n\nBody.\n",
            encoding="utf-8",
        )
        nomatch = tmp_path / "nomatch.md"
        nomatch.write_text(
            "---\ntitle: NoMatch\ntype: project\n---\n\n## Content\n\nBody.\n",
            encoding="utf-8",
        )

        repo = MarkdownZettelRepository()
        zettels = repo.find_all(str(tmp_path), metadata_eq={"type": "note"})

        titles = [z.get_data().metadata.get("title") for z in zettels]
        assert "Match" in titles
        assert "NoMatch" not in titles

    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
        False,
    )
    def test_find_all_empty_dir(self, tmp_path: Path) -> None:
        repo = MarkdownZettelRepository()
        zettels = repo.find_all(str(tmp_path))
        assert zettels == []

    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
        False,
    )
    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository.console",
    )
    def test_find_all_skips_malformed_yaml_frontmatter_and_warns_once(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        good = tmp_path / "good.md"
        good.write_text(MINIMAL_ZETTEL, encoding="utf-8")
        bad = tmp_path / "bad.md"
        bad.write_text(
            "---\ntitle: [unclosed\ntype: note\n---\n\n## Content\n\nBody.\n",
            encoding="utf-8",
        )

        repo = MarkdownZettelRepository()
        zettels = repo.find_all(str(tmp_path))

        assert len(zettels) == 1
        assert zettels[0].get_data().metadata.get("title") == "Test"
        mock_console.warning.assert_called_once()
        assert "bad.md" in mock_console.warning.call_args[0][0]


# Invalid UTF-8 bytes: a failure genuinely isolated by both the Rust and
# Python-fallback backends (unlike malformed YAML frontmatter, which Rust
# silently accepts as empty metadata).
INVALID_UTF8_NOTE_BYTES = b"\xff\xfe---\ntitle: Bad\n---\n\n## Content\n\nBody.\n"


def _write_mixed_notes(tmp_path: Path) -> None:
    good = tmp_path / "good.md"
    good.write_text(MINIMAL_ZETTEL, encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_bytes(INVALID_UTF8_NOTE_BYTES)


class TestFindAllPythonFallbackParseErrors:
    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
        False,
    )
    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository.console",
    )
    def test_find_all_skips_invalid_utf8_note_and_warns_once(self, mock_console: MagicMock, tmp_path: Path) -> None:
        _write_mixed_notes(tmp_path)

        repo = MarkdownZettelRepository()
        zettels = repo.find_all(str(tmp_path))

        assert len(zettels) == 1
        assert zettels[0].get_data().metadata.get("title") == "Test"
        mock_console.warning.assert_called_once()
        assert "bad.md" in mock_console.warning.call_args[0][0]


class TestFindAllRustBackendParseErrors:
    @pytest.mark.skipif(not HAS_RUST, reason="Rust _core not available")
    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository.console",
    )
    def test_find_all_skips_invalid_utf8_note_and_warns_once(self, mock_console: MagicMock, tmp_path: Path) -> None:
        _write_mixed_notes(tmp_path)

        repo = MarkdownZettelRepository()
        zettels = repo.find_all(str(tmp_path))

        assert len(zettels) == 1
        assert zettels[0].get_data().metadata.get("title") == "Test"
        mock_console.warning.assert_called_once()
        assert "bad.md" in mock_console.warning.call_args[0][0]
