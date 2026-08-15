from __future__ import annotations

from pathlib import Path

import pytest
from buvis.pybase.filesystem.atomic_write import atomic_write_bytes, atomic_write_text
from pytest_mock import MockerFixture


class TestAtomicWriteBytes:
    def test_happy_path_writes_data(self, tmp_path: Path) -> None:
        target = tmp_path / "out.bin"
        payload = b"\x00\x01\x02hello\xff"
        atomic_write_bytes(target, payload)
        assert target.read_bytes() == payload

    def test_failure_during_write_leaves_target_untouched(self, tmp_path: Path, mocker: MockerFixture) -> None:
        target = tmp_path / "out.bin"
        target.write_bytes(b"original-content")

        # Force os.replace (the swap) to fail; the target must remain unchanged
        # and no .tmp sibling should be left behind.
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=OSError("simulated swap failure"),
        )
        with pytest.raises(OSError):
            atomic_write_bytes(target, b"new-content")

        assert target.read_bytes() == b"original-content"
        leftover = list(tmp_path.glob(target.name + ".*.tmp"))
        assert leftover == []

    def test_parent_dir_must_exist(self, tmp_path: Path) -> None:
        target = tmp_path / "missing-parent" / "out.bin"
        with pytest.raises(FileNotFoundError):
            atomic_write_bytes(target, b"x")

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.bin"
        target.write_bytes(b"old")
        atomic_write_bytes(target, b"new")
        assert target.read_bytes() == b"new"


class TestAtomicWriteText:
    def test_happy_path_writes_data(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        payload = "hello world"
        atomic_write_text(target, payload)
        assert target.read_text(encoding="utf-8") == payload

    def test_failure_during_write_leaves_target_untouched(self, tmp_path: Path, mocker: MockerFixture) -> None:
        target = tmp_path / "out.txt"
        target.write_text("original-content", encoding="utf-8")

        # Force os.replace (the swap) to fail; the target must remain unchanged
        # and no .tmp sibling should be left behind.
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=OSError("simulated swap failure"),
        )
        with pytest.raises(OSError):
            atomic_write_text(target, "new-content")

        assert target.read_text(encoding="utf-8") == "original-content"
        leftover = list(tmp_path.glob(target.name + ".*.tmp"))
        assert leftover == []

    def test_parent_dir_must_exist(self, tmp_path: Path) -> None:
        target = tmp_path / "missing-parent" / "out.txt"
        with pytest.raises(FileNotFoundError):
            atomic_write_text(target, "x")

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        target.write_text("old", encoding="utf-8")
        atomic_write_text(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_writes_and_reads_back_with_non_default_encoding(self, tmp_path: Path) -> None:
        target = tmp_path / "out-latin1.txt"
        # A string containing a byte value that differs in meaning between
        # utf-8 and latin-1 encodings, to prove the requested encoding is honored.
        payload = "café"
        atomic_write_text(target, payload, encoding="latin-1")
        assert target.read_text(encoding="latin-1") == payload

    def test_new_file_gets_requested_mode(self, tmp_path: Path) -> None:
        target = tmp_path / "out-mode.txt"
        atomic_write_text(target, "data", mode=0o600)
        assert (target.stat().st_mode & 0o777) == 0o600

    def test_new_file_gets_default_mode_when_unspecified(self, tmp_path: Path) -> None:
        target = tmp_path / "out-default-mode.txt"
        atomic_write_text(target, "data")
        assert (target.stat().st_mode & 0o777) == 0o644

    def test_overwrite_preserves_existing_file_permissions(self, tmp_path: Path) -> None:
        target = tmp_path / "out-preserve-mode.txt"
        target.write_text("old", encoding="utf-8")
        target.chmod(0o640)

        # Write with the default mode kwarg; the pre-existing target's own
        # permissions must win over both the tempfile default and `mode`'s default.
        atomic_write_text(target, "new")

        assert target.read_text(encoding="utf-8") == "new"
        assert (target.stat().st_mode & 0o777) == 0o640
