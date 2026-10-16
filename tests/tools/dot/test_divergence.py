from __future__ import annotations

from pathlib import Path

from dot.divergence import divergence_dir, pending_patch_warning


class TestDivergenceDir:
    def test_lives_under_local_share_dot(self, tmp_path: Path) -> None:
        assert divergence_dir(tmp_path) == tmp_path / ".local/share/dot/divergence"


class TestPendingPatchWarning:
    def test_missing_dir_reports_nothing(self, tmp_path: Path) -> None:
        assert pending_patch_warning(tmp_path) is None

    def test_one_patch_reports_count_and_dir(self, tmp_path: Path) -> None:
        d = divergence_dir(tmp_path)
        d.mkdir(parents=True)
        (d / "20261016T120000Z.patch").write_bytes(b"x")

        assert pending_patch_warning(tmp_path) == f"1 divergence patch(es) pending in {d}"

    def test_non_patch_files_are_not_counted(self, tmp_path: Path) -> None:
        d = divergence_dir(tmp_path)
        d.mkdir(parents=True)
        (d / "notes.txt").write_text("x")
        (d / "a.patch").write_bytes(b"x")

        assert pending_patch_warning(tmp_path) == f"1 divergence patch(es) pending in {d}"

    def test_deleted_patch_clears_warning(self, tmp_path: Path) -> None:
        d = divergence_dir(tmp_path)
        d.mkdir(parents=True)
        patch = d / "a.patch"
        patch.write_bytes(b"x")
        assert pending_patch_warning(tmp_path) is not None

        patch.unlink()

        assert pending_patch_warning(tmp_path) is None
