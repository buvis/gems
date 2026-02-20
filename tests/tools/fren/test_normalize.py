from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fren.commands.normalize.normalize import CommandNormalize


class TestNormalizeBasic:
    def test_nfc_normalizes_dirname(self, tmp_path: Path) -> None:
        nfd_dir = tmp_path / "old-name"
        nfd_dir.mkdir()

        with patch(
            "fren.commands.normalize.normalize.unicodedata.normalize",
            side_effect=lambda form, text: "new-name" if text == "old-name" else text,
        ):
            result = CommandNormalize(directory=str(tmp_path)).execute()

        assert not nfd_dir.exists()
        assert (tmp_path / "new-name").exists()
        assert result.output == "Normalized 1 directory name(s)"

    def test_already_nfc_unchanged(self, tmp_path: Path) -> None:
        nfc_dir = tmp_path / "café"
        nfc_dir.mkdir()

        result = CommandNormalize(directory=str(tmp_path)).execute()

        assert nfc_dir.exists()
        assert result.output == "Normalized 0 directory name(s)"

    def test_skips_dot_underscore(self, tmp_path: Path) -> None:
        skipped = tmp_path / "._nfsdata"
        skipped.mkdir()

        result = CommandNormalize(directory=str(tmp_path)).execute()

        assert skipped.exists()
        assert result.output == "Normalized 0 directory name(s)"


class TestNormalizeMerge:
    def test_merges_duplicate_dirs(self, tmp_path: Path) -> None:
        nfd_dir = tmp_path / "nfd-dir"
        nfc_dir = tmp_path / "nfc-dir"
        nfd_dir.mkdir()
        nfc_dir.mkdir()
        (nfd_dir / "nfd.txt").write_text("a")
        (nfc_dir / "nfc.txt").write_text("b")

        with patch(
            "fren.commands.normalize.normalize.unicodedata.normalize",
            side_effect=lambda form, text: "nfc-dir" if text == "nfd-dir" else text,
        ):
            result = CommandNormalize(directory=str(tmp_path)).execute()

        assert result.success
        assert not nfd_dir.exists()
        assert (nfc_dir / "nfd.txt").exists()
        assert (nfc_dir / "nfc.txt").exists()

    def test_merge_collision_warns(self, tmp_path: Path) -> None:
        nfd_dir = tmp_path / "nfd-dir"
        nfc_dir = tmp_path / "nfc-dir"
        nfd_dir.mkdir()
        nfc_dir.mkdir()
        (nfd_dir / "same.txt").write_text("from-nfd")
        (nfc_dir / "same.txt").write_text("from-nfc")

        with patch(
            "fren.commands.normalize.normalize.unicodedata.normalize",
            side_effect=lambda form, text: "nfc-dir" if text == "nfd-dir" else text,
        ):
            result = CommandNormalize(directory=str(tmp_path)).execute()

        assert any("Collision during merge, skipped" in warning for warning in result.warnings)


class TestNormalizeBottomUp:
    def test_deepest_dirs_first(self, tmp_path: Path) -> None:
        parent_nfd = tmp_path / "parent-old"
        child_nfd = parent_nfd / "child-old"
        child_nfd.mkdir(parents=True)
        (child_nfd / "note.txt").write_text("x")

        def fake_normalize(form: str, text: str) -> str:
            if text == "parent-old":
                return "parent-new"
            if text == "child-old":
                return "child-new"
            return text

        with patch("fren.commands.normalize.normalize.unicodedata.normalize", side_effect=fake_normalize):
            result = CommandNormalize(directory=str(tmp_path)).execute()

        parent_nfc = tmp_path / "parent-new"
        child_nfc = parent_nfc / "child-new"
        assert result.success
        assert not result.warnings
        assert (child_nfc / "note.txt").exists()
