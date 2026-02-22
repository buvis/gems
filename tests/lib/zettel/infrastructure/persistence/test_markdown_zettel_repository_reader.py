from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
    MarkdownZettelRepository,
    _rust_dict_to_zettel_data,
)

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
