"""Tests for update execution and re-exec."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.updater.detector import InstallerInfo
from buvis.pybase.updater.executor import run_update, run_update_interactive


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    return tmp_path


def _uv_tool_installer() -> InstallerInfo:
    return InstallerInfo(method="uv-tool", upgrade_command=("uv", "tool", "upgrade", "buvis-gems"))


def _mise_pipx_installer() -> InstallerInfo:
    return InstallerInfo(method="mise-pipx", upgrade_command=("mise", "upgrade", "pipx:buvis-gems"))


class TestRunUpdateKnownInstaller:
    def test_runs_upgrade_command(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_os.execvp.side_effect = SystemExit(0)
            mock_sys.argv = ["bim", "list"]
            mock_sys.exit.side_effect = SystemExit

            with pytest.raises(SystemExit):
                run_update("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        assert mock_sub.run.call_args_list[0].args[0] == ("uv", "tool", "upgrade", "buvis-gems")
        assert mock_sub.run.call_args_list[0].kwargs == {"capture_output": True, "timeout": 120}

    def test_logs_updating_message(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_os.execvp.side_effect = SystemExit(0)
            mock_sys.argv = ["bim", "list"]
            mock_sys.exit.side_effect = SystemExit

            with pytest.raises(SystemExit):
                run_update("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        log_calls = [call.args for call in mock_log.call_args_list]
        assert any("0.7.0" in msg and "0.8.0" in msg for _, level, msg in log_calls if level == "info")

    def test_reexecs_on_success(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.console") as mock_console,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_sys.argv = ["bim", "list"]

            run_update("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        mock_os.execvp.assert_called_once_with("bim", ["bim", "list"])
        mock_console.panic.assert_not_called()

    def test_nothing_printed_to_stderr(self, state_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os"),
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestRunUpdateMisePipx:
    def test_resolves_new_mise_binary_path_before_reexec(self, state_dir: Path, tmp_path: Path) -> None:
        """After a mise upgrade the binary lives at a new version-specific path."""
        new_root = tmp_path / "new_install"
        new_binary = new_root / "bin" / "hello-world"
        new_binary.parent.mkdir(parents=True)
        new_binary.touch()

        def fake_subprocess_run(*args: object, **kwargs: object) -> MagicMock:
            cmd = args[0]
            if cmd == ("mise", "upgrade", "pipx:buvis-gems"):
                return MagicMock(returncode=0, stderr=b"")
            if cmd == ("mise", "where", "pipx:buvis-gems"):
                return MagicMock(returncode=0, stdout=f"{new_root}\n")
            raise AssertionError(f"unexpected command: {cmd}")

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
        ):
            mock_sub.run.side_effect = fake_subprocess_run
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            mock_sys.argv = ["/old/install/bin/hello-world", "--flag"]

            run_update("0.8.1", "0.8.2", _mise_pipx_installer(), state_dir=state_dir)

        mock_os.execvp.assert_called_once_with(
            str(new_binary),
            [str(new_binary), "--flag"],
        )

    def test_falls_back_to_sys_argv_when_mise_where_fails(self, state_dir: Path) -> None:
        def fake_subprocess_run(*args: object, **kwargs: object) -> MagicMock:
            cmd = args[0]
            if cmd == ("mise", "upgrade", "pipx:buvis-gems"):
                return MagicMock(returncode=0, stderr=b"")
            if cmd == ("mise", "where", "pipx:buvis-gems"):
                return MagicMock(returncode=1, stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
        ):
            mock_sub.run.side_effect = fake_subprocess_run
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            mock_sys.argv = ["/old/install/bin/hello-world"]

            run_update("0.8.1", "0.8.2", _mise_pipx_installer(), state_dir=state_dir)

        mock_os.execvp.assert_called_once_with(
            "/old/install/bin/hello-world",
            ["/old/install/bin/hello-world"],
        )

    def test_falls_back_when_new_binary_missing(self, state_dir: Path, tmp_path: Path) -> None:
        new_root = tmp_path / "new_install"
        # Intentionally not creating new_root/bin/hello-world

        def fake_subprocess_run(*args: object, **kwargs: object) -> MagicMock:
            cmd = args[0]
            if cmd == ("mise", "upgrade", "pipx:buvis-gems"):
                return MagicMock(returncode=0, stderr=b"")
            if cmd == ("mise", "where", "pipx:buvis-gems"):
                return MagicMock(returncode=0, stdout=f"{new_root}\n")
            raise AssertionError(f"unexpected command: {cmd}")

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
        ):
            mock_sub.run.side_effect = fake_subprocess_run
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            mock_sys.argv = ["/old/install/bin/hello-world"]

            run_update("0.8.1", "0.8.2", _mise_pipx_installer(), state_dir=state_dir)

        mock_os.execvp.assert_called_once_with(
            "/old/install/bin/hello-world",
            ["/old/install/bin/hello-world"],
        )


class TestRunUpdateFailure:
    def test_logs_on_nonzero_exit(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.return_value = MagicMock(returncode=1, stderr=b"permission denied")
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        mock_os.execvp.assert_not_called()
        log_calls = [call.args for call in mock_log.call_args_list]
        assert any(
            level == "error" and ("failed" in msg.lower() or "permission denied" in msg.lower())
            for _, level, msg in log_calls
        )

    def test_logs_on_timeout(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.side_effect = subprocess.TimeoutExpired(cmd="uv", timeout=120)
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        mock_os.execvp.assert_not_called()
        assert any(level == "error" for _, level, _ in (call.args for call in mock_log.call_args_list))

    def test_logs_on_file_not_found(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.side_effect = FileNotFoundError("uv not found")
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        mock_os.execvp.assert_not_called()
        assert any(level == "error" for _, level, _ in (call.args for call in mock_log.call_args_list))

    def test_logs_on_os_error(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.side_effect = OSError("broken pipe")
            mock_sys.argv = ["bim"]

            run_update("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        mock_os.execvp.assert_not_called()
        assert any(level == "error" for _, level, _ in (call.args for call in mock_log.call_args_list))


class TestRunUpdateExecvpFailure:
    def test_execvp_os_error_exits_one_and_reports_restart_failed(
        self, state_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A real re-exec failure must terminate the process with status 1, print the
        user-facing failure text, and log the same text at level "error" — exercised
        against the real console adapter, not a mock that supplies its own SystemExit."""
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.sys") as mock_sys,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)
            mock_os.execvp.side_effect = OSError("No such file or directory")
            mock_sys.argv = ["bim", "list"]

            with pytest.raises(SystemExit) as exc_info:
                run_update("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        assert exc_info.value.code == 1
        message = "Restart failed: No such file or directory. Update applied; please re-run the command."
        printed = " ".join(capsys.readouterr().out.split())
        assert message in printed
        assert "✘" in printed
        mock_log.assert_any_call(state_dir, "error", message)


class TestRunUpdateInteractive:
    def test_success_returns_zero(self, state_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)

            result = run_update_interactive("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        assert result == 0
        mock_os.execvp.assert_not_called()
        call = mock_sub.run.call_args_list[0]
        assert call.args[0] == ("uv", "tool", "upgrade", "buvis-gems")
        assert call.kwargs.get("capture_output") is False
        out = capsys.readouterr().out
        assert "0.7.0" in out and "0.8.0" in out

    def test_subprocess_nonzero_returns_one(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.return_value = MagicMock(returncode=2)

            result = run_update_interactive("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        assert result == 1
        mock_os.execvp.assert_not_called()
        assert any(level == "error" for _, level, _ in (c.args for c in mock_log.call_args_list))

    def test_timeout_returns_one(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
        ):
            mock_sub.run.side_effect = subprocess.TimeoutExpired(cmd="uv", timeout=120)
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired

            result = run_update_interactive("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        assert result == 1
        mock_os.execvp.assert_not_called()

    def test_file_not_found_returns_one(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
        ):
            mock_sub.run.side_effect = FileNotFoundError("uv not found")
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired

            result = run_update_interactive("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        assert result == 1
        mock_os.execvp.assert_not_called()

    def test_logs_success(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            mock_sub.run.return_value = MagicMock(returncode=0)

            run_update_interactive("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        assert any(level == "info" for _, level, _ in (c.args for c in mock_log.call_args_list))

    def test_none_upgrade_command_returns_one(self, state_dir: Path) -> None:
        """Defensive: if caller passes unknown installer, return 1 without invoking subprocess."""
        installer = InstallerInfo(method="unknown", upgrade_command=None)

        with patch("buvis.pybase.updater.executor.subprocess") as mock_sub:
            result = run_update_interactive("0.7.0", "0.8.0", installer, state_dir=state_dir)

        assert result == 1
        mock_sub.run.assert_not_called()

    def test_slow_upgrade_is_not_bound_to_120_second_automatic_path_timeout(self, state_dir: Path) -> None:
        """A slow-but-successful interactive upgrade must run under a timeout that honors the
        documented 30-minute (1800s) contract, not merely anything above the automatic path's
        120s bound."""

        def fake_subprocess_run(*args: object, **kwargs: object) -> MagicMock:
            # A real slow upgrade would still be running past the automatic path's 120s
            # bound and beyond; simulate that by raising the real timeout error for any
            # finite timeout below the 1800s contract, and only succeeding once the caller
            # waits at least that long (or passes no timeout at all).
            timeout = kwargs.get("timeout")
            if timeout is None:
                return MagicMock(returncode=0)
            assert isinstance(timeout, (int, float))
            if timeout < 1800:
                cmd = args[0]
                assert isinstance(cmd, tuple)
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
            return MagicMock(returncode=0)

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.os") as mock_os,
        ):
            mock_sub.run.side_effect = fake_subprocess_run

            result = run_update_interactive("0.7.0", "0.8.0", _uv_tool_installer(), state_dir=state_dir)

        assert result == 0
        mock_os.execvp.assert_not_called()


class TestRunUpdateUnknownInstaller:
    def test_logs_notification_only(self, state_dir: Path) -> None:
        installer = InstallerInfo(method="unknown", upgrade_command=None)

        with (
            patch("buvis.pybase.updater.executor.subprocess") as mock_sub,
            patch("buvis.pybase.updater.executor.append_log") as mock_log,
        ):
            run_update("0.7.0", "0.8.0", installer, state_dir=state_dir)

        mock_sub.run.assert_not_called()
        log_calls = [call.args for call in mock_log.call_args_list]
        assert any("0.8.0" in msg and "0.7.0" in msg for _, _, msg in log_calls)
