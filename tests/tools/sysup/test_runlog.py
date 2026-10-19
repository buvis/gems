from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from buvis.pybase.result import FatalError

from sysup import runlog


class TestLogsDir:
    def test_xdg_state_home(self, tmp_path: Path) -> None:
        assert runlog.logs_dir() == tmp_path / "state" / "sysup" / "logs"

    def test_fallback_without_xdg(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.delenv("XDG_STATE_HOME")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert runlog.logs_dir() == tmp_path / ".local" / "state" / "sysup" / "logs"


class TestOpenRunLog:
    def test_header_and_plan_names(self, tmp_path: Path) -> None:
        start = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
        log = runlog.open_run_log(start, ["brew", "mise"])
        runlog.close(log)
        text = log.path.read_text()
        assert text == "sysup run 2026-10-18T12:00:00+00:00\nplan: brew, mise\n\n"
        assert log.path.name == "20261018T120000Z.log"

    def test_empty_plan_names_renders_placeholder(self, tmp_path: Path) -> None:
        start = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
        log = runlog.open_run_log(start, [])
        runlog.close(log)
        assert "plan: (empty)\n" in log.path.read_text()

    def test_creates_logs_dir(self, tmp_path: Path) -> None:
        start = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
        assert not runlog.logs_dir().exists()
        log = runlog.open_run_log(start, [])
        runlog.close(log)
        assert runlog.logs_dir().is_dir()

    def test_same_second_collision_gets_suffix(self, tmp_path: Path) -> None:
        start = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
        first = runlog.open_run_log(start, [])
        second = runlog.open_run_log(start, [])
        third = runlog.open_run_log(start, [])
        runlog.close(first)
        runlog.close(second)
        runlog.close(third)
        assert first.path.name == "20261018T120000Z.log"
        assert second.path.name == "20261018T120000Z-1.log"
        assert third.path.name == "20261018T120000Z-2.log"

    def test_does_not_prune(self, tmp_path: Path, mocker) -> None:
        prune = mocker.patch("sysup.runlog.prune")
        log = runlog.open_run_log(datetime(2026, 10, 18, tzinfo=timezone.utc), [])
        runlog.close(log)
        assert prune.call_count == 0

    def test_does_not_truncate_existing_non_matching_file(self, tmp_path: Path) -> None:
        start = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
        directory = runlog.logs_dir()
        directory.mkdir(parents=True)
        existing = directory / "20261018T120000Z.log"
        existing.write_text("pre-existing content")
        log = runlog.open_run_log(start, [])
        runlog.close(log)
        assert existing.read_text() == "pre-existing content"
        assert log.path.name == "20261018T120000Z-1.log"

    def test_mkdir_failure_raises_fatal_with_path(self, tmp_path: Path, mocker) -> None:
        mocker.patch.object(Path, "mkdir", side_effect=OSError("denied"))
        with pytest.raises(FatalError, match=str(runlog.logs_dir())):
            runlog.open_run_log(datetime(2026, 10, 18, tzinfo=timezone.utc), [])

    def test_exclusive_create_other_oserror_raises_fatal(self, tmp_path: Path, mocker) -> None:
        mocker.patch("sysup.runlog.os.open", side_effect=OSError("disk full"))
        with pytest.raises(FatalError, match="disk full"):
            runlog.open_run_log(datetime(2026, 10, 18, tzinfo=timezone.utc), [])

    def test_fdopen_failure_closes_raw_fd(self, tmp_path: Path, mocker) -> None:
        real_close = os.close
        closed: list[int] = []

        def tracking_close(fd: int) -> None:
            closed.append(fd)
            real_close(fd)

        mocker.patch("sysup.runlog.os.close", side_effect=tracking_close)
        mocker.patch("sysup.runlog.os.fdopen", side_effect=OSError("wrap failed"))
        with pytest.raises(FatalError, match="wrap failed"):
            runlog.open_run_log(datetime(2026, 10, 18, tzinfo=timezone.utc), [])
        assert len(closed) == 1

    def test_header_write_failure_closes_wrapped_handle(self, tmp_path: Path, mocker) -> None:
        mocker.patch("sysup.runlog.os.fsync", side_effect=OSError("fsync failed"))
        with pytest.raises(FatalError, match=r"\(incomplete\).*fsync failed"):
            runlog.open_run_log(datetime(2026, 10, 18, tzinfo=timezone.utc), [])
        # the file exists but is incomplete; its handle was closed, not leaked.
        assert runlog.logs_dir().is_dir()

    def test_header_write_failure_suppresses_secondary_close_error(self, tmp_path: Path, mocker) -> None:
        class _BrokenCloseHandle:
            def write(self, _text: str) -> None:
                pass

            def flush(self) -> None:
                pass

            def fileno(self) -> int:
                return -1

            def close(self) -> None:
                raise OSError("close failed")

        mocker.patch("sysup.runlog.os.fdopen", return_value=_BrokenCloseHandle())
        mocker.patch("sysup.runlog.os.fsync", side_effect=OSError("fsync failed"))
        with pytest.raises(FatalError, match="fsync failed"):
            runlog.open_run_log(datetime(2026, 10, 18, tzinfo=timezone.utc), [])

    def test_fdopen_failure_suppresses_secondary_close_error(self, tmp_path: Path, mocker) -> None:
        mocker.patch("sysup.runlog.os.close", side_effect=OSError("close failed"))
        mocker.patch("sysup.runlog.os.fdopen", side_effect=OSError("wrap failed"))
        with pytest.raises(FatalError, match="wrap failed"):
            runlog.open_run_log(datetime(2026, 10, 18, tzinfo=timezone.utc), [])


class TestAppendStep:
    def _log(self, tmp_path: Path) -> runlog.RunLog:
        return runlog.open_run_log(datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc), [])

    def test_captured_step_marker_and_streams(self, tmp_path: Path) -> None:
        log = self._log(tmp_path)
        runlog.append_step(
            log, "brew", "brew update", captured=True, status="ok", exit_code=0, stdout="out\nline2", stderr="err"
        )
        runlog.close(log)
        text = log.path.read_text()
        assert "=== brew: brew update (exit 0) ===\n" in text
        assert "out\nline2\nerr\n\n" in text

    def test_timed_out_marker_with_partial_text(self, tmp_path: Path) -> None:
        log = self._log(tmp_path)
        runlog.append_step(
            log,
            "mise",
            "mise self-update",
            captured=True,
            status="failed",
            timed_out=True,
            timeout_s=30.0,
            stdout="partial",
            stderr="",
        )
        runlog.close(log)
        text = log.path.read_text()
        assert "=== mise: mise self-update (timed out after 30.0s) ===\n" in text
        assert "partial\n\n\n" in text

    def test_not_captured_marker_has_no_stream_section(self, tmp_path: Path) -> None:
        log = self._log(tmp_path)
        runlog.append_step(log, "nvim", "use: nvim-mason", captured=False, status="ok")
        runlog.close(log)
        text = log.path.read_text()
        assert "=== nvim: use: nvim-mason (ok, not captured) ===\n\n" in text

    def test_flushes_and_fsyncs(self, tmp_path: Path, mocker) -> None:
        log = self._log(tmp_path)
        flush = mocker.patch.object(log._handle, "flush", wraps=log._handle.flush)
        fsync = mocker.patch("sysup.runlog.os.fsync")
        runlog.append_step(log, "brew", "brew update", captured=True, status="ok", exit_code=0)
        runlog.close(log)
        assert flush.called
        assert fsync.called

    def test_write_failure_raises_fatal_and_preserves_prior_sections(self, tmp_path: Path, mocker) -> None:
        log = self._log(tmp_path)
        runlog.append_step(log, "brew", "brew update", captured=True, status="ok", exit_code=0, stdout="kept")
        mocker.patch.object(log._handle, "write", side_effect=OSError("disk full"))
        with pytest.raises(FatalError, match=r"\(incomplete\).*disk full"):
            runlog.append_step(log, "mise", "mise upgrade", captured=True, status="ok", exit_code=0)
        log._handle.flush = lambda: None
        log._handle.close = lambda: None
        text = log.path.read_text()
        assert "brew: brew update" in text

    def test_does_not_close_log_on_failure(self, tmp_path: Path, mocker) -> None:
        log = self._log(tmp_path)
        mocker.patch.object(log._handle, "write", side_effect=OSError("boom"))
        with pytest.raises(FatalError):
            runlog.append_step(log, "brew", "brew update", captured=True, status="ok", exit_code=0)
        assert not log._handle.closed


class TestClose:
    def test_closes_handle(self, tmp_path: Path) -> None:
        log = runlog.open_run_log(datetime(2026, 10, 18, tzinfo=timezone.utc), [])
        runlog.close(log)
        assert log._handle.closed

    def test_close_failure_raises_fatal_with_path(self, tmp_path: Path, mocker) -> None:
        log = runlog.open_run_log(datetime(2026, 10, 18, tzinfo=timezone.utc), [])
        mocker.patch.object(log._handle, "close", side_effect=OSError("close failed"))
        with pytest.raises(FatalError, match=r"\(incomplete\).*close failed"):
            runlog.close(log)


class TestPrune:
    def test_missing_directory_is_noop(self, tmp_path: Path) -> None:
        assert runlog.prune(runlog.logs_dir()) is None
        assert not runlog.logs_dir().exists()

    def test_sequential_runs_retain_ten(self, tmp_path: Path) -> None:
        for hour in range(11):
            start = datetime(2026, 10, 18, hour, 0, 0, tzinfo=timezone.utc)
            runlog.prune(runlog.logs_dir())
            log = runlog.open_run_log(start, [])
            runlog.close(log)
        remaining = sorted(p.name for p in runlog.logs_dir().iterdir())
        assert len(remaining) == 10
        assert remaining[0] == "20261018T010000Z.log"

    def test_non_matching_name_is_skipped(self, tmp_path: Path) -> None:
        directory = runlog.logs_dir()
        directory.mkdir(parents=True)
        bogus = directory / "notes.txt"
        bogus.write_text("keep me")
        runlog.prune(directory, keep=0)
        assert bogus.exists()

    def test_symlink_is_skipped_never_followed(self, tmp_path: Path) -> None:
        directory = runlog.logs_dir()
        directory.mkdir(parents=True)
        target = tmp_path / "outside.log"
        target.write_text("outside")
        link = directory / "20261018T010000Z.log"
        link.symlink_to(target)
        runlog.prune(directory, keep=0)
        assert link.exists()
        assert target.exists()

    def test_already_deleted_file_is_not_an_error(self, tmp_path: Path, mocker) -> None:
        directory = runlog.logs_dir()
        directory.mkdir(parents=True)
        unlink = mocker.patch("sysup.runlog.os.unlink", side_effect=FileNotFoundError)
        (directory / "20261018T010000Z.log").write_text("x")
        assert runlog.prune(directory, keep=0) is None
        unlink.assert_called_once()

    def test_other_oserror_on_delete_raises_fatal_and_stops(self, tmp_path: Path, mocker) -> None:
        directory = runlog.logs_dir()
        directory.mkdir(parents=True)
        (directory / "20261018T010000Z.log").write_text("x")
        (directory / "20261018T020000Z.log").write_text("y")
        mocker.patch("sysup.runlog.os.unlink", side_effect=OSError("locked"))
        with pytest.raises(FatalError, match="locked"):
            runlog.prune(directory, keep=0)

    def test_listing_failure_raises_fatal(self, tmp_path: Path, mocker) -> None:
        directory = runlog.logs_dir()
        directory.mkdir(parents=True)
        mocker.patch.object(Path, "iterdir", side_effect=OSError("denied"))
        with pytest.raises(FatalError, match="denied"):
            runlog.prune(directory)

    def test_non_matching_name_is_reported(self, tmp_path: Path, mocker) -> None:
        warning = mocker.patch("sysup.runlog.console.warning")
        directory = runlog.logs_dir()
        directory.mkdir(parents=True)
        bogus = directory / "notes.txt"
        bogus.write_text("keep me")
        runlog.prune(directory, keep=0)
        warning.assert_called_once()
        assert str(bogus) in warning.call_args[0][0]

    def test_non_regular_entry_is_reported(self, tmp_path: Path, mocker) -> None:
        warning = mocker.patch("sysup.runlog.console.warning")
        directory = runlog.logs_dir()
        directory.mkdir(parents=True)
        target = tmp_path / "outside.log"
        target.write_text("outside")
        link = directory / "20261018T010000Z.log"
        link.symlink_to(target)
        runlog.prune(directory, keep=0)
        warning.assert_called_once()
        assert str(link) in warning.call_args[0][0]

    def test_candidate_vanishing_before_restat_is_skipped(self, tmp_path: Path, mocker) -> None:
        directory = runlog.logs_dir()
        directory.mkdir(parents=True)
        path = directory / "20261018T010000Z.log"
        path.write_text("x")
        real_lstat = os.lstat
        calls = {"n": 0}

        def flaky_lstat(target):
            calls["n"] += 1
            if calls["n"] != 1:
                raise FileNotFoundError
            return real_lstat(target)

        mocker.patch("sysup.runlog.os.lstat", side_effect=flaky_lstat)
        unlink = mocker.patch("sysup.runlog.os.unlink")
        assert runlog.prune(directory, keep=0) is None
        unlink.assert_not_called()
        assert calls["n"] == 2
