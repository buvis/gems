from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import pytest
from bim.params.create_note import CreateNoteParams

from tests.tools.bim.create_note_helpers import (
    NoteTemplate,
    ScratchVault,
    article_command,
    create_command,
    write_contact,
)


class TestVaultLinks:
    def test_daily_log_runs_after_save(self, scratch_vault: ScratchVault) -> None:
        notes, repo, _ = scratch_vault
        daily_dir = notes / "calendar" / "daily"
        daily_dir.mkdir(parents=True)
        daily = daily_dir / f"{datetime.now().astimezone():%Y-%m-%d}.md"
        daily.write_text("# Today\n\n## Log\n\n- [ ] _old_ - existing\n\n## Notes\n")

        result = create_command(
            scratch_vault, CreateNoteParams(zettel_type="note", title="Logged"), path_daily=daily_dir
        ).execute()

        assert result.success is True
        saved = repo.find_by_location(result.metadata["path"])
        local = saved.date.astimezone()
        assert f"{local:%Y%m%d%H%M%S}" == str(saved.id)
        entry = f"- [ ] _{local:%d.%m.%Y %H:%M:%S}_ - {result.metadata['wikilink']}"
        assert result.metadata["daily_log"] == {"status": "added", "path": str(daily), "entry": entry}
        assert daily.read_text() == f"# Today\n\n## Log\n\n- [ ] _old_ - existing\n{entry}\n\n## Notes\n"
        assert "errors" not in result.metadata

    def test_daily_log_is_skipped_or_off_without_touching_the_vault(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        daily_dir = notes / "calendar" / "daily"

        skipped = create_command(
            scratch_vault, CreateNoteParams(zettel_type="note", title="One"), path_daily=daily_dir
        ).execute()
        off = create_command(
            scratch_vault, CreateNoteParams(zettel_type="note", title="Two", daily_log=False), path_daily=daily_dir
        ).execute()

        assert skipped.success is True
        assert skipped.metadata["daily_log"]["status"].startswith("skipped: ")
        assert skipped.metadata["daily_log"]["entry"].endswith(f"- {skipped.metadata['wikilink']}")
        assert not daily_dir.exists()
        assert off.success is True
        assert "daily_log" not in off.metadata

    def test_dry_run_reports_daily_log_as_not_written(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault

        result = create_command(
            scratch_vault, CreateNoteParams(zettel_type="note", title="Preview", dry_run=True), path_daily=notes / "d"
        ).execute()

        assert result.metadata["daily_log"]["status"] == "not written (dry run)"
        assert result.metadata["daily_log"]["entry"].endswith(f"- {result.metadata['wikilink']}")
        assert list(notes.iterdir()) == []

    def test_body_mentions_of_contacts_are_linked_once(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        write_contact(notes, "ada-lovelace", "Ada Lovelace")
        link = "[[notes/contact/ada-lovelace|Ada Lovelace]]"

        result = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", title="Meeting", body="Ada Lovelace spoke. Ada Lovelace again."),
        ).execute()

        assert result.success is True
        assert result.metadata["linked_contacts"] == [link]
        assert f"{link} spoke. Ada Lovelace again." in Path(result.metadata["path"]).read_text()

    def test_link_contacts_can_be_switched_off(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        write_contact(notes, "ada-lovelace", "Ada Lovelace")

        result = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", title="Copy", body="Ada Lovelace verbatim.", link_contacts=False),
        ).execute()

        assert "linked_contacts" not in result.metadata
        assert "Ada Lovelace verbatim." in Path(result.metadata["path"]).read_text()

    def test_contact_template_body_is_not_linked(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        write_contact(notes, "ada-lovelace", "Ada Lovelace")

        class ContactLike(NoteTemplate):
            folder = "contact"

        result = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", title="Alan", body="Knows Ada Lovelace."),
            ContactLike(),
        ).execute()

        assert result.success is True
        assert "linked_contacts" not in result.metadata
        content = Path(result.metadata["path"]).read_text()
        assert "Knows Ada Lovelace." in content
        assert "[[" not in content


class TestArticleWorkflow:
    def test_article_without_summary_fails(self, scratch_vault: ScratchVault, tmp_path: Path) -> None:
        result = article_command(
            scratch_vault, tmp_path, CreateNoteParams(zettel_type="article", title="T", body="Original")
        ).execute()

        assert result.success is False
        assert result.error == "article needs --summary-file with the core facts"
        assert list(scratch_vault[0].iterdir()) == []
        assert not (tmp_path / "archives" / "articles").exists()

    def test_article_without_original_fails(self, scratch_vault: ScratchVault, tmp_path: Path) -> None:
        result = article_command(
            scratch_vault, tmp_path, CreateNoteParams(zettel_type="article", title="T", summary="Facts", body=" \n")
        ).execute()

        assert result.success is False
        assert result.error == "article needs the original text: pass --body-file or --source"
        assert not (tmp_path / "archives" / "articles").exists()

    def test_article_archives_original_and_links_it(self, scratch_vault: ScratchVault, tmp_path: Path) -> None:
        notes, repo, _ = scratch_vault
        write_contact(notes, "ada-lovelace", "Ada Lovelace")
        source = notes.parent / "inbox" / "Big News.md"
        source.write_text("---\ntitle: ignored\n---\nOriginal text by Ada Lovelace.\n")
        params = CreateNoteParams(
            zettel_type="article",
            source=source,
            summary="\n\nCore facts from Ada Lovelace.\n",
            extra_answers={"web": "https://example.com/news"},
        )

        result = article_command(scratch_vault, tmp_path, params).execute()

        assert result.success is True
        saved = repo.find_by_location(result.metadata["path"])
        archive = Path(result.metadata["archive"]["path"])
        assert archive.name == "Big News.md"
        assert archive.parent.name == f"{saved.date:%Y%m}00"
        assert archive.parent.parent == tmp_path / "archives" / "articles" / f"{saved.date:%Y}"
        assert archive.read_text() == (
            "# Big News\n\nOriginal text by Ada Lovelace.\n\n\n---\n\nSource: https://example.com/news\n"
        )
        content = Path(result.metadata["path"]).read_text()
        assert result.metadata["type"] == "note"
        assert result.metadata["title"] == "Big News"
        assert f"- article:: [Big News](file://{quote(str(archive), safe='/')})" in content
        assert "- web:: [Big News](https://example.com/news)" in content
        assert "Core facts from [[notes/contact/ada-lovelace|Ada Lovelace]]." in content
        assert "Original text" not in content
        assert result.metadata["linked_contacts"] == ["[[notes/contact/ada-lovelace|Ada Lovelace]]"]
        assert not source.exists()
        assert result.metadata["trashed_source"] == str(notes.parent / ".trash" / "Big News.md")

    def test_article_dry_run_writes_nothing(self, scratch_vault: ScratchVault, tmp_path: Path) -> None:
        notes, _, _ = scratch_vault
        params = CreateNoteParams(zettel_type="article", title="T", body="Original", summary="Facts", dry_run=True)

        result = article_command(scratch_vault, tmp_path, params).execute()

        assert result.success is True
        assert result.metadata["archive"]["content"] == "# T\n\nOriginal\n"
        assert Path(result.metadata["archive"]["path"]).name == "T.md"
        assert "Facts" in result.metadata["content"]
        assert not (tmp_path / "archives" / "articles").exists()
        assert list(notes.iterdir()) == []

    def test_article_archive_is_removed_when_note_fails(self, scratch_vault: ScratchVault, tmp_path: Path) -> None:
        notes, repo, _ = scratch_vault
        source = notes.parent / "inbox" / "Big News.md"
        source.write_text("Original")
        params = CreateNoteParams(zettel_type="article", source=source, summary="Facts")

        with patch.object(repo, "save", autospec=True, side_effect=OSError("disk full")):
            result = article_command(scratch_vault, tmp_path, params).execute()

        assert result.success is False
        assert "disk full" in (result.error or "")
        assert list((tmp_path / "archives" / "articles").rglob("*.md")) == []
        assert list(notes.iterdir()) == []
        assert source.read_text() == "Original"
        assert not (notes.parent / ".trash").exists()


class TestReviewVaultRegressions:
    @pytest.mark.parametrize("invalid_utf8", [True, False])
    def test_daily_log_failure_keeps_success_and_cleans_source(
        self, scratch_vault: ScratchVault, invalid_utf8: bool
    ) -> None:
        notes = scratch_vault[0]
        daily_dir = notes.parent / "daily"
        daily_dir.mkdir()
        (daily_dir / f"{datetime.now().astimezone():%Y-%m-%d}.md").write_bytes(b"\xff")
        source = notes.parent / "inbox" / "Original.md"
        source.write_text("Body")
        cmd = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source), path_daily=daily_dir)
        if invalid_utf8:
            result = cmd.execute()
        else:
            with patch("bim.commands.create_note.create_note.append_daily_log", side_effect=OSError("denied")):
                result = cmd.execute()
        assert result.success
        assert result.metadata["errors"]
        assert Path(result.metadata["path"]).is_file()
        assert not source.exists()

    def test_interruption_removes_article_archive(self, scratch_vault: ScratchVault, tmp_path: Path) -> None:
        cmd = article_command(
            scratch_vault,
            tmp_path,
            CreateNoteParams(zettel_type="article", title="T", body="Original", summary="Facts"),
        )
        with patch.object(scratch_vault[1], "save", side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                cmd.execute()
        assert list((tmp_path / "archives").rglob("*.md")) == []

    def test_article_body_strips_frontmatter_and_preserves_whitespace(
        self, scratch_vault: ScratchVault, tmp_path: Path
    ) -> None:
        cmd = article_command(
            scratch_vault,
            tmp_path,
            CreateNoteParams(
                zettel_type="article", title="T", body="---\ntitle: ignored\n---\n\n Original  \n", summary="Facts"
            ),
        )
        result = cmd.execute()
        assert result.success
        assert Path(result.metadata["archive"]["path"]).read_text() == "# T\n\n\n Original  \n\n"

    @pytest.mark.parametrize("problem", ["existing", "unconfigured", "parent"])
    def test_article_archive_error_creates_no_note(
        self, scratch_vault: ScratchVault, tmp_path: Path, problem: str
    ) -> None:
        cmd = article_command(
            scratch_vault,
            tmp_path,
            CreateNoteParams(zettel_type="article", title="T", body="Original", summary="Facts"),
        )
        if problem == "existing":
            from bim.shared.article_archive import archive_path

            target = archive_path(cmd.path_articles, "T", datetime.now().astimezone())
            target.parent.mkdir(parents=True)
            target.write_text("Keep")
        elif problem == "unconfigured":
            cmd.path_articles = None
        else:
            cmd.path_articles = tmp_path / "missing" / "articles"
        result = cmd.execute()
        assert not result.success
        assert list(scratch_vault[0].iterdir()) == []
        if problem == "existing":
            assert target.read_text() == "Keep"

    def test_article_source_strips_only_one_frontmatter_block(
        self, scratch_vault: ScratchVault, tmp_path: Path
    ) -> None:
        source = scratch_vault[0].parent / "inbox" / "T.md"
        source.write_text("---\ntitle: ignored\n---\n---\nkeep: body\n---\nOriginal\n")
        cmd = article_command(
            scratch_vault, tmp_path, CreateNoteParams(zettel_type="article", source=source, summary="Facts")
        )
        result = cmd.execute()
        assert result.success
        assert Path(result.metadata["archive"]["path"]).read_text() == "# T\n\n---\nkeep: body\n---\nOriginal\n\n"
