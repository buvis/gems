from __future__ import annotations

import importlib
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.adapters.console.console import console
from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
    MarkdownZettelRepository,
    _rust_dict_to_zettel_data,
)

try:
    importlib.import_module("buvis.pybase.zettel._core")
    HAS_RUST = True
except ImportError:
    HAS_RUST = False

MINIMAL_ZETTEL = """\
---
title: Test
type: note
---

## Content

Body text.
"""

# Invalid UTF-8 bytes: used for the cross-backend fixture below because it is
# a failure genuinely isolated by both the Rust and Python-fallback backends.
# Malformed YAML frontmatter would not work here: the Rust backend silently
# accepting it (parsing to empty metadata instead of erroring) is a
# recorded, deliberately deferred gap for this PRD -- not an endorsed
# permanent divergence -- tracked in
# dev/local/reviews/00050-zettel-scanner-error-surfacing-v1-ledger.json.
INVALID_UTF8_NOTE_BYTES = b"\xff\xfe---\ntitle: Bad\n---\n\n## Content\n\nBody.\n"


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
        "buvis.pybase.adapters.console.console.console",
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


def _write_mixed_notes(tmp_path: Path) -> None:
    good = tmp_path / "good.md"
    good.write_text(MINIMAL_ZETTEL, encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_bytes(INVALID_UTF8_NOTE_BYTES)


class TestFindAllBackendParseErrors:
    """An unparseable note must be isolated the same way regardless of
    backend: skip it, keep the good note, warn exactly once naming it.
    """

    @pytest.mark.parametrize(
        "use_rust",
        [
            pytest.param(False, id="python-fallback"),
            pytest.param(
                True,
                id="rust-backend",
                marks=pytest.mark.skipif(not HAS_RUST, reason="Rust _core not available"),
            ),
        ],
    )
    @patch(
        "buvis.pybase.adapters.console.console.console",
    )
    def test_find_all_skips_invalid_utf8_note_and_warns_once(
        self, mock_console: MagicMock, use_rust: bool, tmp_path: Path
    ) -> None:
        _write_mixed_notes(tmp_path)

        force_python_fallback = (
            nullcontext()
            if use_rust
            else patch(
                "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
                False,
            )
        )
        with force_python_fallback:
            repo = MarkdownZettelRepository()
            zettels = repo.find_all(str(tmp_path))

        assert len(zettels) == 1
        assert zettels[0].get_data().metadata.get("title") == "Test"
        mock_console.warning.assert_called_once()
        assert "bad.md" in mock_console.warning.call_args[0][0]


class TestFindAllFilteredBackendParseErrors:
    """The `metadata_eq` filtered branch (`load_filtered` for Rust, the
    filtered rglob loop for Python) must isolate an unparseable note the same
    way regardless of backend: skip it, keep the matching note, warn exactly
    once naming it.
    """

    @pytest.mark.parametrize(
        "use_rust",
        [
            pytest.param(False, id="python-fallback"),
            pytest.param(
                True,
                id="rust-backend",
                marks=pytest.mark.skipif(not HAS_RUST, reason="Rust _core not available"),
            ),
        ],
    )
    @patch(
        "buvis.pybase.adapters.console.console.console",
    )
    def test_find_all_filtered_surfaces_parse_error_and_keeps_matching_note(
        self,
        mock_console: MagicMock,
        use_rust: bool,
        tmp_path: Path,
        tmp_path_factory: pytest.TempPathFactory,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        match = tmp_path / "match.md"
        match.write_text(
            "---\ntitle: Match\ntype: note\n---\n\n## Content\n\nBody.\n",
            encoding="utf-8",
        )
        bad = tmp_path / "bad.md"
        bad.write_bytes(INVALID_UTF8_NOTE_BYTES)

        if use_rust:
            # The Rust `load_filtered` branch resolves a cache path from
            # XDG_CACHE_HOME (falling back to ~/.cache). Redirect it to a
            # separate per-test tmp dir so this test starts from a cold,
            # isolated cache and never reads/writes the developer's real
            # ~/.cache/buvis - a warmed cache would change what the scan
            # reports and make this test flaky/non-hermetic.
            cache_home = tmp_path_factory.mktemp("xdg_cache_home")
            monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))

        force_python_fallback = (
            nullcontext()
            if use_rust
            else patch(
                "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
                False,
            )
        )
        with force_python_fallback:
            repo = MarkdownZettelRepository()
            zettels = repo.find_all(str(tmp_path), metadata_eq={"type": "note"})

        titles = [z.get_data().metadata.get("title") for z in zettels]
        assert "Match" in titles
        mock_console.warning.assert_called_once()
        assert "bad.md" in mock_console.warning.call_args[0][0]


class TestFindAllWarningAggregation:
    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
        False,
    )
    @patch(
        "buvis.pybase.adapters.console.console.console",
    )
    def test_find_all_warns_once_naming_every_bad_note_when_two_notes_fail(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        good = tmp_path / "good.md"
        good.write_text(MINIMAL_ZETTEL, encoding="utf-8")
        bad_one = tmp_path / "bad_one.md"
        bad_one.write_bytes(INVALID_UTF8_NOTE_BYTES)
        bad_two = tmp_path / "bad_two.md"
        bad_two.write_text(
            "---\ntitle: [unclosed\ntype: note\n---\n\n## Content\n\nBody.\n",
            encoding="utf-8",
        )

        repo = MarkdownZettelRepository()
        zettels = repo.find_all(str(tmp_path))

        assert len(zettels) == 1
        mock_console.warning.assert_called_once()
        message = mock_console.warning.call_args[0][0]
        assert "bad_one.md" in message
        assert "bad_two.md" in message

    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
        False,
    )
    @patch(
        "buvis.pybase.adapters.console.console.console",
    )
    def test_find_all_does_not_warn_when_every_note_parses(self, mock_console: MagicMock, tmp_path: Path) -> None:
        good = tmp_path / "good.md"
        good.write_text(MINIMAL_ZETTEL, encoding="utf-8")

        repo = MarkdownZettelRepository()
        zettels = repo.find_all(str(tmp_path))

        assert len(zettels) == 1
        mock_console.warning.assert_not_called()


# A well-formed note (valid mapping front matter) used as the base for the
# back-matter defect fixtures below: back matter that parses to a scalar
# rather than a mapping.
WELL_FORMED_NOTE_FOR_BACKMATTER = """\
---
title: BackMatterVictim
type: note
---

## Content

Body text.
"""


class TestFindAllPythonFallbackNonMappingParseErrors:
    """An unparseable note must not kill the whole scan.

    These three fixtures parse without a YAML syntax error but resolve to a
    non-mapping value (a bare scalar) where a mapping is required - for the
    front matter, and separately for the back matter. `find_all` must isolate
    each one: skip it, keep the good note, and warn exactly once naming it.
    """

    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
        False,
    )
    @patch(
        "buvis.pybase.adapters.console.console.console",
    )
    def test_find_all_skips_note_with_bare_scalar_frontmatter_and_warns_once(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        good = tmp_path / "good.md"
        good.write_text(MINIMAL_ZETTEL, encoding="utf-8")
        bad = tmp_path / "bad_scalar_frontmatter.md"
        bad.write_text(
            "---\njust a string\n---\n\n## Content\n\nBody.\n",
            encoding="utf-8",
        )

        repo = MarkdownZettelRepository()
        zettels = repo.find_all(str(tmp_path))

        assert len(zettels) == 1
        assert zettels[0].get_data().metadata.get("title") == "Test"
        mock_console.warning.assert_called_once()
        assert "bad_scalar_frontmatter.md" in mock_console.warning.call_args[0][0]

    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
        False,
    )
    @patch(
        "buvis.pybase.adapters.console.console.console",
    )
    def test_find_all_skips_note_with_scalar_int_backmatter_and_warns_once(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        good = tmp_path / "good.md"
        good.write_text(MINIMAL_ZETTEL, encoding="utf-8")
        bad = tmp_path / "bad_int_backmatter.md"
        bad.write_text(
            WELL_FORMED_NOTE_FOR_BACKMATTER + "\n---\n42\n",
            encoding="utf-8",
        )

        repo = MarkdownZettelRepository()
        zettels = repo.find_all(str(tmp_path))

        assert len(zettels) == 1
        assert zettels[0].get_data().metadata.get("title") == "Test"
        mock_console.warning.assert_called_once()
        assert "bad_int_backmatter.md" in mock_console.warning.call_args[0][0]

    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
        False,
    )
    @patch(
        "buvis.pybase.adapters.console.console.console",
    )
    def test_find_all_skips_note_with_bare_string_backmatter_and_warns_once(
        self, mock_console: MagicMock, tmp_path: Path
    ) -> None:
        good = tmp_path / "good.md"
        good.write_text(MINIMAL_ZETTEL, encoding="utf-8")
        bad = tmp_path / "bad_string_backmatter.md"
        bad.write_text(
            WELL_FORMED_NOTE_FOR_BACKMATTER + "\n---\nplain string\n",
            encoding="utf-8",
        )

        repo = MarkdownZettelRepository()
        zettels = repo.find_all(str(tmp_path))

        assert len(zettels) == 1
        assert zettels[0].get_data().metadata.get("title") == "Test"
        mock_console.warning.assert_called_once()
        assert "bad_string_backmatter.md" in mock_console.warning.call_args[0][0]


class TestFindAllWarningRealRender:
    """The warning must name the bad file verbatim in the actual rendered
    output. A filename containing square brackets looks like Rich markup, so
    this must be checked against the real console render path - a mocked
    console cannot observe text being eaten during rendering.
    """

    @patch(
        "buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository._HAS_RUST",
        False,
    )
    def test_find_all_warning_names_bracketed_filename_verbatim_in_real_render(self, tmp_path: Path) -> None:
        good = tmp_path / "good.md"
        good.write_text(MINIMAL_ZETTEL, encoding="utf-8")
        bad = tmp_path / "[wip] bad.md"
        bad.write_bytes(INVALID_UTF8_NOTE_BYTES)

        repo = MarkdownZettelRepository()
        with console.capture() as capture:
            zettels = repo.find_all(str(tmp_path))
        output = capture.get()

        assert len(zettels) == 1
        assert zettels[0].get_data().metadata.get("title") == "Test"
        assert "[wip]" in output
        assert "bad.md" in output
