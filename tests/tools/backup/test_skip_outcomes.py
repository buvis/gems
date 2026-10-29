from __future__ import annotations

from pathlib import Path

import pytest

from backup.capabilities.tar_archive import TarArchive
from backup.step_result import StepResult


class TestStepResult:
    @pytest.mark.parametrize("label,message", [("first", "missing source"), ("second", "no selected items")])
    def test_step_result_keeps_positional_fields_and_defaults_to_not_skipped(self, label: str, message: str) -> None:
        result = StepResult(label, True, message, None)
        assert result.label == label
        assert result.success is True
        assert result.message == message
        assert result.archive is None
        assert result.skipped is False
        skipped = StepResult(label, True, message, skipped=True)
        assert skipped.label == label
        assert skipped.message == message
        assert skipped.success is True
        assert skipped.skipped is True


@pytest.mark.parametrize("engine", ["python-tarfile", "system-tar"])
class TestSkippedArchives:
    @pytest.mark.parametrize("dry_run", [False, True])
    @pytest.mark.parametrize("source_state", ["missing", "file"])
    def test_missing_source_skips_but_existing_non_directory_fails(
        self,
        tmp_path: Path,
        engine: str,
        dry_run: bool,
        source_state: str,
    ) -> None:
        source = tmp_path / source_state
        if source_state == "file":
            source.write_text("not a directory", encoding="utf-8")
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"old archive")
        before = out.stat()
        result = next(
            iter(
                TarArchive().run(
                    label="optional",
                    source=str(source),
                    out=str(out),
                    engine=engine,
                    dry_run=dry_run,
                )
            )
        )
        assert result.success is (source_state == "missing")
        assert result.skipped is (source_state == "missing")
        reason = "source not found" if source_state == "missing" else "source is not a directory"
        assert result.message == f"{reason}: {source}"
        assert out.read_bytes() == b"old archive"
        assert out.stat().st_mtime_ns == before.st_mtime_ns
        assert out.stat().st_ino == before.st_ino
        assert sorted(path.name for path in tmp_path.iterdir()) == sorted(
            ["out.tar.gz", "file"] if source_state == "file" else ["out.tar.gz"],
        )

    @pytest.mark.parametrize("dry_run", [False, True])
    @pytest.mark.parametrize("kind", ["absent", "excluded"])
    def test_no_selected_members_skips_and_preserves_existing_output(
        self,
        tmp_path: Path,
        engine: str,
        dry_run: bool,
        kind: str,
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "unselected").write_text("must not leak", encoding="utf-8")
        if kind == "excluded":
            (source / "a").write_text("first", encoding="utf-8")
            (source / "b").write_text("second", encoding="utf-8")
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"preserve previous")
        before = out.stat()
        result = next(
            iter(
                TarArchive().run(
                    label="optional",
                    source=str(source),
                    out=str(out),
                    items=["a", "b"],
                    excludes=["a", "b"],
                    engine=engine,
                    dry_run=dry_run,
                )
            )
        )
        assert result.success is True
        assert result.skipped is True
        assert result.message
        assert out.read_bytes() == b"preserve previous"
        assert out.stat().st_mtime_ns == before.st_mtime_ns
        assert out.stat().st_ino == before.st_ino
        assert sorted(path.name for path in tmp_path.iterdir()) == ["out.tar.gz", "src"]
