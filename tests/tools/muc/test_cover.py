from __future__ import annotations

import os
from unittest.mock import patch

from muc.commands.cover.cover import CommandCover


class TestCommandCover:
    @staticmethod
    def _touch(path, mtime: float | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        if mtime is not None:
            os.utime(path, (mtime, mtime))

    def test_no_cover_files(self, tmp_path) -> None:
        result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert result.output == "No duplicate covers found"
        assert result.warnings == []

    def test_single_cover_file(self, tmp_path) -> None:
        cover = tmp_path / "cover.jpg"
        self._touch(cover)

        result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert result.output == "No duplicate covers found"
        assert cover.exists()

    def test_multiple_covers_keeps_newest(self, tmp_path) -> None:
        older = tmp_path / "cover.jpg"
        newer = tmp_path / "cover.png"
        self._touch(older, mtime=100.0)
        self._touch(newer, mtime=200.0)

        result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert result.output == "Cleaned 1 directories, removed 1 files"
        assert not older.exists()
        assert newer.exists()

    def test_equal_mtime_tiebreak(self, tmp_path) -> None:
        first = tmp_path / "cover.jpg"
        second = tmp_path / "Cover.PNG"
        self._touch(first, mtime=300.0)
        self._touch(second, mtime=300.0)

        result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert first.exists()
        assert not second.exists()

    def test_case_insensitive_matching(self, tmp_path) -> None:
        older = tmp_path / "Cover.JPG"
        newer = tmp_path / "cover.png"
        self._touch(older, mtime=100.0)
        self._touch(newer, mtime=200.0)

        result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert not older.exists()
        assert newer.exists()

    def test_renames_survivor_to_lowercase(self, tmp_path) -> None:
        older = tmp_path / "cover.jpg"
        survivor = tmp_path / "Cover.PNG"
        renamed = tmp_path / "cover.png"
        self._touch(older, mtime=100.0)
        self._touch(survivor, mtime=200.0)

        result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert not older.exists()
        assert renamed.exists()
        assert "cover.png" in {path.name for path in tmp_path.iterdir()}

    def test_nested_dirs_independent(self, tmp_path) -> None:
        one_old = tmp_path / "album1" / "cover.jpg"
        one_new = tmp_path / "album1" / "cover.png"
        two_old = tmp_path / "album2" / "cover.jpeg"
        two_new = tmp_path / "album2" / "cover.jpg"
        self._touch(one_old, mtime=100.0)
        self._touch(one_new, mtime=200.0)
        self._touch(two_old, mtime=100.0)
        self._touch(two_new, mtime=200.0)

        result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert result.output == "Cleaned 2 directories, removed 2 files"
        assert not one_old.exists()
        assert one_new.exists()
        assert not two_old.exists()
        assert two_new.exists()

    def test_root_dir_scanned(self, tmp_path) -> None:
        old_cover = tmp_path / "cover.jpg"
        new_cover = tmp_path / "cover.png"
        self._touch(old_cover, mtime=100.0)
        self._touch(new_cover, mtime=200.0)

        result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert not old_cover.exists()
        assert new_cover.exists()

    def test_skips_symlinks(self, tmp_path) -> None:
        real_cover = tmp_path / "cover.jpg"
        symlink_cover = tmp_path / "cover.png"
        target = tmp_path / "target.png"
        self._touch(real_cover)
        self._touch(target)
        symlink_cover.symlink_to(target)

        result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert result.output == "No duplicate covers found"
        assert real_cover.exists()
        assert symlink_cover.is_symlink()

    def test_skips_non_image_extensions(self, tmp_path) -> None:
        text_cover = tmp_path / "cover.txt"
        bmp_cover = tmp_path / "cover.bmp"
        self._touch(text_cover)
        self._touch(bmp_cover)

        result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert result.output == "No duplicate covers found"
        assert text_cover.exists()
        assert bmp_cover.exists()


class TestCommandCoverErrors:
    @staticmethod
    def _touch(path, mtime: float | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        if mtime is not None:
            os.utime(path, (mtime, mtime))

    def test_iterdir_oserror_warns(self, tmp_path) -> None:
        sub = tmp_path / "album"
        sub.mkdir()
        self._touch(sub / "cover.jpg")
        self._touch(sub / "cover.png")

        original_iterdir = type(tmp_path).iterdir

        def broken_iterdir(self_path):
            if self_path == sub:
                raise OSError("permission denied")
            return original_iterdir(self_path)

        with patch.object(type(tmp_path), "iterdir", broken_iterdir):
            result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert any("Failed to inspect directory" in w for w in result.warnings)

    def test_stat_oserror_warns(self, tmp_path) -> None:
        (tmp_path / "cover.jpg").touch()
        (tmp_path / "cover.png").touch()

        # Patch stat to always raise for cover files, but also patch is_file
        # and is_symlink to bypass their internal stat calls. This avoids
        # depending on pathlib internals (call counts vary across versions).
        original_stat = type(tmp_path).stat
        original_is_file = type(tmp_path).is_file
        original_is_dir = type(tmp_path).is_dir
        original_is_symlink = type(tmp_path).is_symlink

        def _is_cover(p):
            return p.stem.lower() == "cover" and p.suffix.lower() in {".jpg", ".jpeg", ".png"}

        def broken_stat(self_path, *args, **kwargs):
            if _is_cover(self_path):
                raise OSError("stat failed")
            return original_stat(self_path, *args, **kwargs)

        def force_is_file(self_path):
            return True if _is_cover(self_path) else original_is_file(self_path)

        def force_not_dir(self_path):
            return False if _is_cover(self_path) else original_is_dir(self_path)

        def force_not_symlink(self_path):
            return False if _is_cover(self_path) else original_is_symlink(self_path)

        with (
            patch.object(type(tmp_path), "stat", broken_stat),
            patch.object(type(tmp_path), "is_file", force_is_file),
            patch.object(type(tmp_path), "is_dir", force_not_dir),
            patch.object(type(tmp_path), "is_symlink", force_not_symlink),
        ):
            result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert any("Failed to inspect cover files" in w for w in result.warnings)

    def test_unlink_oserror_warns(self, tmp_path) -> None:
        self._touch(tmp_path / "cover.jpg", mtime=100.0)
        self._touch(tmp_path / "cover.png", mtime=200.0)

        with patch("pathlib.Path.unlink", side_effect=OSError("delete failed")):
            result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert any("Failed to delete file" in w for w in result.warnings)

    def test_rename_oserror_warns(self, tmp_path) -> None:
        self._touch(tmp_path / "cover.jpg", mtime=100.0)
        self._touch(tmp_path / "Cover.PNG", mtime=200.0)

        with patch("pathlib.Path.rename", side_effect=OSError("rename failed")):
            result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert any("Failed to rename file" in w for w in result.warnings)

    def test_three_covers_removes_two(self, tmp_path) -> None:
        self._touch(tmp_path / "cover.jpg", mtime=100.0)
        self._touch(tmp_path / "cover.png", mtime=200.0)
        self._touch(tmp_path / "cover.jpeg", mtime=300.0)

        result = CommandCover(tmp_path).execute()

        assert result.success is True
        assert result.output == "Cleaned 1 directories, removed 2 files"
        assert not (tmp_path / "cover.jpg").exists()
        assert not (tmp_path / "cover.png").exists()
        assert (tmp_path / "cover.jpeg").exists()
