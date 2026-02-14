from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bim.cli import cli
from bim.commands.edit_note.edit_note import CommandEditNote, edit_single

MINIMAL_ZETTEL = """\
---
title: Original Title
type: note
tags:
  - alpha
  - beta
processed: false
publish: false
---

## Content

Some body text.
"""


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def zettel_file(tmp_path: Path) -> Path:
    p = tmp_path / "202401151030 Test note.md"
    p.write_text(MINIMAL_ZETTEL, encoding="utf-8")
    return p


class TestEditSingle:
    def test_updates_metadata(self, zettel_file: Path) -> None:
        edit_single(zettel_file, {"title": "New Title"})
        content = zettel_file.read_text()
        assert "title: New Title" in content

    def test_updates_multiple_fields(self, zettel_file: Path) -> None:
        edit_single(zettel_file, {"title": "Changed", "processed": True})
        content = zettel_file.read_text()
        assert "Changed" in content
        assert "processed: true" in content

    def test_updates_tags(self, zettel_file: Path) -> None:
        edit_single(zettel_file, {"tags": ["gamma"]})
        content = zettel_file.read_text()
        assert "gamma" in content
        assert "alpha" not in content

    def test_updates_reference(self, zettel_file: Path) -> None:
        edit_single(zettel_file, {"source": "http://example.com"}, target="reference")
        content = zettel_file.read_text()
        assert "http://example.com" in content

    def test_updates_section(self, zettel_file: Path) -> None:
        edit_single(zettel_file, {"# Original Title": "Replaced body."}, target="section")
        content = zettel_file.read_text()
        assert "Replaced body." in content
        assert "Some body text." not in content

    def test_quiet_suppresses_console(self, zettel_file: Path) -> None:
        with patch("bim.commands.edit_note.edit_note.console") as mock_console:
            edit_single(zettel_file, {"title": "Quiet"}, quiet=True)
            mock_console.success.assert_not_called()

    def test_loud_prints_console(self, zettel_file: Path) -> None:
        with patch("bim.commands.edit_note.edit_note.console") as mock_console:
            edit_single(zettel_file, {"title": "Loud"})
            mock_console.success.assert_called_once()

    def test_returns_message(self, zettel_file: Path) -> None:
        msg = edit_single(zettel_file, {"title": "X"})
        assert zettel_file.name in msg

    def test_preserves_unmodified_fields(self, zettel_file: Path) -> None:
        edit_single(zettel_file, {"title": "Changed"})
        content = zettel_file.read_text()
        assert "type: note" in content
        assert "alpha" in content


class TestCommandEditNote:
    def test_scripted_calls_edit_single(self, zettel_file: Path) -> None:
        with patch("bim.commands.edit_note.edit_note.edit_single") as mock:
            cmd = CommandEditNote(path=zettel_file, changes={"title": "X"})
            cmd.execute()
            mock.assert_called_once_with(zettel_file, {"title": "X"}, "metadata")

    def test_no_changes_launches_tui(self, zettel_file: Path) -> None:
        with patch("bim.commands.edit_note.tui.EditNoteApp") as mock_app:
            cmd = CommandEditNote(path=zettel_file)
            cmd.execute()
            mock_app.assert_called_once_with(path=zettel_file)
            mock_app.return_value.run.assert_called_once()

    def test_target_passed_through(self, zettel_file: Path) -> None:
        with patch("bim.commands.edit_note.edit_note.edit_single") as mock:
            cmd = CommandEditNote(path=zettel_file, changes={"src": "x"}, target="reference")
            cmd.execute()
            mock.assert_called_once_with(zettel_file, {"src": "x"}, "reference")


class TestEditCliCommand:
    def test_edit_scripted(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text(MINIMAL_ZETTEL)

        with patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_cmd:
            instance = mock_cmd.return_value
            result = runner.invoke(
                cli,
                ["edit", str(note), "--title", "New", "--tags", "a,b", "--type", "project"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                path=note,
                changes={"title": "New", "tags": ["a", "b"], "type": "project"},
            )
            instance.execute.assert_called_once()

    def test_edit_boolean_flags(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text(MINIMAL_ZETTEL)

        with patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_cmd:
            instance = mock_cmd.return_value
            result = runner.invoke(
                cli,
                ["edit", str(note), "--processed", "--publish"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                path=note,
                changes={"processed": True, "publish": True},
            )
            instance.execute.assert_called_once()

    def test_edit_no_flags_launches_tui(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text(MINIMAL_ZETTEL)

        with patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_cmd:
            instance = mock_cmd.return_value
            result = runner.invoke(
                cli,
                ["edit", str(note)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(path=note, changes=None)
            instance.execute.assert_called_once()

    def test_edit_extra_set(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text(MINIMAL_ZETTEL)

        with patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_cmd:
            instance = mock_cmd.return_value
            result = runner.invoke(
                cli,
                ["edit", str(note), "-s", "custom=val"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                path=note,
                changes={"custom": "val"},
            )
            instance.execute.assert_called_once()

    def test_edit_missing_file(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["edit", "/nonexistent.md"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "doesn't exist" in result.output
