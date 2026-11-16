from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bim.commands.format_note.format_note import CommandFormatNote
from bim.params.format_note import FormatNoteParams
from pytest_mock import MockerFixture


@pytest.fixture
def zettel_file(tmp_path: Path, minimal_zettel: str) -> Path:
    p = tmp_path / "202401151030 Test note.md"
    p.write_text(minimal_zettel, encoding="utf-8")
    return p


@pytest.fixture
def format_note_dependencies():
    repo = MagicMock()
    formatter = MagicMock()
    note = MagicMock()
    with (
        patch("bim.commands.format_note.format_note.ReadZettelUseCase") as mock_reader_cls,
        patch("bim.commands.format_note.format_note.PrintZettelUseCase") as mock_printer_cls,
    ):
        reader = mock_reader_cls.return_value
        reader.execute.return_value = note
        printer = mock_printer_cls.return_value
        printer.execute.return_value = "formatted content"
        yield {
            "repo": repo,
            "formatter": formatter,
            "reader": reader,
            "printer": printer,
            "mock_reader_cls": mock_reader_cls,
            "mock_printer_cls": mock_printer_cls,
        }


class TestCommandFormatNote:
    def test_missing_file_reports_failure(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.md"
        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[missing]),
            repo=MagicMock(),
            formatter=MagicMock(),
        )
        result = cmd.execute()
        assert result.success is False
        assert result.error == f"{missing} doesn't exist"

    def test_writes_to_output_file(
        self,
        zettel_file: Path,
        tmp_path: Path,
        format_note_dependencies,
    ) -> None:
        output_path = tmp_path / "formatted.md"
        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[zettel_file], path_output=output_path),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )
        result = cmd.execute()

        assert result.success is True
        assert result.metadata["written_to"] == str(output_path)
        assert output_path.read_text(encoding="utf-8") == "formatted content"

    def test_batch_formats_all(
        self,
        tmp_path: Path,
        minimal_zettel: str,
        format_note_dependencies,
    ) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text(minimal_zettel, encoding="utf-8")
        b.write_text(minimal_zettel, encoding="utf-8")

        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[a, b]),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )
        result = cmd.execute()
        assert result.success is True
        assert result.metadata["formatted_count"] == 2
        assert a.read_text(encoding="utf-8") == "formatted content"
        assert b.read_text(encoding="utf-8") == "formatted content"

    def test_batch_skips_missing(
        self,
        tmp_path: Path,
        minimal_zettel: str,
        format_note_dependencies,
    ) -> None:
        exists = tmp_path / "exists.md"
        exists.write_text(minimal_zettel, encoding="utf-8")
        missing = tmp_path / "missing.md"

        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[missing, exists]),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )
        result = cmd.execute()
        assert result.success is True
        assert result.metadata["formatted_count"] == 1
        assert result.warnings == [f"{missing} doesn't exist"]
        assert exists.read_text(encoding="utf-8") == "formatted content"

    def test_batch_write_failure_leaves_existing_file_untouched(
        self,
        tmp_path: Path,
        minimal_zettel: str,
        format_note_dependencies,
        mocker: MockerFixture,
    ) -> None:
        """os.replace failure during the atomic write propagates and leaves the file byte-for-byte intact."""
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text(minimal_zettel, encoding="utf-8")
        b.write_text(minimal_zettel, encoding="utf-8")
        original_a = a.read_text(encoding="utf-8")

        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=OSError("disk full"),
        )

        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[a, b]),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )

        with pytest.raises(OSError):
            cmd.execute()

        assert a.read_text(encoding="utf-8") == original_a

    def test_single_write_failure_leaves_existing_file_untouched(
        self,
        zettel_file: Path,
        tmp_path: Path,
        format_note_dependencies,
        mocker: MockerFixture,
    ) -> None:
        """os.replace failure writing path_output returns failure and leaves the file byte-for-byte intact."""
        output_path = tmp_path / "formatted.md"
        output_path.write_text("original content", encoding="utf-8")

        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=OSError("disk full"),
        )

        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[zettel_file], path_output=output_path),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )
        result = cmd.execute()

        assert result.success is False
        assert output_path.read_text(encoding="utf-8") == "original content"

    def test_single_returns_content(
        self,
        zettel_file: Path,
        format_note_dependencies,
    ) -> None:
        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[zettel_file]),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )
        result = cmd.execute()

        assert result.success is True
        assert result.output == "formatted content"

    def test_single_includes_original(
        self,
        zettel_file: Path,
        format_note_dependencies,
    ) -> None:
        original = zettel_file.read_text(encoding="utf-8")
        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[zettel_file]),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )
        result = cmd.execute()

        assert result.success is True
        assert result.metadata["original"] == original

    def test_write_os_error(
        self,
        zettel_file: Path,
        tmp_path: Path,
    ) -> None:
        """OSError writing output file returns failure."""
        output_path = tmp_path / "nonexistent_dir" / "out.md"
        with (
            patch("bim.commands.format_note.format_note.ReadZettelUseCase") as mock_reader_cls,
            patch("bim.commands.format_note.format_note.PrintZettelUseCase") as mock_printer_cls,
        ):
            note = MagicMock()
            mock_reader_cls.return_value.execute.return_value = note
            mock_printer_cls.return_value.execute.return_value = "formatted"

            cmd = CommandFormatNote(
                params=FormatNoteParams(paths=[zettel_file], path_output=output_path),
                repo=MagicMock(),
                formatter=MagicMock(),
            )
            result = cmd.execute()

        assert result.success is False
        assert "error occurred while writing" in result.error

    def test_write_unicode_encode_error(
        self,
        zettel_file: Path,
        tmp_path: Path,
    ) -> None:
        """UnicodeEncodeError writing output file returns failure."""
        output_path = tmp_path / "out.md"

        with (
            patch("bim.commands.format_note.format_note.ReadZettelUseCase") as mock_reader_cls,
            patch("bim.commands.format_note.format_note.PrintZettelUseCase") as mock_printer_cls,
        ):
            note = MagicMock()
            mock_reader_cls.return_value.execute.return_value = note
            # A lone surrogate cannot be encoded as UTF-8, so the real encoder
            # raises UnicodeEncodeError naturally during the write.
            mock_printer_cls.return_value.execute.return_value = "\ud800"

            cmd = CommandFormatNote(
                params=FormatNoteParams(paths=[zettel_file], path_output=output_path),
                repo=MagicMock(),
                formatter=MagicMock(),
            )

            result = cmd.execute()

        assert result.success is False
        assert "could not be encoded" in result.error

    def test_path_output_none_resolves_to_none(
        self,
        zettel_file: Path,
        format_note_dependencies,
    ) -> None:
        """When path_output is None, the output content is returned directly."""
        cmd = CommandFormatNote(
            params=FormatNoteParams(paths=[zettel_file], path_output=None),
            repo=format_note_dependencies["repo"],
            formatter=format_note_dependencies["formatter"],
        )
        result = cmd.execute()

        assert result.success is True
        assert result.output == "formatted content"
        assert "written_to" not in result.metadata


def _tiromex_concept(concept_type: str, unknown: str, relation: str) -> str:
    return (
        "---\n"
        "id: 20260411145300\n"
        "title: Knowledge is justified belief\n"
        "date: 2026-04-11T14:53:00+02:00\n"
        "tags: []\n"
        "type: note\n"
        "publish: false\n"
        "processed: false\n"
        f"concept-type: {concept_type}\n"
        "assent: tentative\n"
        "lifecycle: fleeting\n"
        "claims:\n"
        "  - id: c1\n"
        "    statement: Knowledge is justified belief\n"
        f"{unknown}\n"
        "---\n"
        "\n"
        "# Knowledge is justified belief\n"
        "\n"
        "The claim holds for ordinary cases.\n"
        "\n"
        "---\n"
        "\n"
        "- parent:: [[notes/tiromex/20260411140000|§ Epistemology]]\n"
        f"{relation}\n"
    )


class TestFormatTiromexConceptNote:
    @pytest.mark.parametrize(
        ("concept_type", "unknown", "relation"),
        [
            ("thesis", "x-reviewer: alice", "- supports:: [[notes/tiromex/20260412090000|Belief needs grounds]]"),
            ("observation", "source-note: kept", "- contradicts:: [[notes/tiromex/20260413100000|Luck defeats it]]"),
        ],
    )
    def test_keeps_concept_fields_and_relations_and_is_idempotent(
        self, tmp_path: Path, concept_type: str, unknown: str, relation: str
    ) -> None:
        from bim.dependencies import get_formatter, get_repo

        note = tmp_path / "20260411145300.md"
        note.write_text(_tiromex_concept(concept_type, unknown, relation), encoding="utf-8")
        first, second = tmp_path / "first.md", tmp_path / "second.md"

        for source, target in ((note, first), (first, second)):
            params = FormatNoteParams(paths=[source], path_output=target)
            result = CommandFormatNote(params=params, repo=get_repo(), formatter=get_formatter()).execute()
            assert result.success is True

        lines = first.read_text(encoding="utf-8").splitlines()
        for expected in (
            f"concept-type: {concept_type}",
            "assent: tentative",
            "lifecycle: fleeting",
            unknown,
            "The claim holds for ordinary cases.",
            "- parent:: [[notes/tiromex/20260411140000|§ Epistemology]]",
            relation,
        ):
            assert expected in lines
        assert any("Knowledge is justified belief" in line and "statement" in line for line in lines)
        assert [line for line in lines if line.startswith("# ")] == ["# Knowledge is justified belief"]
        assert second.read_bytes() == first.read_bytes()
