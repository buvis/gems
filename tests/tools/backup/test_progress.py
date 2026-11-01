from __future__ import annotations

import os
import tarfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal, get_type_hints

import pytest

from backup.capabilities import tar_archive
from backup.capabilities.tar_archive import TarArchive, _write_archive
from backup.step_result import ProgressEvent
from tests.tools.backup.progress_engine_cases import TestStrengthenedEngineProgress as TestStrengthenedEngineProgress


class ProgressConsumerError(Exception):
    """An ordinary consumer exception outside common built-in classes."""


class TestProgressEventRecord:
    def test_event_record_has_exact_named_tuple_fields_types_and_no_defaults(self) -> None:
        assert ProgressEvent.__bases__ == (tuple,)
        assert ProgressEvent._fields == ("label", "phase", "done_bytes", "total_bytes")
        assert ProgressEvent._field_defaults == {}
        assert get_type_hints(ProgressEvent) == {
            "label": str,
            "phase": Literal["scanning", "archiving", "finalizing"],
            "done_bytes": int | None,
            "total_bytes": int | None,
        }

    @pytest.mark.parametrize(
        "label,phase,done_bytes,total_bytes",
        [
            ("documents", "scanning", None, None),
            ("documents-old", "archiving", 37, 101),
            ("", "finalizing", 0, 0),
            ("photos", "archiving", 2**40, 2**41),
            ("photos", "scanning", 0, None),
            ("documents", "finalizing", None, 101),
            ("Příliš žluťoučký 🗃️", "archiving", 2**63, 2**80),
        ],
    )
    def test_event_record_preserves_each_positional_field_and_byte_value(
        self,
        label: str,
        phase: Literal["scanning", "archiving", "finalizing"],
        done_bytes: int | None,
        total_bytes: int | None,
    ) -> None:
        event = ProgressEvent(label, phase, done_bytes, total_bytes)
        assert event.label == label
        assert event.phase == phase
        assert event.done_bytes == done_bytes
        assert event.total_bytes == total_bytes
        assert event[0] == event.label
        assert event[1] == event.phase
        assert event[2] == event.done_bytes
        assert event[3] == event.total_bytes
        assert tuple(event) == (label, phase, done_bytes, total_bytes)
        assert event == ProgressEvent(
            total_bytes=total_bytes,
            done_bytes=done_bytes,
            phase=phase,
            label=label,
        )
        assert event == ProgressEvent(label, phase=phase, done_bytes=done_bytes, total_bytes=total_bytes)

    @pytest.mark.parametrize("field", ["label", "phase", "done_bytes", "total_bytes"])
    def test_event_record_rejects_field_mutation(self, field: str) -> None:
        event = ProgressEvent("documents", "archiving", 37, 101)
        assert not hasattr(event, "__dict__")
        with pytest.raises(AttributeError):
            setattr(event, field, None)
        assert tuple(event) == ("documents", "archiving", 37, 101)

    @pytest.mark.parametrize(
        "args",
        [(), ("documents",), ("documents", "scanning"), ("documents", "scanning", None)],
    )
    def test_event_record_requires_all_four_arguments(self, args: tuple[object, ...]) -> None:
        with pytest.raises(TypeError):
            ProgressEvent(*args)

    def test_event_record_distinguishes_similar_labels_and_each_field(self) -> None:
        event = ProgressEvent("documents", "archiving", 37, 101)
        assert event != ProgressEvent("documents-old", "archiving", 37, 101)
        assert event != ProgressEvent("documents", "finalizing", 37, 101)
        assert event != ProgressEvent("documents", "archiving", 38, 101)
        assert event != ProgressEvent("documents", "archiving", 37, 102)

    def test_event_record_crosses_worker_thread_without_sharing_mutable_call_state(self) -> None:
        original = ProgressEvent("documents", "scanning", None, None)

        def update_in_worker(event: ProgressEvent) -> tuple[ProgressEvent, ProgressEvent]:
            updated = event._replace(phase="archiving", done_bytes=37, total_bytes=101)
            other = ProgressEvent("photos", "finalizing", 0, 0)
            return updated, other

        with ThreadPoolExecutor(max_workers=1) as executor:
            updated, other = executor.submit(update_in_worker, original).result(timeout=5)
        assert tuple(original) == ("documents", "scanning", None, None)
        assert (original.label, original.phase, original.done_bytes, original.total_bytes) == (
            "documents",
            "scanning",
            None,
            None,
        )
        assert (other.label, other.phase, other.done_bytes, other.total_bytes) == ("photos", "finalizing", 0, 0)
        assert isinstance(updated, ProgressEvent)
        assert tuple(updated) == ("documents", "archiving", 37, 101)
        replacements = [
            (original._replace(label="photos"), ("photos", "scanning", None, None)),
            (original._replace(phase="finalizing"), ("documents", "finalizing", None, None)),
            (original._replace(done_bytes=37), ("documents", "scanning", 37, None)),
            (original._replace(total_bytes=101), ("documents", "scanning", None, 101)),
            (updated._replace(done_bytes=None), ("documents", "archiving", None, 101)),
            (updated._replace(total_bytes=None), ("documents", "archiving", 37, None)),
        ]
        for replacement, expected in replacements:
            assert isinstance(replacement, ProgressEvent)
            assert (
                replacement.label,
                replacement.phase,
                replacement.done_bytes,
                replacement.total_bytes,
            ) == expected
            assert tuple(replacement) == expected


def _create_selected_input_source(tmp_path: Path, sizes: list[int]) -> Path:
    source = tmp_path / "src"
    source.mkdir()
    for name, size in zip(["a-old", "b"], sizes, strict=True):
        (source / name).write_bytes(b"x" * size)
    (source / "a").write_bytes(b"excluded" * 13)
    return source


class TestArchiveEngineProgress:
    @pytest.mark.parametrize("engine", ["python-tarfile", "system-tar"])
    @pytest.mark.parametrize("label,sizes", [("docs", [7, 19]), ("docs-old", [11, 31])])
    def test_engine_reports_ordered_phases_and_selected_input_bytes_before_publication(
        self,
        tmp_path: Path,
        engine: str,
        label: str,
        sizes: list[int],
    ) -> None:
        source = _create_selected_input_source(tmp_path, sizes)
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"previous archive")
        events: list[ProgressEvent] = []
        finalizing_output: list[bytes] = []

        def progress(event: ProgressEvent) -> None:
            events.append(event)
            if event.phase == "finalizing":
                finalizing_output.append(out.read_bytes())

        result = next(
            iter(
                TarArchive().run(
                    label=label,
                    source=str(source),
                    out=str(out),
                    engine=engine,
                    items=["a", "a-old", "b"],
                    excludes=["a"],
                    progress=progress,
                )
            )
        )
        assert result.success is True
        assert result.out_path == str(out)
        assert finalizing_output == [b"previous archive"]
        total = sum(sizes)
        done = total if engine == "python-tarfile" else None
        assert events[0] == ProgressEvent(label, "scanning", None, None)
        assert events[1] == ProgressEvent(label, "archiving", 0 if done is not None else None, total)
        assert events[-1] == ProgressEvent(label, "finalizing", done, total)
        assert all(event.label == label for event in events)
        assert all(event.total_bytes == total for event in events[1:])
        assert all(event.phase == "archiving" for event in events[1:-1])
        if engine == "system-tar":
            assert all(event.done_bytes is None for event in events)
        else:
            assert events[-2] == ProgressEvent(label, "archiving", total, total)
        with tarfile.open(out) as archive:
            assert {Path(member.name).name for member in archive.getmembers() if member.isfile()} == {"a-old", "b"}
        assert out.stat().st_mode & 0o777 == 0o600

    @pytest.mark.parametrize("sizes", [[3, 7, 11, 17], [5, 13, 19, 23]])
    def test_engine_throttles_at_two_tenths_and_flushes_short_final_count(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        sizes: list[int],
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        names = ["a", "b", "c", "d"]
        for name, size in zip(names, sizes, strict=True):
            (source / name).write_bytes(b"x" * size)
        clock = [0.0]
        moments = dict(zip(names, [0.199, 0.2, 0.399, 0.3999], strict=True))
        original_add = tarfile.TarFile.add

        def add_with_clock(archive: tarfile.TarFile, name: str, *args: object, **kwargs: object) -> None:
            original_add(archive, name, *args, **kwargs)
            clock[0] = moments[Path(name).name]

        monkeypatch.setattr(time, "monotonic", lambda: clock[0])
        monkeypatch.setattr(tarfile.TarFile, "add", add_with_clock)
        events: list[ProgressEvent] = []
        result = next(
            iter(
                TarArchive().run(
                    label="timed",
                    source=str(source),
                    out=str(tmp_path / "timed.tar.gz"),
                    engine="python-tarfile",
                    items=names,
                    progress=events.append,
                )
            )
        )
        assert result.success is True
        total = sum(sizes)
        assert events == [
            ProgressEvent("timed", "scanning", None, None),
            ProgressEvent("timed", "archiving", 0, total),
            ProgressEvent("timed", "archiving", sum(sizes[:2]), total),
            ProgressEvent("timed", "archiving", total, total),
            ProgressEvent("timed", "finalizing", total, total),
        ]

    @pytest.mark.parametrize("label,size", [("first", 7), ("first-old", 29)])
    def test_engine_short_archive_flushes_without_waiting_or_duplicate_final_count(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        label: str,
        size: int,
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "payload").write_bytes(b"x" * size)
        monkeypatch.setattr(time, "monotonic", lambda: 42.0)
        events: list[ProgressEvent] = []
        result = next(
            iter(
                TarArchive().run(
                    label=label,
                    source=str(source),
                    out=str(tmp_path / "out.tar.gz"),
                    engine="python-tarfile",
                    progress=events.append,
                )
            )
        )
        assert result.success is True
        assert events == [
            ProgressEvent(label, "scanning", None, None),
            ProgressEvent(label, "archiving", 0, size),
            ProgressEvent(label, "archiving", size, size),
            ProgressEvent(label, "finalizing", size, size),
        ]

    @pytest.mark.parametrize("engine", ["python-tarfile", "system-tar"])
    @pytest.mark.parametrize("items", [None, ["a", "b"]])
    def test_engine_direct_dry_run_never_calls_progress(
        self,
        tmp_path: Path,
        engine: str,
        items: list[str] | None,
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "a").write_bytes(b"first")
        (source / "b").write_bytes(b"second payload")
        out = tmp_path / "out.tar.gz"
        events: list[ProgressEvent] = []
        selected: dict[str, object] = {} if items is None else {"items": items}
        result = next(
            iter(
                TarArchive().run(
                    label="preview",
                    source=str(source),
                    out=str(out),
                    engine=engine,
                    **selected,
                    dry_run=True,
                    progress=events.append,
                )
            )
        )
        assert result.success is True
        assert events == []
        assert not out.exists()

    @pytest.mark.parametrize("source_state", ["missing", "file"])
    def test_engine_unwalkable_source_emits_no_fabricated_activity(
        self,
        tmp_path: Path,
        source_state: str,
    ) -> None:
        source = tmp_path / source_state
        if source_state == "file":
            source.write_bytes(b"not a directory")
        events: list[ProgressEvent] = []
        out = tmp_path / "out.tar.gz"
        result = next(
            iter(
                TarArchive().run(
                    label="unwalkable",
                    source=str(source),
                    out=str(out),
                    engine="python-tarfile",
                    progress=events.append,
                )
            )
        )
        assert result.success is (source_state == "missing")
        assert result.skipped is (source_state == "missing")
        assert events == []
        assert not out.exists()

    def test_engine_selection_skip_can_end_after_scanning(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "a-old").write_bytes(b"near miss")
        (source / "b-old").write_bytes(b"another near miss")
        events: list[ProgressEvent] = []
        out = tmp_path / "out.tar.gz"
        result = next(
            iter(
                TarArchive().run(
                    label="empty",
                    source=str(source),
                    out=str(out),
                    items=["a", "b"],
                    engine="python-tarfile",
                    progress=events.append,
                )
            )
        )
        assert result.success is True
        assert result.skipped is True
        assert events == [ProgressEvent("empty", "scanning", None, None)]
        assert not out.exists()

    def test_engine_unavailable_system_tar_falls_back_with_activity_only_progress(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        payload = b"real fallback archive payload"
        (source / "payload").write_bytes(payload)
        out = tmp_path / "fallback.tar.gz"
        events: list[ProgressEvent] = []
        monkeypatch.setenv("PATH", "")
        result = next(
            iter(
                TarArchive().run(
                    label="fallback",
                    source=str(source),
                    out=str(out),
                    engine="system-tar",
                    progress=events.append,
                )
            )
        )
        assert result.success is True
        assert result.out_path == str(out)
        assert "used python engine" in result.message
        assert events == [
            ProgressEvent("fallback", "scanning", None, None),
            ProgressEvent("fallback", "archiving", None, len(payload)),
            ProgressEvent("fallback", "finalizing", None, len(payload)),
        ]
        with tarfile.open(out) as archive:
            members = [member for member in archive.getmembers() if member.isfile()]
            assert len(members) == 1
            assert Path(members[0].name).name == "payload"
            extracted = archive.extractfile(members[0])
            assert extracted is not None
            assert extracted.read() == payload

    @pytest.mark.parametrize("engine", ["python-tarfile", "system-tar"])
    def test_engine_empty_source_reports_zero_total_and_finalizes_real_archive(
        self,
        tmp_path: Path,
        engine: str,
    ) -> None:
        source = tmp_path / "empty"
        source.mkdir()
        out = tmp_path / "empty.tar.gz"
        events: list[ProgressEvent] = []
        result = next(
            iter(
                TarArchive().run(
                    label="empty",
                    source=str(source),
                    out=str(out),
                    engine=engine,
                    progress=events.append,
                )
            )
        )
        assert result.success is True
        assert result.out_path == str(out)
        done = 0 if engine == "python-tarfile" else None
        assert events == [
            ProgressEvent("empty", "scanning", None, None),
            ProgressEvent("empty", "archiving", done, 0),
            ProgressEvent("empty", "finalizing", done, 0),
        ]
        with tarfile.open(out) as archive:
            assert not any(member.isfile() for member in archive.getmembers())


class TestArchiveInputBytes:
    @pytest.mark.parametrize("fixture_kind", ["incompressible", "compressible"])
    def test_percent_uses_input_bytes_not_output_size(self, tmp_path: Path, fixture_kind: str) -> None:
        source = tmp_path / "src"
        source.mkdir()
        sizes = [256 * 1024, 8192]
        payloads = {
            name: os.urandom(size) if fixture_kind == "incompressible" else b"x" * size
            for name, size in zip(["a", "b"], sizes, strict=True)
        }
        for name, payload in payloads.items():
            (source / name).write_bytes(payload)
        total = sum((source / name).stat().st_size for name in payloads)
        out = tmp_path / "out.tar.gz"
        events: list[ProgressEvent] = []
        result = next(
            iter(
                TarArchive().run(
                    label=fixture_kind,
                    source=str(source),
                    out=str(out),
                    engine="python-tarfile",
                    progress=events.append,
                )
            )
        )
        assert result.success is True
        assert out.stat().st_size != total
        if fixture_kind == "compressible":
            assert out.stat().st_size < total // 2
        else:
            assert out.stat().st_size > total * 0.9
        assert events[1] == ProgressEvent(fixture_kind, "archiving", 0, total)
        assert all(event.total_bytes == total for event in events[1:])
        assert events[-2:] == [
            ProgressEvent(fixture_kind, "archiving", total, total),
            ProgressEvent(fixture_kind, "finalizing", total, total),
        ]
        with tarfile.open(out) as archive:
            members = [member for member in archive.getmembers() if member.isfile()]
            assert {Path(member.name).name for member in members} == set(payloads)
            assert sum(member.size for member in members) == total
            for member in members:
                extracted = archive.extractfile(member)
                assert extracted is not None
                assert extracted.read() == payloads[Path(member.name).name]

    @pytest.mark.parametrize("sizes", [[7, 19], [13, 31]])
    def test_input_bytes_counts_regular_paths_and_hardlinks_but_not_directories_or_symlinks(
        self,
        tmp_path: Path,
        sizes: list[int],
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        first = source / "a"
        second = source / "a-old"
        first.write_bytes(b"x" * sizes[0])
        second.write_bytes(b"y" * sizes[1])
        hardlink = source / "hardlink"
        os.link(first, hardlink)
        directory = source / "directory"
        directory.mkdir()
        (directory / "not-selected").write_bytes(b"must not recurse")
        symlink = source / "symlink"
        symlink.symlink_to(second)
        broken = source / "broken"
        broken.symlink_to(source / "absent")
        counts: list[int] = []
        finalized: list[bool] = []
        out = tmp_path / "out.tar.gz"
        files = [first, directory, symlink, broken, second, hardlink]
        _write_archive(out, source, files, on_bytes=counts.append, on_finalize=lambda: finalized.append(True))
        assert counts == [sizes[0], sizes[0], sizes[0], sizes[0], sum(sizes), sum(sizes) + sizes[0]]
        assert finalized == [True]
        with tarfile.open(out) as archive:
            members = {Path(member.name).name: member for member in archive.getmembers()}
        assert set(members) == {path.name for path in files}
        assert members["symlink"].issym()
        assert members["broken"].issym()
        assert members["directory"].isdir()
        assert members["hardlink"].islnk()

    def test_input_bytes_empty_writer_finalizes_without_member_callbacks(self, tmp_path: Path) -> None:
        counts: list[int] = []
        finalized: list[bool] = []
        out = tmp_path / "empty.tar.gz"
        _write_archive(out, tmp_path, [], on_bytes=counts.append, on_finalize=lambda: finalized.append(True))
        assert counts == []
        assert finalized == [True]
        with tarfile.open(out) as archive:
            assert archive.getmembers() == []

    @pytest.mark.parametrize("size", [7, 29])
    def test_input_bytes_failed_member_preserves_output_and_never_finalizes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        size: int,
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        first = source / "a"
        first.write_bytes(b"x" * size)
        second = source / "a-old"
        second.write_bytes(b"not successfully added")
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"previous archive")
        counts: list[int] = []
        finalized: list[bool] = []
        original_add = tarfile.TarFile.add

        def fail_second(archive: tarfile.TarFile, name: str, *args: object, **kwargs: object) -> None:
            if Path(name) == second:
                raise OSError("archive member failed")
            original_add(archive, name, *args, **kwargs)

        monkeypatch.setattr(tarfile.TarFile, "add", fail_second)
        with pytest.raises(OSError, match="archive member failed"):
            _write_archive(
                out,
                source,
                [first, second],
                on_bytes=counts.append,
                on_finalize=lambda: finalized.append(True),
            )
        assert counts == [size]
        assert finalized == []
        assert out.read_bytes() == b"previous archive"
        assert sorted(path.name for path in tmp_path.iterdir()) == ["out.tar.gz", "src"]

    def test_input_bytes_state_is_local_to_each_shared_capability_run(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        capability = TarArchive()
        monkeypatch.setattr(time, "monotonic", lambda: 42.0)
        for label, size in [("a", 7), ("a-old", 23)]:
            source = tmp_path / label
            source.mkdir()
            (source / "data").write_bytes(b"x" * size)
            events: list[ProgressEvent] = []
            result = next(
                iter(
                    capability.run(
                        label=label,
                        source=str(source),
                        out=str(tmp_path / f"{label}.tar.gz"),
                        engine="python-tarfile",
                        progress=events.append,
                    )
                )
            )
            assert result.success is True
            assert events[-2:] == [
                ProgressEvent(label, "archiving", size, size),
                ProgressEvent(label, "finalizing", size, size),
            ]


class TestProgressExceptionsSwallowed:
    @pytest.mark.parametrize(
        "exception",
        [
            ValueError("first"),
            RuntimeError("first-old"),
            OSError("unavailable"),
            TypeError("unsupported"),
            ProgressConsumerError("consumer failed"),
        ],
    )
    def test_ordinary_progress_exception_is_swallowed_after_delivering_exact_event(self, exception: Exception) -> None:
        events = [ProgressEvent("a", "archiving", 7, 31), ProgressEvent("a-old", "finalizing", 19, 37)]
        received: list[ProgressEvent] = []

        def callback(event: ProgressEvent) -> None:
            received.append(event)
            raise exception

        for event in events:
            tar_archive._emit_progress(callback, event)
        assert received == events
        tar_archive._emit_progress(None, events[0])

    @pytest.mark.parametrize("exception", [KeyboardInterrupt(), SystemExit(7), GeneratorExit(), BaseException("stop")])
    def test_base_exception_is_not_swallowed_by_progress_emitter(self, exception: BaseException) -> None:
        event = ProgressEvent("interrupt", "scanning", None, None)
        received: list[ProgressEvent] = []

        def callback(delivered: ProgressEvent) -> None:
            received.append(delivered)
            raise exception

        with pytest.raises(type(exception)) as caught:
            tar_archive._emit_progress(callback, event)
        assert caught.value is exception
        assert received == [event]

    @pytest.mark.parametrize("phase", ["scanning", "archiving", "finalizing"])
    def test_callback_exception_is_swallowed_and_real_engine_archive_finishes(self, tmp_path: Path, phase: str) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "a").write_bytes(b"first")
        (source / "a-old").write_bytes(b"second payload")
        out = tmp_path / "out.tar.gz"
        events: list[ProgressEvent] = []

        def callback(event: ProgressEvent) -> None:
            events.append(event)
            if event.phase == phase:
                raise RuntimeError("consumer unavailable")

        result = next(
            iter(
                TarArchive().run(
                    label="resilient",
                    source=str(source),
                    out=str(out),
                    engine="python-tarfile",
                    progress=callback,
                )
            )
        )
        assert result.success is True
        assert events[0] == ProgressEvent("resilient", "scanning", None, None)
        assert events[-1] == ProgressEvent("resilient", "finalizing", 19, 19)
        with tarfile.open(out) as archive:
            assert {Path(member.name).name for member in archive.getmembers() if member.isfile()} == {"a", "a-old"}

    @pytest.mark.parametrize("exception", [KeyboardInterrupt(), SystemExit(7)])
    def test_engine_interrupt_is_not_swallowed_and_writer_cleans_temporary_archive(
        self,
        tmp_path: Path,
        exception: BaseException,
    ) -> None:
        source = tmp_path / "src"
        source.mkdir()
        payload = source / "a"
        payload.write_bytes(b"first")
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"previous archive")
        cancel = threading.Event()
        received: list[int] = []

        def callback(done: int) -> None:
            received.append(done)
            cancel.set()
            raise exception

        with pytest.raises(type(exception)) as caught:
            _write_archive(out, source, [payload], cancel=cancel, on_bytes=callback)
        assert caught.value is exception
        assert received == [5]
        assert out.read_bytes() == b"previous archive"
        assert sorted(path.name for path in tmp_path.iterdir()) == ["out.tar.gz", "src"]
