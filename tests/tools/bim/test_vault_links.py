from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from bim.shared.vault_links import append_daily_log, contact_names, daily_log_entry, link_contacts

NOW = datetime(2026, 11, 9, 13, 49, 25, tzinfo=timezone(timedelta(hours=1)))
LINK = "[[notes/20261109134925|Why caches lie]]"
ENTRY = f"- [ ] _09.11.2026 13:49:25_ - {LINK}"
NAMES = {"ada lovelace": "ada-lovelace", "lovelace, ada": "ada-lovelace", "alan turing": "alan-turing"}


def _write_contact(folder: Path, slug: str, frontmatter: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{slug}.md").write_text(f"---\n{frontmatter}\n---\n\n# Body\n", encoding="utf-8")


class TestDailyLog:
    def test_log_entry_matches_quickadd_shape(self) -> None:
        assert daily_log_entry(NOW, LINK) == ENTRY

    def test_appends_after_last_log_line(self, tmp_path: Path) -> None:
        daily = tmp_path / "2026-11-09.md"
        daily.write_text("# Day\n\n## Log\n\n- [ ] _09.11.2026 08:00:00_ - first\n\n\n## Notes\n\nkeep\n")

        result = append_daily_log(tmp_path, NOW, LINK)

        assert result == {"status": "added", "path": str(daily), "entry": ENTRY}
        assert (
            daily.read_text()
            == f"# Day\n\n## Log\n\n- [ ] _09.11.2026 08:00:00_ - first\n{ENTRY}\n\n\n## Notes\n\nkeep\n"
        )

    def test_empty_log_section_gets_the_entry_under_the_heading(self, tmp_path: Path) -> None:
        daily = tmp_path / "2026-11-09.md"
        daily.write_text("## Log\n\n## Notes\n")

        append_daily_log(tmp_path, NOW, LINK)

        assert daily.read_text() == f"## Log\n{ENTRY}\n\n## Notes\n"

    def test_comment_lines_inside_fenced_code_are_not_headings(self, tmp_path: Path) -> None:
        daily = tmp_path / "2026-11-09.md"
        daily.write_text("## Log\n\n```bash\n# install deps\nmake\n```\n\n## Notes\n")

        append_daily_log(tmp_path, NOW, LINK)

        assert daily.read_text() == f"## Log\n\n```bash\n# install deps\nmake\n```\n{ENTRY}\n\n## Notes\n"

    def test_skips_when_daily_note_missing(self, tmp_path: Path) -> None:
        folder = tmp_path / "daily"

        result = append_daily_log(folder, NOW, LINK)

        assert result == {
            "status": f"skipped: {folder / '2026-11-09.md'} does not exist (Obsidian creates it)",
            "entry": ENTRY,
        }
        assert not folder.exists()

    def test_skips_when_no_log_heading(self, tmp_path: Path) -> None:
        daily = tmp_path / "2026-11-09.md"
        daily.write_text("# Day\n\n## Notes\n")

        result = append_daily_log(tmp_path, NOW, LINK)

        assert result == {"status": f"skipped: {daily} has no '## Log' section", "entry": ENTRY}
        assert daily.read_text() == "# Day\n\n## Notes\n"


class TestContactNames:
    def test_indexes_title_aliases_and_last_first(self, tmp_path: Path) -> None:
        _write_contact(
            tmp_path, "ada-lovelace", 'title: Ada Lovelace\naliases: [Countess Lovelace, "A. Lovelace", Ada]'
        )
        _write_contact(tmp_path, "alan-turing", "title: Alan Turing\naliases:\n  - Prof. Turing\n  - Turing")

        assert contact_names(tmp_path) == {
            "ada lovelace": "ada-lovelace",
            "lovelace, ada": "ada-lovelace",
            "countess lovelace": "ada-lovelace",
            "a. lovelace": "ada-lovelace",
            "alan turing": "alan-turing",
            "turing, alan": "alan-turing",
            "prof. turing": "alan-turing",
        }

    def test_ambiguous_name_is_not_linked(self, tmp_path: Path) -> None:
        _write_contact(tmp_path, "ada-lovelace", "title: Ada Lovelace\naliases: [The Boss]")
        _write_contact(tmp_path, "alan-turing", "title: Alan Turing\naliases: [The Boss]")
        (tmp_path / "broken.md").write_bytes(b"\xff\xfe")

        names = contact_names(tmp_path)

        assert "the boss" not in names
        assert names["ada lovelace"] == "ada-lovelace"
        assert names["alan turing"] == "alan-turing"
        text, links = link_contacts("The Boss met Ada Lovelace.", names, "notes/contact")
        assert text == "The Boss met [[notes/contact/ada-lovelace|Ada Lovelace]]."
        assert links == ["[[notes/contact/ada-lovelace|Ada Lovelace]]"]

    def test_missing_folder_gives_no_names(self, tmp_path: Path) -> None:
        assert contact_names(tmp_path / "contact") == {}


class TestLinkContacts:
    def test_links_first_mention_case_and_diacritic_insensitive(self) -> None:
        text = "Met Ádá  Lovelace. Later ada lovelace again, then Alan Turing."

        linked, links = link_contacts(text, NAMES, "notes/contact")

        assert linked == (
            "Met [[notes/contact/ada-lovelace|Ádá  Lovelace]]. Later ada lovelace again, "
            "then [[notes/contact/alan-turing|Alan Turing]]."
        )
        assert links == ["[[notes/contact/ada-lovelace|Ádá  Lovelace]]", "[[notes/contact/alan-turing|Alan Turing]]"]

    def test_never_links_inside_code_links_or_urls(self) -> None:
        text = (
            "`Ada Lovelace` and ```\nAda Lovelace\n``` and [[x|Ada Lovelace]] and [Ada Lovelace](http://x) "
            "and ![Ada Lovelace](photo.jpg) and https://ada lovelace.example then Ada Lovelace."
        )

        linked, links = link_contacts(text, NAMES, "notes/contact")

        assert linked == text.replace("then Ada Lovelace.", "then [[notes/contact/ada-lovelace|Ada Lovelace]].")
        assert links == ["[[notes/contact/ada-lovelace|Ada Lovelace]]"]

    def test_last_first_form_is_linked(self) -> None:
        linked, links = link_contacts("From: Lovelace, Ada (Acme)", NAMES, "notes/contact")

        assert linked == "From: [[notes/contact/ada-lovelace|Lovelace, Ada]] (Acme)"
        assert links == ["[[notes/contact/ada-lovelace|Lovelace, Ada]]"]

    def test_skip_slug_and_word_boundaries(self) -> None:
        assert link_contacts("Ada Lovelace", NAMES, "notes/contact", skip_slug="ada-lovelace") == ("Ada Lovelace", [])
        assert link_contacts("Ada Lovelaces", NAMES, "notes/contact") == ("Ada Lovelaces", [])
        assert link_contacts("", NAMES, "notes/contact") == ("", [])
        assert link_contacts("Ada Lovelace", {}, "notes/contact") == ("Ada Lovelace", [])


class TestReviewParsing:
    def test_log_heading_inside_fence_is_ignored(self, tmp_path: Path) -> None:
        daily = tmp_path / "2026-11-09.md"
        daily.write_text("```md\n## Log\n```\n\n## Log\n\n## Notes\n")
        append_daily_log(tmp_path, NOW, LINK)
        assert daily.read_text() == f"```md\n## Log\n```\n\n## Log\n{ENTRY}\n\n## Notes\n"

    def test_crlf_log_heading(self, tmp_path: Path) -> None:
        daily = tmp_path / "2026-11-09.md"
        daily.write_bytes(b"## Log\r\n\r\n## Notes\r\n")
        result = append_daily_log(tmp_path, NOW, LINK)
        assert result["status"] == "added"

    def test_inline_code_and_reference_links_are_protected(self) -> None:
        text = "``Ada Lovelace ` code`` [Ada Lovelace][person]"
        assert link_contacts(text, NAMES, "notes/contact") == (text, [])

    def test_quoted_alias_with_comma(self, tmp_path: Path) -> None:
        _write_contact(tmp_path, "ada", 'title: Ada Lovelace\naliases: [Countess Lovelace, "Byron, Ada Lovelace"]')
        assert contact_names(tmp_path)["byron, ada lovelace"] == "ada"
