from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bim.shared.article_archive import archive_file_name, archive_original, archive_path, archive_text

NOW = datetime(2026, 11, 9, 13, 49, 25, tzinfo=timezone(timedelta(hours=1)))


class TestArchiveOriginal:
    def test_archive_path_is_year_month00_title(self, tmp_path: Path) -> None:
        root = tmp_path / "articles"

        path = archive_original(root, "Why caches lie", "Body text", "https://example.com/post", NOW)

        assert path == root / "2026" / "20261100" / "Why caches lie.md"
        assert path == archive_path(root, "Why caches lie", NOW)
        assert path.read_text() == "# Why caches lie\n\nBody text\n\n---\n\nSource: https://example.com/post\n"

    def test_without_web_the_source_footer_is_omitted(self, tmp_path: Path) -> None:
        path = archive_original(tmp_path / "articles", "Plain", "Body", "", NOW)

        assert path.read_text() == "# Plain\n\nBody\n"
        assert archive_text("Plain", "Body", "") == "# Plain\n\nBody\n"

    def test_archive_refuses_existing_file(self, tmp_path: Path) -> None:
        first = archive_original(tmp_path / "articles", "Same", "First", "", NOW)

        with pytest.raises(FileExistsError):
            archive_original(tmp_path / "articles", "Same", "Second", "", NOW)

        assert first.read_text() == "# Same\n\nFirst\n"

    def test_missing_parent_of_root_fails_before_writing(self, tmp_path: Path) -> None:
        root = tmp_path / "missing" / "articles"

        with pytest.raises(ValueError, match=f"{root.parent} does not exist; set path_articles"):
            archive_original(root, "T", "Body", "", NOW)

        assert not root.parent.exists()

    def test_write_failure_removes_owned_archive(self, tmp_path: Path, mocker) -> None:
        original_open = Path.open

        def fail_write(path: Path, *args, **kwargs):
            handle = original_open(path, *args, **kwargs)
            wrapped = mocker.MagicMock(wraps=handle)
            wrapped.__enter__.return_value = wrapped
            wrapped.__exit__.side_effect = handle.__exit__

            def partial_write(content: bytes) -> None:
                handle.write(content[:3])
                raise OSError("write failed")

            wrapped.write.side_effect = partial_write
            return wrapped

        mocker.patch.object(Path, "open", autospec=True, side_effect=fail_write)
        with pytest.raises(OSError, match="write failed"):
            archive_original(tmp_path / "articles", "T", "Body", "", NOW)
        assert not archive_path(tmp_path / "articles", "T", NOW).exists()


class TestArchiveFileName:
    def test_archive_name_replaces_path_characters(self) -> None:
        assert archive_file_name("a/b\\c:d\x01e. ") == "a-b-c-d-e"
        assert archive_file_name("Keep Ünïcödé & spaces") == "Keep Ünïcödé & spaces"
        assert archive_file_name(" / ") == "-"

    @pytest.mark.parametrize("title", ["", "...", "   "])
    def test_empty_name_is_rejected(self, title: str) -> None:
        with pytest.raises(ValueError, match="cannot be used as a file name"):
            archive_file_name(title)
