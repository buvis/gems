from __future__ import annotations

import os
import subprocess
import tarfile
import threading
from pathlib import Path

import pytest

from backup.capabilities import tar_archive
from backup.capabilities.tar_archive import TarArchive, _write_archive
from backup.step_result import ProgressEvent


class TestStrengthenedEngineProgress:
    def test_input_bytes_uses_member_size_before_add_changes_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = tmp_path / "payload"
        payload.write_bytes(b"original")
        original_add = tarfile.TarFile.add

        def add_then_change(archive: tarfile.TarFile, name: str, *args: object, **kwargs: object) -> None:
            original_add(archive, name, *args, **kwargs)
            Path(name).write_bytes(b"changed source with a different size")

        monkeypatch.setattr(tarfile.TarFile, "add", add_then_change)
        counts: list[int] = []
        out = tmp_path / "out.tar.gz"
        _write_archive(out, tmp_path, [payload], on_bytes=counts.append)
        assert counts == [len(b"original")]
        with tarfile.open(out) as archive:
            member = archive.getmember("payload")
            extracted = archive.extractfile(member)
            assert extracted is not None
            assert extracted.read() == b"original"

    @pytest.mark.parametrize("items", [None, ["payload"]])
    def test_engine_scanning_is_delivered_before_selection_or_tree_walk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, items: list[str] | None
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "payload").write_bytes(b"input")
        events: list[ProgressEvent] = []
        boundary_events: list[list[ProgressEvent]] = []
        walk_name = "_walk_tree" if items is None else "_select_items"
        original_walk = getattr(tar_archive, walk_name)

        def walk_after_scanning(*args: object, **kwargs: object) -> object:
            boundary_events.append(events.copy())
            return original_walk(*args, **kwargs)

        monkeypatch.setattr(tar_archive, walk_name, walk_after_scanning)
        selected: dict[str, object] = {} if items is None else {"items": items}
        result = next(
            TarArchive().run(
                label="ordered",
                source=str(source),
                out=str(tmp_path / "out.tar.gz"),
                engine="python-tarfile",
                progress=events.append,
                **selected,
            )
        )
        assert result.success is True
        assert boundary_events == [[ProgressEvent("ordered", "scanning", None, None)]]

    def test_input_bytes_failed_stream_close_never_finalizes_or_publishes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"previous archive")
        original_close = tarfile.TarFile.close

        def fail_close(archive: tarfile.TarFile) -> None:
            was_closed = archive.closed
            original_close(archive)
            if not was_closed:
                raise OSError("stream close failed")

        monkeypatch.setattr(tarfile.TarFile, "close", fail_close)
        counts: list[int] = []
        finalized: list[bool] = []
        with pytest.raises(OSError, match="stream close failed"):
            _write_archive(out, tmp_path, [], on_bytes=counts.append, on_finalize=lambda: finalized.append(True))
        assert counts == []
        assert finalized == []
        assert out.read_bytes() == b"previous archive"
        assert list(tmp_path.iterdir()) == [out]

    @pytest.mark.parametrize("engine", ["python-tarfile", "system-tar"])
    def test_engine_syncs_closed_archive_before_atomic_publication(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, engine: str
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "payload").write_bytes(b"input")
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"previous archive")
        stages: list[str] = []
        original_sync, original_replace = os.fsync, os.replace

        def sync(fd: int) -> None:
            original_sync(fd)
            stages.append("synced")

        def publish(*args: object, **kwargs: object) -> None:
            stages.append("published")
            original_replace(*args, **kwargs)

        def progress(event: ProgressEvent) -> None:
            if event.phase == "finalizing":
                stages.append("closed")
                assert out.read_bytes() == b"previous archive"

        monkeypatch.setattr(os, "fsync", sync)
        monkeypatch.setattr(os, "replace", publish)
        result = next(
            TarArchive().run(label="durable", source=str(source), out=str(out), engine=engine, progress=progress)
        )
        assert result.success is True
        assert stages == ["closed", "synced", "published"]
        with tarfile.open(out) as archive:
            assert any(member.isfile() for member in archive.getmembers())

    def test_engine_cancellation_without_callback_exception_preserves_output_and_cleans_temp(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        payload = source / "payload"
        payload.write_bytes(b"input")
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"previous archive")
        cancel = threading.Event()
        counts: list[int] = []

        def cancel_after_member(done: int) -> None:
            counts.append(done)
            cancel.set()

        with pytest.raises(tar_archive.ArchiveCancelled):
            _write_archive(out, source, [payload], cancel=cancel, on_bytes=cancel_after_member)
        assert counts == [5]
        assert out.read_bytes() == b"previous archive"
        assert sorted(path.name for path in tmp_path.iterdir()) == ["out.tar.gz", "src"]

    def test_engine_system_tar_completes_subprocess_without_python_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "payload").write_bytes(b"system input")
        out = tmp_path / "out.tar.gz"
        processes: list[subprocess.Popen[bytes]] = []
        original_popen, original_open = subprocess.Popen, tarfile.open

        def launch(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
            process = original_popen(*args, **kwargs)
            processes.append(process)
            return process

        def open_without_python_writer(*args: object, **kwargs: object) -> tarfile.TarFile:
            assert not str(kwargs.get("mode", "r")).startswith("w"), "unexpected Python fallback"
            return original_open(*args, **kwargs)

        monkeypatch.setattr(subprocess, "Popen", launch)
        monkeypatch.setattr(tarfile, "open", open_without_python_writer)
        events: list[ProgressEvent] = []
        result = next(
            TarArchive().run(
                label="system", source=str(source), out=str(out), engine="system-tar", progress=events.append
            )
        )
        assert result.success is True
        assert "used python engine" not in result.message
        assert [process.returncode for process in processes] == [0]
        assert events[-1] == ProgressEvent("system", "finalizing", None, len(b"system input"))
        with tarfile.open(out) as archive:
            member = next(member for member in archive.getmembers() if member.isfile())
            extracted = archive.extractfile(member)
            assert extracted is not None
            assert extracted.read() == b"system input"

    @pytest.mark.parametrize("exception", [KeyboardInterrupt(), SystemExit(7)])
    def test_engine_system_finalizing_interruption_is_not_swallowed_or_published(
        self, tmp_path: Path, exception: BaseException
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "payload").write_bytes(b"input")
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"previous archive")
        events: list[ProgressEvent] = []

        def interrupt_finalizing(event: ProgressEvent) -> None:
            events.append(event)
            if event.phase == "finalizing":
                raise exception

        with pytest.raises(type(exception)) as caught:
            next(
                TarArchive().run(
                    label="interrupt",
                    source=str(source),
                    out=str(out),
                    engine="system-tar",
                    progress=interrupt_finalizing,
                )
            )
        assert caught.value is exception
        assert events[-1] == ProgressEvent("interrupt", "finalizing", None, 5)
        assert out.read_bytes() == b"previous archive"
        assert sorted(path.name for path in tmp_path.iterdir()) == ["out.tar.gz", "src"]
