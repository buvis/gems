from __future__ import annotations

import re
from pathlib import Path

import pytest
from bim.commands.create_note.create_note import CommandCreateNote
from bim.commands.edit_note.edit_note import CommandEditNote
from bim.params.create_note import CreateNoteParams
from bim.params.edit_note import EditNoteParams
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter import MarkdownZettelFormatter
from buvis.pybase.zettel.infrastructure.persistence.file_parsers.parsers.markdown.markdown import (
    MarkdownZettelFileParser,
)
from buvis.pybase.zettel.infrastructure.persistence.template_loader import discover_templates, run_template_hooks
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval

from tests.tools.bim.create_note_helpers import ScratchVault

TEMPLATE_NAMES = [
    "note",
    "project",
    "contact",
    "meeting-minutes",
    "illustrated-note",
    "youtube",
    "article",
    "book",
    "problem-resolution-report",
]


class TestCreateEditRoundTrip:
    @pytest.mark.parametrize("template_name", TEMPLATE_NAMES)
    def test_bundled_template_stays_clean_and_stable(
        self, scratch_vault: ScratchVault, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, template_name: str
    ) -> None:
        notes, repo, formatter = scratch_vault
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path / "config"))
        projects = tmp_path / "projects"
        projects.mkdir()
        cmd = CommandCreateNote(
            params=CreateNoteParams(
                zettel_type=template_name,
                title="Probe",
                daily_log=False,
                extra_answers={
                    "deliverable": "fix",
                    "location": "teams",
                    "web": "https://example.com",
                    "video": "dQw4w9WgXcQ",
                },
                body="Original" if template_name == "article" else None,
                summary="Facts" if template_name == "article" else None,
            ),
            path_zettelkasten=notes,
            repo=repo,
            formatter=formatter,
            templates=discover_templates(python_eval),
            hook_runner=lambda hooks, data, root: run_template_hooks(hooks, data, root, path_projects=projects),
            path_articles=tmp_path / "articles",
        )
        result = cmd.execute()
        assert result.success, result.error
        path = Path(result.metadata["path"])
        original = path.read_text()
        assert not re.search(r" +$", original, re.M)
        assert original.endswith("\n") and not original.endswith("\n\n")
        assert MarkdownZettelFormatter.format(MarkdownZettelFileParser.parse(original)) == original

        for summary in ("x", "y"):
            edited = CommandEditNote(
                params=EditNoteParams(paths=[path], changes={"summary": summary}), repo=repo
            ).execute()
            assert edited.success, edited.error
            updated = path.read_text()
            assert not re.search(r" +$", updated, re.M)
            assert updated.split("\n---\n", 1)[1] == original.split("\n---\n", 1)[1]
