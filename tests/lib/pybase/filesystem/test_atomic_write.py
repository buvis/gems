from __future__ import annotations

import os
import tempfile
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

    def test_failure_during_replace_leaves_target_untouched(self, tmp_path: Path, mocker: MockerFixture) -> None:
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

    def test_failure_during_fsync_leaves_target_untouched(self, tmp_path: Path, mocker: MockerFixture) -> None:
        target = tmp_path / "out.bin"
        target.write_bytes(b"original-content")

        # Force a failure during the write/fsync stage (before the replace
        # swap even happens); the target must remain unchanged.
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.fsync",
            side_effect=OSError("simulated write failure"),
        )
        with pytest.raises(OSError):
            atomic_write_bytes(target, b"new-content")

        assert target.read_bytes() == b"original-content"
        leftover = list(tmp_path.glob(target.name + ".*.tmp"))
        assert leftover == []

    def test_temp_file_created_in_target_directory(self, tmp_path: Path, mocker: MockerFixture) -> None:
        target = tmp_path / "out.bin"
        # A temp file on another filesystem would make os.replace raise EXDEV;
        # same-directory placement is what makes the swap atomic.
        replace_spy = mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=os.replace,
        )

        atomic_write_bytes(target, b"data")

        tmp_src = Path(replace_spy.call_args.args[0])
        assert tmp_src.parent == target.parent

    def test_fsync_called_before_replace(self, tmp_path: Path, mocker: MockerFixture) -> None:
        target = tmp_path / "out.bin"
        call_order: list[str] = []
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.fsync",
            side_effect=lambda fd: call_order.append("fsync"),
        )
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=lambda *args, **kwargs: call_order.append("replace"),
        )

        atomic_write_bytes(target, b"data")

        assert call_order == ["fsync", "replace"]

    def test_base_exception_during_replace_still_cleans_up_temp_file(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        target = tmp_path / "out.bin"
        target.write_bytes(b"original-content")

        # KeyboardInterrupt/SystemExit derive from BaseException, not Exception.
        # Cleanup must still run so no orphaned .tmp sibling survives a Ctrl-C.
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=KeyboardInterrupt,
        )
        with pytest.raises(KeyboardInterrupt):
            atomic_write_bytes(target, b"new-content")

        leftover = list(tmp_path.glob(target.name + ".*.tmp"))
        assert leftover == []

    def test_fchmod_failure_closes_descriptor_instead_of_leaking(self, tmp_path: Path, mocker: MockerFixture) -> None:
        target = tmp_path / "out.bin"
        captured_fd: dict[str, int] = {}
        real_mkstemp = tempfile.mkstemp

        def fake_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
            fd, name = real_mkstemp(*args, **kwargs)
            captured_fd["fd"] = fd
            return fd, name

        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.tempfile.mkstemp",
            side_effect=fake_mkstemp,
        )
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.fchmod",
            side_effect=PermissionError("nope"),
        )
        close_spy = mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.close",
            side_effect=os.close,
        )

        with pytest.raises(PermissionError):
            atomic_write_bytes(target, b"data")

        closed_fds = [call.args[0] for call in close_spy.call_args_list]
        assert captured_fd["fd"] in closed_fds

    def test_cleanup_unlink_failure_does_not_mask_original_write_error(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        target = tmp_path / "out.bin"
        target.write_bytes(b"original-content")

        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=OSError("disk full"),
        )
        # Cleanup's own unlink fails with a different error; the caller must
        # still see the original write/replace failure, not this one.
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.unlink",
            side_effect=PermissionError("cleanup denied"),
        )

        with pytest.raises(OSError) as exc_info:
            atomic_write_bytes(target, b"new-content")

        assert str(exc_info.value) == "disk full"

    def test_parent_dir_must_exist(self, tmp_path: Path) -> None:
        target = tmp_path / "missing-parent" / "out.bin"
        with pytest.raises(FileNotFoundError):
            atomic_write_bytes(target, b"x")

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.bin"
        target.write_bytes(b"old")
        atomic_write_bytes(target, b"new")
        assert target.read_bytes() == b"new"

    @pytest.mark.skipif(
        not hasattr(os, "fchmod"),
        reason="fchmod is unavailable here (e.g. Windows); atomic_write skips permission handling.",
    )
    def test_new_file_gets_default_mode(self, tmp_path: Path) -> None:
        target = tmp_path / "out-default-mode.bin"
        atomic_write_bytes(target, b"data")
        assert (target.stat().st_mode & 0o777) == 0o644

    @pytest.mark.skipif(
        not hasattr(os, "fchmod"),
        reason="fchmod is unavailable here (e.g. Windows); atomic_write skips permission handling.",
    )
    def test_overwrite_preserves_existing_file_permissions(self, tmp_path: Path) -> None:
        target = tmp_path / "out-preserve-mode.bin"
        target.write_bytes(b"old")
        target.chmod(0o640)

        # atomic_write_bytes has no mode kwarg; the pre-existing target's own
        # permissions must still win over the tempfile/default mode.
        atomic_write_bytes(target, b"new")

        assert target.read_bytes() == b"new"
        assert (target.stat().st_mode & 0o777) == 0o640


class TestAtomicWriteText:
    def test_happy_path_writes_data(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        payload = "hello world"
        atomic_write_text(target, payload)
        assert target.read_text(encoding="utf-8") == payload

    def test_failure_during_replace_leaves_target_untouched(self, tmp_path: Path, mocker: MockerFixture) -> None:
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

    def test_base_exception_during_replace_still_cleans_up_temp_file(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        target = tmp_path / "out.txt"
        target.write_text("original-content", encoding="utf-8")

        # KeyboardInterrupt/SystemExit derive from BaseException, not Exception.
        # Cleanup must still run so no orphaned .tmp sibling survives a Ctrl-C.
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=KeyboardInterrupt,
        )
        with pytest.raises(KeyboardInterrupt):
            atomic_write_text(target, "new-content")

        leftover = list(tmp_path.glob(target.name + ".*.tmp"))
        assert leftover == []

    def test_fchmod_failure_closes_descriptor_instead_of_leaking(self, tmp_path: Path, mocker: MockerFixture) -> None:
        target = tmp_path / "out.txt"
        captured_fd: dict[str, int] = {}
        real_mkstemp = tempfile.mkstemp

        def fake_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
            fd, name = real_mkstemp(*args, **kwargs)
            captured_fd["fd"] = fd
            return fd, name

        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.tempfile.mkstemp",
            side_effect=fake_mkstemp,
        )
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.fchmod",
            side_effect=PermissionError("nope"),
        )
        close_spy = mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.close",
            side_effect=os.close,
        )

        with pytest.raises(PermissionError):
            atomic_write_text(target, "data")

        closed_fds = [call.args[0] for call in close_spy.call_args_list]
        assert captured_fd["fd"] in closed_fds

    def test_cleanup_unlink_failure_does_not_mask_original_write_error(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        target = tmp_path / "out.txt"
        target.write_text("original-content", encoding="utf-8")

        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=OSError("disk full"),
        )
        # Cleanup's own unlink fails with a different error; the caller must
        # still see the original write/replace failure, not this one.
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.unlink",
            side_effect=PermissionError("cleanup denied"),
        )

        with pytest.raises(OSError) as exc_info:
            atomic_write_text(target, "new-content")

        assert str(exc_info.value) == "disk full"

    def test_parent_dir_must_exist(self, tmp_path: Path) -> None:
        target = tmp_path / "missing-parent" / "out.txt"
        with pytest.raises(FileNotFoundError):
            atomic_write_text(target, "x")

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        target.write_text("old", encoding="utf-8")
        atomic_write_text(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_writing_through_a_symlink_replaces_the_link_not_the_target(self, tmp_path: Path) -> None:
        real_target = tmp_path / "real.txt"
        real_target.write_text("original-content", encoding="utf-8")
        link_path = tmp_path / "link.txt"
        link_path.symlink_to(real_target)

        atomic_write_text(link_path, "new-content")

        # os.replace swaps a new inode into the link's own path rather than
        # writing through it: the symlink becomes a plain file holding the
        # new content, and the real target it used to point at is untouched.
        assert not link_path.is_symlink()
        assert link_path.read_text(encoding="utf-8") == "new-content"
        assert real_target.read_text(encoding="utf-8") == "original-content"

    def test_writes_and_reads_back_with_non_default_encoding(self, tmp_path: Path) -> None:
        target = tmp_path / "out-latin1.txt"
        # A string containing a byte value that differs in meaning between
        # utf-8 and latin-1 encodings, to prove the requested encoding is honored.
        payload = "café"
        atomic_write_text(target, payload, encoding="latin-1")
        assert target.read_text(encoding="latin-1") == payload

    @pytest.mark.skipif(
        not hasattr(os, "fchmod"),
        reason="fchmod is unavailable here (e.g. Windows); atomic_write skips permission handling.",
    )
    def test_new_file_gets_requested_mode(self, tmp_path: Path) -> None:
        target = tmp_path / "out-mode.txt"
        atomic_write_text(target, "data", mode=0o600)
        assert (target.stat().st_mode & 0o777) == 0o600

    @pytest.mark.skipif(
        not hasattr(os, "fchmod"),
        reason="fchmod is unavailable here (e.g. Windows); atomic_write skips permission handling.",
    )
    def test_new_file_gets_default_mode_when_unspecified(self, tmp_path: Path) -> None:
        target = tmp_path / "out-default-mode.txt"
        atomic_write_text(target, "data")
        assert (target.stat().st_mode & 0o777) == 0o644

    @pytest.mark.skipif(
        not hasattr(os, "fchmod"),
        reason="fchmod is unavailable here (e.g. Windows); atomic_write skips permission handling.",
    )
    def test_overwrite_preserves_existing_file_permissions(self, tmp_path: Path) -> None:
        target = tmp_path / "out-preserve-mode.txt"
        target.write_text("old", encoding="utf-8")
        target.chmod(0o640)

        # Write with the default mode kwarg; the pre-existing target's own
        # permissions must win over both the tempfile default and `mode`'s default.
        atomic_write_text(target, "new")

        assert target.read_text(encoding="utf-8") == "new"
        assert (target.stat().st_mode & 0o777) == 0o640
