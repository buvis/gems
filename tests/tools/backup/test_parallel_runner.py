from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from subprocess import Popen
from unittest.mock import call, create_autospec

import pytest
from buvis.pybase.result import FatalError
from click.testing import CliRunner

from backup.capabilities.tar_archive import (
    ArchiveCancelled,
    TarArchive,
    _write_archive,
    _write_archive_system_tar,
)
from backup.cli import cli, console
from backup.runner import Runner
from backup.step_result import StepResult
from tests.tools.backup.parallel_runner_helpers import PRIORITY, WAIT, CapabilityProbe, Consumption, configure


def _members(tmp_path: Path) -> list[Path]:
    source = tmp_path / "src"
    source.mkdir()
    first = source / "report.txt"
    second = source / "report.txt.backup"
    first.write_bytes(b"first archive contents")
    second.write_bytes(b"second, different archive contents")
    omitted = source / "nested" / "report.txt"
    omitted.parent.mkdir()
    omitted.write_bytes(b"same basename, outside the supplied member list")
    return [first, second]


def _assert_output(out: Path, previous: bytes | None) -> None:
    if previous is None:
        assert not out.exists()
    else:
        assert out.read_bytes() == previous


def _require_archive_fsync_before_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    synced: set[tuple[int, int]] = set()
    real_fsync, real_replace = os.fsync, os.replace

    def sync(fd: int) -> None:
        real_fsync(fd)
        stat = os.fstat(fd)
        synced.add((stat.st_dev, stat.st_ino))

    def replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        stat = os.stat(source)
        assert (stat.st_dev, stat.st_ino) in synced, "archive must be fsynced before publication"
        real_replace(source, destination)

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "replace", replace)


def _stub_tar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, stubborn: bool = False, complete: bool = False
) -> Path:
    real_tar = shutil.which("tar")
    assert real_tar is not None
    bindir = tmp_path / "bin"
    bindir.mkdir()
    marker = tmp_path / "tar-started"
    script = bindir / "tar"
    script.write_text(
        f"#!{sys.executable}\n"
        "import os, signal, time\n"
        "from pathlib import Path\n"
        + ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if stubborn else "")
        + f"Path({str(marker)!r}).write_text(\n"
        + "    str(os.getpid()) + '\\n' + str(os.getsid(0)) + '\\n' + os.environ.get('COPYFILE_DISABLE', '')\n)\n"
        + f"time.sleep({0.45 if complete else 30})\n"
        + (f"os.execv({real_tar!r}, [{real_tar!r}, *__import__('sys').argv[1:]])\n" if complete else ""),
        encoding="utf-8",
    )
    script.chmod(0o700)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    return marker


def _cancel_after_start(marker: Path, cancel: threading.Event) -> threading.Thread:
    def watch() -> None:
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            cancel.wait(0.01)
        cancel.set()

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    return thread


@pytest.fixture
def tar_children(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[subprocess.Popen[bytes]]]:
    real_popen = subprocess.Popen
    children: list[subprocess.Popen[bytes]] = []

    def spawn(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(subprocess, "Popen", spawn)
    yield children
    for child in children:
        if child.poll() is None:
            child.kill()
            child.communicate()


class TestPythonArchiveCancellation:
    @pytest.mark.parametrize("previous", [None, b"previous complete archive"])
    def test_cancel_cleans_after_current_member_without_adding_the_next(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        previous: bytes | None,
    ) -> None:
        files = _members(tmp_path)
        out = tmp_path / "out.tar.gz"
        if previous is not None:
            out.write_bytes(previous)
        before = set(tmp_path.iterdir())
        cancel = threading.Event()
        added: list[Path] = []
        real_add = tarfile.TarFile.add

        def add(archive: tarfile.TarFile, name: str | Path, *args: object, **kwargs: object) -> None:
            real_add(archive, name, *args, **kwargs)
            added.append(Path(name))
            cancel.set()

        monkeypatch.setattr(tarfile.TarFile, "add", add)
        with pytest.raises(ArchiveCancelled):
            _write_archive(out, tmp_path, files, cancel=cancel)
        assert added == [files[0]]
        _assert_output(out, previous)
        assert set(tmp_path.iterdir()) == before

    @pytest.mark.parametrize("member_count", [0, 2])
    def test_cancel_cleans_when_iterable_finishes_even_without_members(self, tmp_path: Path, member_count: int) -> None:
        files = _members(tmp_path)[:member_count]
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"earlier archive remains intact")
        before = set(tmp_path.iterdir())
        cancel = threading.Event()

        def selected() -> Iterator[Path]:
            yield from files
            cancel.set()

        with pytest.raises(ArchiveCancelled):
            _write_archive(out, tmp_path, selected(), cancel=cancel)
        assert out.read_bytes() == b"earlier archive remains intact"
        assert set(tmp_path.iterdir()) == before

    @pytest.mark.parametrize("member_count", [0, 2])
    def test_cancel_cleans_when_requested_during_fsync(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        member_count: int,
    ) -> None:
        files = _members(tmp_path)[:member_count]
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"published before this attempt")
        before = set(tmp_path.iterdir())
        cancel = threading.Event()
        real_fsync = os.fsync

        def sync(fd: int) -> None:
            real_fsync(fd)
            cancel.set()

        monkeypatch.setattr(os, "fsync", sync)
        with pytest.raises(ArchiveCancelled):
            _write_archive(out, tmp_path, files, cancel=cancel)
        assert out.read_bytes() == b"published before this attempt"
        assert set(tmp_path.iterdir()) == before

    @pytest.mark.parametrize("member_count", [0, 2])
    @pytest.mark.parametrize("supply_event", [False, True])
    def test_uncancelled_writer_publishes_exact_members_with_private_permissions(
        self,
        tmp_path: Path,
        member_count: int,
        supply_event: bool,
    ) -> None:
        files = _members(tmp_path)[:member_count]
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"old archive")
        before = set(tmp_path.iterdir())
        options = {"cancel": threading.Event()} if supply_event else {}
        _write_archive(out, tmp_path, files, **options)
        with tarfile.open(out, "r:gz") as archive:
            assert archive.getnames() == [str(path.relative_to(tmp_path)) for path in files]
            for path in files:
                member = archive.extractfile(str(path.relative_to(tmp_path)))
                assert member is not None
                assert member.read() == path.read_bytes()
        assert out.stat().st_mode & 0o777 == 0o600
        assert set(tmp_path.iterdir()) == before


class TestSystemArchiveCancellation:
    @pytest.mark.parametrize("previous", [None, b"previous system archive"])
    @pytest.mark.parametrize("stubborn", [False, True])
    def test_terminates_tar_and_cancel_cleans_without_fallback(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        tar_children: list[subprocess.Popen[bytes]],
        previous: bytes | None,
        stubborn: bool,
    ) -> None:
        files = _members(tmp_path)
        marker = _stub_tar(tmp_path, monkeypatch, stubborn=stubborn)
        out = tmp_path / "out.tar.gz"
        if previous is not None:
            out.write_bytes(previous)
        cancel = threading.Event()
        thread = _cancel_after_start(marker, cancel)
        try:
            with pytest.raises(ArchiveCancelled):
                _write_archive_system_tar(out, tmp_path, files, cancel=cancel)
        finally:
            cancel.set()
            thread.join(timeout=4)
        pid, session, copyfile = marker.read_text(encoding="utf-8").splitlines()
        assert pid == session
        assert copyfile == "1"
        assert len(tar_children) == 1
        child = tar_children[0]
        assert child.pid == int(pid)
        assert child.returncode == -(signal.SIGKILL if stubborn else signal.SIGTERM)
        with pytest.raises(ProcessLookupError):
            os.kill(int(pid), 0)
        assert all(pipe is not None and pipe.closed for pipe in (child.stdin, child.stdout, child.stderr))
        _assert_output(out, previous)
        assert set(tmp_path.iterdir()) == {files[0].parent, marker.parent / "bin", marker} | (
            {out} if previous else set()
        )

    def test_polling_timeouts_retry_without_input_and_do_not_trigger_python_fallback(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        tar_children: list[subprocess.Popen[bytes]],
    ) -> None:
        files = _members(tmp_path)
        unusual = files[0].parent / "space and\nnewline.txt"
        unusual.write_bytes(b"NUL-delimited filename content")
        files.append(unusual)
        marker = _stub_tar(tmp_path, monkeypatch, complete=True)
        out = tmp_path / "out.tar.gz"
        calls: list[dict[str, object]] = []
        real_communicate = Popen.communicate

        def communicate(child: Popen[bytes], **kwargs: object) -> tuple[bytes, bytes]:
            calls.append(dict(kwargs))
            return real_communicate(child, **kwargs)

        monkeypatch.setattr(Popen, "communicate", communicate)
        _require_archive_fsync_before_publication(monkeypatch)
        assert _write_archive_system_tar(out, tmp_path, files, cancel=threading.Event()) is None
        assert marker.exists()
        assert len(calls) >= 2
        assert calls[0] == {
            "input": b"\0".join(str(path.relative_to(tmp_path)).encode() for path in files) + b"\0",
            "timeout": 0.2,
        }
        assert all(item == {"timeout": 0.2} for item in calls[1:])
        with tarfile.open(out, "r:gz") as archive:
            assert set(archive.getnames()) == {str(path.relative_to(tmp_path)) for path in files}
            for path in files:
                member = archive.extractfile(str(path.relative_to(tmp_path)))
                assert member is not None
                assert member.read() == path.read_bytes()
        assert out.stat().st_mode & 0o777 == 0o600
        assert all(
            pipe is not None and pipe.closed
            for pipe in (tar_children[0].stdin, tar_children[0].stdout, tar_children[0].stderr)
        )

    @pytest.mark.parametrize("member_count", [0, 2])
    def test_cancel_cleans_before_spawn_when_member_iteration_sets_event(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        member_count: int,
    ) -> None:
        files = _members(tmp_path)[:member_count]
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"last usable backup")
        before = set(tmp_path.iterdir())
        cancel = threading.Event()

        def selected() -> Iterator[Path]:
            yield from files
            cancel.set()

        def unexpected_spawn(*args: object, **kwargs: object) -> None:
            pytest.fail("member-iteration cancellation must prevent starting tar")

        monkeypatch.setattr(subprocess, "Popen", unexpected_spawn)
        with pytest.raises(ArchiveCancelled):
            _write_archive_system_tar(out, tmp_path, selected(), cancel=cancel)
        assert out.read_bytes() == b"last usable backup"
        assert set(tmp_path.iterdir()) == before

    @pytest.mark.parametrize("member_count", [0, 2])
    def test_cancel_cleans_after_child_exits_without_publishing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        member_count: int,
    ) -> None:
        files = _members(tmp_path)[:member_count]
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"last usable backup")
        before = set(tmp_path.iterdir())
        cancel = threading.Event()
        process = create_autospec(subprocess.Popen, instance=True)
        process.poll.return_value = 0
        process.returncode = 0
        process.stdin = None
        process.stdout = None
        process.stderr = None

        def communicate(input: bytes | None = None, timeout: float | None = None) -> tuple[bytes, bytes]:
            cancel.set()
            return b"", b""

        process.communicate.side_effect = communicate
        monkeypatch.setattr(subprocess, "Popen", create_autospec(subprocess.Popen, return_value=process))
        with pytest.raises(ArchiveCancelled):
            _write_archive_system_tar(out, tmp_path, files, cancel=cancel)
        expected_input = b"".join(os.fsencode(path.relative_to(tmp_path)) + b"\0" for path in files)
        assert process.communicate.call_args_list == [call(input=expected_input, timeout=0.2)]
        assert out.read_bytes() == b"last usable backup"
        assert set(tmp_path.iterdir()) == before


class TestCapabilityArchiveCancellation:
    @pytest.mark.parametrize("engine", ["python-tarfile", "system-tar"])
    def test_already_cancelled_capability_does_not_select_members_or_create_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        engine: str,
    ) -> None:
        files = _members(tmp_path)
        out = tmp_path / "new-output-directory" / "out.tar.gz"
        cancel = threading.Event()
        cancel.set()

        def unexpected_walk(*args: object, **kwargs: object) -> None:
            pytest.fail("an already-cancelled capability must not walk the source")

        monkeypatch.setattr(os, "scandir", unexpected_walk)
        with pytest.raises(ArchiveCancelled):
            list(
                TarArchive().run(
                    label="pre-cancelled", source=str(files[0].parent), out=str(out), engine=engine, cancel=cancel
                )
            )
        assert not out.parent.exists()

    @pytest.mark.parametrize("engine", ["python-tarfile", "system-tar"])
    def test_capability_forwards_cancellation_to_selected_engine_or_legitimate_fallback(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        engine: str,
    ) -> None:
        files = _members(tmp_path)
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"complete capability backup")
        cancel = threading.Event()
        real_add = tarfile.TarFile.add

        def add(archive: tarfile.TarFile, name: str | Path, *args: object, **kwargs: object) -> None:
            real_add(archive, name, *args, **kwargs)
            cancel.set()

        def unavailable(*args: object, **kwargs: object) -> None:
            raise OSError("tar unavailable for legitimate Python fallback")

        monkeypatch.setattr(tarfile.TarFile, "add", add)
        if engine == "system-tar":
            monkeypatch.setattr(subprocess, "Popen", unavailable)
        before = set(tmp_path.iterdir())
        with pytest.raises(ArchiveCancelled):
            list(
                TarArchive().run(
                    label="cancel-during-write", source=str(files[0].parent), out=str(out), engine=engine, cancel=cancel
                )
            )
        assert out.read_bytes() == b"complete capability backup"
        assert set(tmp_path.iterdir()) == before

    @pytest.mark.parametrize("engine", ["python-tarfile", "system-tar"])
    def test_cancel_cleans_temp_files_both_engines(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        tar_children: list[subprocess.Popen[bytes]],
        engine: str,
    ) -> None:
        files = _members(tmp_path)
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"last complete capability archive")
        cancel = threading.Event()
        marker = _stub_tar(tmp_path, monkeypatch) if engine == "system-tar" else None
        before = set(tmp_path.iterdir())
        real_add = tarfile.TarFile.add

        def add(archive: tarfile.TarFile, name: str | Path, *args: object, **kwargs: object) -> None:
            if engine == "system-tar":
                pytest.fail("cancellation must escape the system writer without Python fallback")
            real_add(archive, name, *args, **kwargs)
            cancel.set()

        monkeypatch.setattr(tarfile.TarFile, "add", add)
        thread = _cancel_after_start(marker, cancel) if marker is not None else None
        try:
            with pytest.raises(ArchiveCancelled):
                list(
                    TarArchive().run(
                        label="archive-cancel",
                        source=str(files[0].parent),
                        out=str(out),
                        engine=engine,
                        cancel=cancel,
                    )
                )
        finally:
            cancel.set()
            if thread is not None:
                thread.join(timeout=4)
        assert out.read_bytes() == b"last complete capability archive"
        assert set(tmp_path.iterdir()) == before | ({marker} if marker is not None else set())
        if engine == "system-tar":
            assert marker is not None and marker.exists()
            assert len(tar_children) == 1
            assert tar_children[0].returncode == -signal.SIGTERM


class TestParallelRunner:
    @pytest.mark.parametrize("jobs", [0, -2])
    def test_jobs_rejects_nonpositive_limits(self, monkeypatch: pytest.MonkeyPatch, jobs: int) -> None:
        cfg = configure(monkeypatch, CapabilityProbe())
        with pytest.raises(ValueError, match="^jobs must be at least 1$"):
            Runner(cfg, jobs=jobs)

    @pytest.mark.parametrize("jobs", [None, 1, 2])
    def test_never_exceeds_jobs(self, monkeypatch: pytest.MonkeyPatch, jobs: int | None) -> None:
        probe = CapabilityProbe()
        cfg = configure(monkeypatch, probe)
        runner = Runner(cfg) if jobs is None else Runner(cfg, jobs=jobs)
        limit = 3 if jobs is None else jobs
        with Consumption(runner, cfg, probe) as consumer:
            for name in PRIORITY[:limit]:
                assert probe.started[name].wait(WAIT), f"initial batch did not start {name}"
            assert not any(probe.started[name].is_set() for name in PRIORITY[limit:])
            assert probe.maximum == limit
            probe.release_all()
            consumer.finish()
        assert probe.maximum == limit
        assert {result.label for result in consumer.results} == set(PRIORITY)
        assert len(consumer.results) == 5
        assert all(result.success for result in consumer.results)
        assert runner.interrupted is False
        assert runner.cancelled_names == ()

    def test_jobs_one_runs_strictly_in_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        probe = CapabilityProbe()
        cfg = configure(monkeypatch, probe)
        runner = Runner(cfg, jobs=1)
        with Consumption(runner, cfg, probe) as consumer:
            for index, name in enumerate(PRIORITY):
                assert probe.started[name].wait(WAIT)
                assert [call["label"] for call in probe.calls] == list(PRIORITY[: index + 1])
                probe.release[name].set()
                assert consumer.received[name].wait(WAIT)
            consumer.finish()
        assert [result.label for result in consumer.results] == list(PRIORITY)
        assert probe.maximum == 1

    def test_order_follows_completion_while_preserving_each_instances_steps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probe = CapabilityProbe(("alpha-copy", "alpha"))
        cfg = configure(monkeypatch, probe)

        def steps(kwargs: dict[str, object]) -> Iterator[StepResult]:
            name = str(kwargs["label"])
            assert probe.release[name].wait(WAIT)
            yield StepResult(name, True, f"first {name}")
            yield StepResult(name, True, f"second {name}")

        probe.behavior = steps
        with Consumption(Runner(cfg, jobs=2), cfg, probe) as consumer:
            assert probe.started["alpha"].wait(WAIT)
            assert probe.started["alpha-copy"].wait(WAIT)
            probe.release["alpha-copy"].set()
            assert consumer.received["alpha-copy"].wait(WAIT)
            probe.release["alpha"].set()
            consumer.finish()
        assert [(row.label, row.message) for row in consumer.results] == [
            ("alpha-copy", "first alpha-copy"),
            ("alpha-copy", "second alpha-copy"),
            ("alpha", "first alpha"),
            ("alpha", "second alpha"),
        ]
        assert set(consumer.thread_ids) == {consumer.thread.ident}
        assert all(worker != consumer.thread.ident for worker in probe.thread_ids)

    @pytest.mark.parametrize("error", [ValueError("bad archive"), FatalError("disk unavailable")])
    def test_failure_isolated_from_other_workers(self, monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
        probe = CapabilityProbe(("alpha", "alpha-copy"))
        cfg = configure(monkeypatch, probe)

        def fail_one(kwargs: dict[str, object]) -> Iterator[StepResult]:
            name = str(kwargs["label"])
            if name == "alpha":
                raise error
            yield StepResult(name, True, "independent complete")

        probe.behavior = fail_one
        results = {row.label: row for row in Runner(cfg, jobs=2).run(list(cfg.instances.items()))}
        assert set(results) == {"alpha", "alpha-copy"}
        assert results["alpha"].success is False
        assert results["alpha"].message == f"alpha failed: {error}"
        assert results["alpha"].archive is None
        assert results["alpha-copy"].success is True
        assert results["alpha-copy"].message == "independent complete"

    def test_interrupt_cancels_active_and_unsubmitted_but_preserves_committed_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probe = CapabilityProbe(("omega", "alpha-copy", "alpha"))
        cfg = configure(monkeypatch, probe)

        def interruptible(kwargs: dict[str, object]) -> Iterator[StepResult]:
            name = str(kwargs["label"])
            cancel = kwargs["cancel"]
            assert isinstance(cancel, threading.Event)
            if name == "alpha":
                assert probe.started["alpha-copy"].wait(WAIT)
                yield StepResult(name, True, "committed alpha")
                return
            assert cancel.wait(WAIT)
            raise ArchiveCancelled()

        probe.behavior = interruptible
        runner = Runner(cfg, jobs=2)
        iterator = runner.run(list(cfg.instances.items()))
        try:
            first = next(iterator)
            runner.request_cancel()
            runner.request_cancel()
            results = [first, *iterator]
        finally:
            runner.request_cancel()
            iterator.close()
        assert first.label == "alpha" and first.success is True
        assert first.message == "committed alpha"
        assert [row.label for row in results].count("alpha") == 1
        assert {row.label for row in results if not row.success} == {"alpha-copy", "omega"}
        assert len(results) == 3
        assert not probe.started["omega"].is_set()

        assert runner.interrupted is True
        assert runner.cancelled_names == ("alpha-copy", "omega")
        assert probe.active == 0

    def test_interrupt_keyboard_at_yield_drains_workers_without_reraising(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probe = CapabilityProbe(("alpha", "alpha-copy", "omega"))
        cfg = configure(monkeypatch, probe)

        def interruptible(kwargs: dict[str, object]) -> Iterator[StepResult]:
            name = str(kwargs["label"])
            if name == "alpha":
                assert probe.started["alpha-copy"].wait(WAIT)
                yield StepResult(name, True, "already committed")
                return
            cancel = kwargs["cancel"]
            assert isinstance(cancel, threading.Event)
            assert cancel.wait(WAIT)
            raise ArchiveCancelled()

        probe.behavior = interruptible
        runner = Runner(cfg, jobs=2)
        iterator = runner.run(list(cfg.instances.items()))
        try:
            completed = next(iterator)
            interrupted = iterator.throw(KeyboardInterrupt())
            remaining = [interrupted, *iterator]
        finally:
            runner.request_cancel()
            iterator.close()
        assert completed.success is True
        assert len(remaining) == 2
        assert all(not row.success and row.archive is None and not row.skipped for row in remaining)
        assert {row.label for row in remaining} == {"alpha-copy", "omega"}
        assert runner.interrupted is True
        assert runner.cancelled_names == ("alpha-copy", "omega")
        assert probe.active == 0

    def test_interrupt_generator_close_joins_active_workers_and_prevents_refill(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probe = CapabilityProbe(("alpha", "alpha-copy", "omega"))
        cfg = configure(monkeypatch, probe)
        cleaned = threading.Event()

        def interruptible(kwargs: dict[str, object]) -> Iterator[StepResult]:
            name = str(kwargs["label"])
            if name == "alpha":
                assert probe.started["alpha-copy"].wait(WAIT)
                yield StepResult(name, True, "finished before close")
                return
            cancel = kwargs["cancel"]
            assert isinstance(cancel, threading.Event)
            assert cancel.wait(WAIT)
            cleaned.set()
            raise ArchiveCancelled()

        probe.behavior = interruptible
        runner = Runner(cfg, jobs=2)
        iterator = runner.run(list(cfg.instances.items()))
        try:
            assert next(iterator).label == "alpha"
        finally:
            iterator.close()
        assert cleaned.is_set()
        assert probe.active == 0
        assert not probe.started["omega"].is_set()


class TestCliParallelJobs:
    @pytest.mark.parametrize("jobs", [0, -2])
    @pytest.mark.parametrize("mode", [[], ["--list"], ["--plan"], ["--dry-run"]])
    def test_cli_rejects_invalid_jobs_before_loading_config_or_early_modes(
        self, tmp_path: Path, jobs: int, mode: list[str]
    ) -> None:
        missing = tmp_path / "missing.yaml"
        result = CliRunner().invoke(
            cli, ["--config-dir", str(tmp_path), "--config", str(missing), "--jobs", str(jobs), *mode]
        )
        assert result.exit_code == 1, result.output
        assert "--jobs must be at least 1" in result.output
        assert str(missing) not in result.output
        assert "Usage:" not in result.output

    @pytest.mark.parametrize("arguments,expected", [([], 3), (["--jobs", "1"], 1), (["--jobs", "2"], 2)])
    @pytest.mark.parametrize("dry_run", [False, True])
    def test_cli_forwards_default_and_explicit_jobs_to_real_scheduling(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        arguments: list[str],
        expected: int,
        dry_run: bool,
    ) -> None:
        probe = CapabilityProbe()
        cfg = configure(monkeypatch, probe)
        payload = cfg.model_dump(by_alias=True)
        payload["instances"]["git-src"] = {"use": "tar-archive", "enabled": False}
        path = tmp_path / "jobs.yaml"
        path.write_text(json.dumps(payload), encoding="utf-8")
        messages: list[str] = []
        monkeypatch.setattr(console, "info", messages.append)
        failures: list[BaseException] = []

        def release_batch() -> None:
            try:
                for name in PRIORITY[:expected]:
                    assert probe.started[name].wait(WAIT), f"missing initial worker {name}"
                assert all(not probe.started[name].is_set() for name in PRIORITY[expected:])
            except BaseException as exc:
                failures.append(exc)
            finally:
                probe.release_all()

        releaser = threading.Thread(target=release_batch, daemon=True)
        releaser.start()
        try:
            mode = ["--dry-run"] if dry_run else []
            result = CliRunner().invoke(cli, ["--config-dir", str(tmp_path), "--config", str(path), *arguments, *mode])
        finally:
            probe.release_all()
            releaser.join(WAIT)
        assert not releaser.is_alive()
        assert failures == []
        assert result.exit_code == 0, result.output
        assert probe.maximum == expected
        assert {row["label"] for row in probe.calls} == set(PRIORITY)
        assert len(probe.calls) == len(PRIORITY)
        assert all(row["dry_run"] is dry_run for row in probe.calls)
        assert all(row["token"] == f"token-{row['label']}" for row in probe.calls)
        assert probe.active == 0
        verb = "previewed" if dry_run else "archived"
        assert messages[-1] == f"{verb} 5, skipped 0, failed 0"

    @pytest.mark.parametrize("name", ["alpha", "alpha-copy"])
    def test_cli_plan_keeps_writers_and_executor_unused_with_jobs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
    ) -> None:
        from concurrent.futures import ThreadPoolExecutor

        probe = CapabilityProbe(("alpha", "alpha-copy"))
        cfg = configure(monkeypatch, probe)
        payload = cfg.model_dump(by_alias=True)
        payload["instances"]["git-src"] = {"use": "tar-archive", "enabled": False}
        path = tmp_path / "plan.yaml"
        path.write_text(json.dumps(payload), encoding="utf-8")

        def reject_executor(*args: object, **kwargs: object) -> None:
            raise AssertionError("a read-only plan must not construct an executor")

        monkeypatch.setattr(ThreadPoolExecutor, "__init__", reject_executor)
        result = CliRunner().invoke(
            cli, ["--config-dir", str(tmp_path), "--config", str(path), "--jobs", "2", "--plan", "--only", name]
        )
        assert result.exit_code == 0, result.output
        assert [row["label"] for row in probe.plans] == [name]
        assert probe.calls == []
        assert name in result.output
