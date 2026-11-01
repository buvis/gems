from __future__ import annotations

import io
import os
import subprocess
import threading
from pathlib import Path
from unittest.mock import Mock, call, create_autospec

import pytest

from backup.capabilities.tar_archive import ArchiveCancelled, _write_archive_system_tar


def _controlled_tar(
    monkeypatch: pytest.MonkeyPatch, cancel: threading.Event, mode: str, failure: str
) -> tuple[Mock, Mock]:
    process = create_autospec(subprocess.Popen, instance=True)
    process.stdin, process.stdout, process.stderr = io.BytesIO(), io.BytesIO(), io.BytesIO()
    process.poll.return_value = None
    process.returncode = None
    initial = OSError("pipe broken") if failure == "exception" else subprocess.TimeoutExpired("tar", 0.2)
    outcomes: list[BaseException | tuple[bytes, bytes]] = [initial]
    if mode.startswith("kill"):
        outcomes.append(subprocess.TimeoutExpired("tar", 5.0))
    outcomes.append((b"", b""))
    pending = iter(outcomes)

    def communicate(input: bytes | None = None, timeout: float | None = None) -> tuple[bytes, bytes]:
        outcome = next(pending)
        if failure == "cancel":
            cancel.set()
        if isinstance(outcome, BaseException):
            raise outcome
        process.returncode = -9 if mode.startswith("kill") else -15
        return outcome

    process.communicate.side_effect = communicate
    if mode == "terminate-race":
        process.terminate.side_effect = ProcessLookupError("already exited during terminate")
    if mode == "kill-race":
        process.kill.side_effect = ProcessLookupError("already exited during kill")

    def start(args: list[str], **kwargs: object) -> Mock:
        Path(args[6]).write_bytes(b"partial archive from failed child")
        return process

    spawn = create_autospec(subprocess.Popen, side_effect=start)
    monkeypatch.setattr(subprocess, "Popen", spawn)
    monkeypatch.setattr("backup.capabilities.tar_archive.shutil.which", lambda name: "/controlled/tar")
    return process, spawn


class TestSystemTarLifecycle:
    @pytest.mark.parametrize("mode", ["terminate", "kill", "terminate-race", "kill-race"])
    @pytest.mark.parametrize("failure", ["exception", "cancel"])
    @pytest.mark.parametrize("previous", [None, b"last complete backup"])
    def test_failure_reaps_child_closes_pipes_and_preserves_atomic_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, failure: str, previous: bytes | None
    ) -> None:
        source = tmp_path / "member.txt"
        source.write_bytes(b"selected contents")
        out = tmp_path / "out.tar.gz"
        if previous is not None:
            out.write_bytes(previous)
        before = set(tmp_path.iterdir())
        cancel = threading.Event()
        process, spawn = _controlled_tar(monkeypatch, cancel, mode, failure)
        if failure == "cancel":
            with pytest.raises(ArchiveCancelled):
                _write_archive_system_tar(out, tmp_path, [source], cancel=cancel)
        else:
            assert _write_archive_system_tar(out, tmp_path, [source], cancel=cancel) == (
                "tar invocation failed: pipe broken"
            )
        expected = [
            call.communicate(input=b"member.txt\0", timeout=0.2),
            call.poll(),
            call.terminate(),
            call.communicate(timeout=5.0),
        ]
        if mode.startswith("kill"):
            expected.extend([call.kill(), call.communicate()])
        assert process.mock_calls == expected
        assert process.returncode == (-9 if mode.startswith("kill") else -15)
        assert all(pipe.closed for pipe in (process.stdin, process.stdout, process.stderr))
        spawn.assert_called_once()
        args, kwargs = spawn.call_args
        temp = Path(args[0][6])
        assert args[0] == [
            "/controlled/tar",
            "-C",
            str(tmp_path),
            "--no-recursion",
            "--null",
            "-czf",
            str(temp),
            "-T",
            "-",
        ]
        assert kwargs["stdin"] == kwargs["stdout"] == kwargs["stderr"] == subprocess.PIPE
        assert kwargs["start_new_session"] is True
        assert kwargs["env"] == {**os.environ, "COPYFILE_DISABLE": "1"}
        assert temp.parent == out.parent and temp != out
        assert not temp.exists()
        assert set(tmp_path.iterdir()) == before
        if previous is None:
            assert not out.exists()
        else:
            assert out.read_bytes() == previous
