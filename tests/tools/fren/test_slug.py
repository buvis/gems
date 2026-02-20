from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fren.commands.slug.slug import CommandSlug


class TestSlugBasic:
    def test_slugify_simple(self, tmp_path: Path) -> None:
        source = tmp_path / "Hello World.txt"
        source.write_text("x")

        result = CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "Hello-World.txt").exists()
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

        assert (tmp_path / "2025-01-07_1530_Project-Update.eml").exists()

    def test_eml_strips_re_prefix(self, tmp_path: Path) -> None:
        source = tmp_path / "reply.eml"
        source.write_text("Subject: Re: Meeting Notes\n\nbody\n", encoding="utf-8")

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "Meeting-Notes.eml").exists()

    def test_eml_strips_fwd_prefix(self, tmp_path: Path) -> None:
        source = tmp_path / "forward.eml"
        source.write_text("Subject: Fwd: Important\n\nbody\n", encoding="utf-8")

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "Important.eml").exists()

    def test_eml_missing_date(self, tmp_path: Path) -> None:
        source = tmp_path / "nodate.eml"
        source.write_text("Subject: Roadmap Draft\n\nbody\n", encoding="utf-8")

        CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "Roadmap-Draft.eml").exists()

    def test_eml_malformed(self, tmp_path: Path) -> None:
        source = tmp_path / "café ###.eml"
        source.write_bytes(b"garbage")

        with patch(
            "fren.commands.slug.slug.email.message_from_binary_file",
            side_effect=ValueError("malformed"),
        ):
            CommandSlug(paths=(str(source),)).execute()

        assert (tmp_path / "cafe.eml").exists()


class TestSlugCollision:
    def test_collision_adds_suffix(self, tmp_path: Path) -> None:
        first = tmp_path / "A!.txt"
        second = tmp_path / "A@.txt"
        first.write_text("first")
        second.write_text("second")

        CommandSlug(paths=(str(first), str(second))).execute()

        assert (tmp_path / "A.txt").exists()
        assert (tmp_path / "A-1.txt").exists()

    def test_multiple_collisions(self, tmp_path: Path) -> None:
        first = tmp_path / "A!.txt"
        second = tmp_path / "A@.txt"
        third = tmp_path / "A#.txt"
        first.write_text("first")
        second.write_text("second")
        third.write_text("third")

        CommandSlug(paths=(str(first), str(second), str(third))).execute()

        assert (tmp_path / "A.txt").exists()
        assert (tmp_path / "A-1.txt").exists()
        assert (tmp_path / "A-2.txt").exists()


class TestSlugErrors:
    def test_nonexistent_path(self, tmp_path: Path) -> None:
        existing = tmp_path / "ok.txt"
        existing.write_text("x")
        missing = tmp_path / "missing.txt"

        result = CommandSlug(paths=(str(existing), str(missing))).execute()

        assert result.success
        assert any("Path not found" in warning for warning in result.warnings)
