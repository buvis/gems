from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fren.commands.slug.slug import CommandSlug


class TestSlugBasic:
    def test_slugify_simple(self, tmp_path: Path) -> None:
        source = tmp_path / "Hello World.txt"
        source.write_text("x")

        result = CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "hello-world.txt").exists()
        assert result.output == "Renamed 1 file(s)"

    def test_slugify_diacritics(self, tmp_path: Path) -> None:
        source = tmp_path / "café résumé.pdf"
        source.write_text("x")

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "cafe-resume.pdf").exists()

    def test_slugify_special_chars(self, tmp_path: Path) -> None:
        source = tmp_path / "file (1) [copy].txt"
        source.write_text("x")

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "file-1-copy.txt").exists()

    def test_no_rename_needed(self, tmp_path: Path) -> None:
        source = tmp_path / "already-clean.txt"
        source.write_text("x")

        result = CommandSlug(paths=(str(source),)).execute()

        assert source.exists()
        assert result.output == "Renamed 0 file(s)"

    def test_unnamed_fallback(self, tmp_path: Path) -> None:
        source = tmp_path / "###.txt"
        source.write_text("x")

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "unnamed.txt").exists()


class TestSlugEml:
    def test_eml_with_date_and_subject(self, tmp_path: Path) -> None:
        source = tmp_path / "mail.eml"
        source.write_text(
            "Date: Tue, 07 Jan 2025 15:30:00 +0000\nSubject: Project Update\n\nbody\n",
            encoding="utf-8",
        )

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "20250107153000-project-update.eml").exists()

    def test_eml_strips_re_prefix(self, tmp_path: Path) -> None:
        source = tmp_path / "reply.eml"
        source.write_text("Subject: Re: Meeting Notes\n\nbody\n", encoding="utf-8")

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "meeting-notes.eml").exists()

    def test_eml_strips_fwd_prefix(self, tmp_path: Path) -> None:
        source = tmp_path / "forward.eml"
        source.write_text("Subject: Fwd: Important\n\nbody\n", encoding="utf-8")

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "important.eml").exists()

    def test_eml_missing_date(self, tmp_path: Path) -> None:
        source = tmp_path / "nodate.eml"
        source.write_text("Subject: Roadmap Draft\n\nbody\n", encoding="utf-8")

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "roadmap-draft.eml").exists()

    def test_eml_malformed(self, tmp_path: Path) -> None:
        source = tmp_path / "café ###.eml"
        source.write_bytes(b"garbage")

        with patch(
            "fren.commands.slug.slug.email.message_from_binary_file",
            side_effect=ValueError("malformed"),
        ):
            CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "cafe.eml").exists()


    def test_eml_rfc2047_encoded_subject(self, tmp_path: Path) -> None:
        source = tmp_path / "encoded.eml"
        source.write_bytes(
            b"Date: Fri, 27 Feb 2026 17:29:07 +0000\r\n"
            b"Subject: =?utf-8?q?D=C4=9Bkujeme_za_objedn=C3=A1vku_#1119771906_na_Rohlik.cz?=\r\n"
            b"\r\nbody\r\n"
        )

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "20260227172907-dekujeme-za-objednavku-1119771906-na-rohlik-cz.eml").exists()


class TestSlugCollision:
    def test_collision_adds_suffix(self, tmp_path: Path) -> None:
        first = tmp_path / "A!.txt"
        second = tmp_path / "A@.txt"
        first.write_text("first")
        second.write_text("second")

        CommandSlug(paths=(str(first), str(second))).execute()

        assert (tmp_path / "a.txt").exists()
        assert (tmp_path / "a-1.txt").exists()

    def test_multiple_collisions(self, tmp_path: Path) -> None:
        first = tmp_path / "A!.txt"
        second = tmp_path / "A@.txt"
        third = tmp_path / "A#.txt"
        first.write_text("first")
        second.write_text("second")
        third.write_text("third")

        CommandSlug(paths=(str(first), str(second), str(third))).execute()

        assert (tmp_path / "a.txt").exists()
        assert (tmp_path / "a-1.txt").exists()
        assert (tmp_path / "a-2.txt").exists()


class TestSlugEmlEdgeCases:
    def test_eml_naive_datetime(self, tmp_path: Path) -> None:
        """Covers line 70: datetime without tzinfo gets UTC assigned."""
        source = tmp_path / "naive.eml"
        # Date without timezone offset produces naive datetime
        source.write_text(
            "Date: 07 Jan 2025 10:00:00\nSubject: Naive\n\nbody\n",
            encoding="utf-8",
        )

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "20250107100000-naive.eml").exists()

    def test_eml_unparseable_date(self, tmp_path: Path) -> None:
        """Covers lines 72-73: bad date string triggers ValueError, date_prefix stays empty."""
        source = tmp_path / "baddate.eml"
        source.write_text(
            "Date: not-a-date\nSubject: Good Subject\n\nbody\n",
            encoding="utf-8",
        )

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "good-subject.eml").exists()

    def test_eml_no_subject(self, tmp_path: Path) -> None:
        """eml with empty subject falls back to 'unnamed'."""
        source = tmp_path / "empty_subj.eml"
        source.write_text("Date: Tue, 07 Jan 2025 12:00:00 +0000\n\nbody\n", encoding="utf-8")

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "20250107120000-unnamed.eml").exists()

    def test_eml_fw_prefix_stripped(self, tmp_path: Path) -> None:
        """Fw: prefix (short form) is stripped."""
        source = tmp_path / "fw.eml"
        source.write_text("Subject: Fw: Ticket\n\nbody\n", encoding="utf-8")

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "ticket.eml").exists()

    def test_slugify_name_plain_unnamed_fallback(self, tmp_path: Path) -> None:
        """Covers line 87: _slugify_name_plain returns 'unnamed' for empty slug."""
        source = tmp_path / "###.eml"
        source.write_bytes(b"garbage")

        # Force the eml parser to fail so it falls back to _slugify_name_plain
        with patch(
            "fren.commands.slug.slug.email.message_from_binary_file",
            side_effect=OSError("bad"),
        ):
            CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "unnamed.eml").exists()


class TestSlugErrors:
    def test_nonexistent_path(self, tmp_path: Path) -> None:
        existing = tmp_path / "ok.txt"
        existing.write_text("x")
        missing = tmp_path / "missing.txt"

        result = CommandSlug(paths=(str(existing), str(missing))).execute()

        assert result.success
        assert any("Path not found" in warning for warning in result.warnings)

    def test_rename_exception_warns(self, tmp_path: Path) -> None:
        """Covers lines 33-34: exception during rename produces warning."""
        source = tmp_path / "Hello World.txt"
        source.write_text("x")

        with patch.object(Path, "rename", side_effect=OSError("disk full")):
            result = CommandSlug(paths=(str(source),)).execute()

        assert result.success
        assert any("Failed to rename" in w for w in result.warnings)
        assert result.output == "Renamed 0 file(s)"
