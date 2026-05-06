from __future__ import annotations

from pathlib import Path

import pytest
from bim.commands.doc.shared.atomic_write import atomic_write_bytes, atomic_write_text
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
            "bim.commands.doc.shared.atomic_write.os.replace",
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
    def test_happy_path_writes_text(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        atomic_write_text(target, "héllo wörld\n")
        assert target.read_text(encoding="utf-8") == "héllo wörld\n"

    def test_failure_leaves_target_untouched(self, tmp_path: Path, mocker: MockerFixture) -> None:
        target = tmp_path / "out.txt"
        target.write_text("original", encoding="utf-8")
        mocker.patch(
            "bim.commands.doc.shared.atomic_write.os.replace",
            side_effect=OSError("simulated swap failure"),
        )
        with pytest.raises(OSError):
            atomic_write_text(target, "new")
        assert target.read_text(encoding="utf-8") == "original"
        leftover = list(tmp_path.glob(target.name + ".*.tmp"))
        assert leftover == []
