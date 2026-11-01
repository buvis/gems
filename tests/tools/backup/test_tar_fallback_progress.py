from __future__ import annotations

import os
import shutil
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from backup.capabilities.tar_archive import TarArchive

if TYPE_CHECKING:
    from backup.capabilities.tar_archive import ProgressEvent


def _source_files(root: Path, payload: bytes) -> dict[str, bytes]:
    root.mkdir()
    files = {"member.txt": payload, "member.txt.extra": payload[::-1], "empty.txt": b""}
    for name, contents in files.items():
        (root / name).write_bytes(contents)
    return files


def _fail_after_finalizing(
    monkeypatch: pytest.MonkeyPatch, boundary: str, events: list[ProgressEvent], *, always: bool = False
) -> list[str]:
    original = getattr(os, boundary)
    failures: list[str] = []

    def fail(*args: object, **kwargs: object) -> object:
        if events and events[-1].phase == "finalizing" and (always or not failures):
            failures.append(events[-1].phase)
            raise OSError("post-close persistence failed")
        return original(*args, **kwargs)

    monkeypatch.setattr(os, boundary, fail)
    return failures


def _assert_archive(out: Path, files: dict[str, bytes]) -> None:
    with tarfile.open(out, "r:gz") as archive:
        actual: dict[str, bytes] = {}
        for member in archive.getmembers():
            if member.isfile():
                stream = archive.extractfile(member)
                assert stream is not None
                with stream:
                    actual[Path(member.name).name] = stream.read()
    assert actual == files


class TestFallbackProgress:
    @pytest.mark.parametrize("boundary", ["fsync", "chmod", "replace"])
    @pytest.mark.parametrize("label,payload", [("docs", b"first archive"), ("docs-extra", b"different payload")])
    def test_post_close_failure_restarts_activity_before_python_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str, label: str, payload: bytes
    ) -> None:
        assert shutil.which("tar") is not None, "This regression requires the system tar path"
        source, out = tmp_path / label, tmp_path / f"{label}.tar.gz"
        files = _source_files(source, payload)
        out.write_bytes(b"previous complete backup")
        events: list[ProgressEvent] = []
        failures = _fail_after_finalizing(monkeypatch, boundary, events)
        (result,) = TarArchive().run(
            label=label,
            source=str(source),
            out=str(out),
            excludes=[],
            progress=events.append,
            engine="system-tar",
        )
        assert result.success, result.message
        assert failures == ["finalizing"]
        assert result.out_path == str(out)
        assert result.file_count == len(files)
        total = sum(map(len, files.values()))
        assert result.total_bytes == total
        _assert_archive(out, files)
        activity = [event for event in events if event.phase != "scanning"]
        phases = [event.phase for event in activity]
        assert phases[0] == "archiving"
        first_close = phases.index("finalizing")
        assert phases[first_close + 1] == "archiving", phases
        assert phases[-1] == "finalizing"
        assert all(event.label == label and event.total_bytes == total for event in activity)
        assert all(event.done_bytes is None for event in activity if event.phase == "archiving")

    @pytest.mark.parametrize("payload", [b"old", b"older complete backup"])
    def test_persistent_post_close_failure_is_reported_and_preserves_previous_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: bytes
    ) -> None:
        source, out = tmp_path / "source", tmp_path / "backup.tar.gz"
        _source_files(source, b"new archive contents")
        out.write_bytes(payload)
        events: list[ProgressEvent] = []
        failures = _fail_after_finalizing(monkeypatch, "fsync", events, always=True)
        with pytest.raises(OSError, match="post-close persistence failed"):
            list(
                TarArchive().run(
                    label="failing",
                    source=str(source),
                    out=str(out),
                    excludes=[],
                    progress=events.append,
                    engine="system-tar",
                )
            )
        assert failures == ["finalizing", "finalizing"]
        assert out.read_bytes() == payload
        assert sorted(path.name for path in tmp_path.iterdir()) == ["backup.tar.gz", "source"]
