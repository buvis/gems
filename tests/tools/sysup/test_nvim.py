from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from buvis.pybase.result import FatalError

from sysup.commands.nvim.nvim import CommandNvim


class TestCommandNvim:
    @staticmethod
    def _result(returncode: int = 0, stderr: str = "", stdout: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)

    def test_all_steps_succeed(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [self._result(), self._result(), self._result()]

        steps = list(CommandNvim().execute())

        assert len(steps) == 3
        assert all(s.success for s in steps)
        assert [s.label for s in steps] == ["lazy", "mason", "treesitter"]

    def test_nvim_missing_raises(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value=None)

        with pytest.raises(FatalError, match="nvim not found"):
            list(CommandNvim().execute())

    def test_lazy_fails_continues(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [
            self._result(returncode=1, stderr="lazy error"),
            self._result(),
            self._result(),
        ]

        steps = list(CommandNvim().execute())

        assert not steps[0].success
        assert "lazy error" in steps[0].message
        assert steps[1].success
        assert steps[2].success
        assert mock_run.call_count == 3

    def test_mason_fails_continues(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [
            self._result(),
            self._result(returncode=1, stderr="mason error"),
            self._result(),
        ]

        steps = list(CommandNvim().execute())

        assert steps[0].success
        assert not steps[1].success
        assert "mason error" in steps[1].message
        assert steps[2].success

    def test_treesitter_fails(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [
            self._result(),
            self._result(),
            self._result(returncode=1, stderr="ts error"),
        ]

        steps = list(CommandNvim().execute())

        assert steps[0].success
        assert steps[1].success
        assert not steps[2].success
        assert "ts error" in steps[2].message

    def test_mason_timeout(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [
            self._result(),
            subprocess.TimeoutExpired(cmd="nvim", timeout=300),
            self._result(),
        ]

        steps = list(CommandNvim().execute())

        assert steps[0].success
        assert not steps[1].success
        assert "timed out" in steps[1].message
        assert steps[2].success

    def test_mason_timeout_includes_captured_output(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        exc = subprocess.TimeoutExpired(cmd="nvim", timeout=300)
        exc.stderr = b"Installing lua-language-server\n"
        mock_run.side_effect = [self._result(), exc, self._result()]

        steps = list(CommandNvim().execute())

        assert "timed out" in steps[1].message
        assert "lua-language-server" in steps[1].message

    def test_lazy_fails_empty_stderr(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [
            self._result(returncode=1, stderr=""),
            self._result(),
            self._result(),
        ]

        steps = list(CommandNvim().execute())

        assert "unknown error" in steps[0].message

    def test_mason_fails_empty_stderr(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [
            self._result(),
            self._result(returncode=1, stderr=""),
            self._result(),
        ]

        steps = list(CommandNvim().execute())

        assert "unknown error" in steps[1].message

    def test_treesitter_fails_empty_stderr(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [
            self._result(),
            self._result(),
            self._result(returncode=1, stderr=""),
        ]

        steps = list(CommandNvim().execute())

        assert "unknown error" in steps[2].message

    def test_mason_invocation_force_loads_plugins_and_uses_sync(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run", return_value=self._result())

        list(CommandNvim().execute())

        mason_args = mock_run.call_args_list[1].args[0]
        assert "Lazy load mason.nvim mason-tool-installer.nvim" in mason_args
        assert "MasonToolsUpdateSync" in mason_args
        assert "+qa" in mason_args
        assert not any("MasonToolsUpdateCompleted" in a for a in mason_args)
        assert mock_run.call_args_list[1].kwargs["timeout"] == CommandNvim.MASON_TIMEOUT
        assert CommandNvim.MASON_TIMEOUT == 600
        # Probe block: one -c argument must reference mason-registry and emit mason FAIL/OK lines
        probe_args = [a for a in mason_args if "mason-registry" in a]
        assert probe_args, "expected a -c arg running a Lua probe over mason-registry"
        probe = probe_args[0]
        assert "mason FAIL" in probe
        assert "mason OK" in probe
        assert "ensure_installed" in probe

    def test_mason_all_tools_installed_succeeds_silently(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [
            self._result(),
            self._result(stdout="mason OK foo\nmason OK bar\n"),
            self._result(),
        ]

        steps = list(CommandNvim().execute())

        assert steps[1].success
        assert steps[1].message == ""

    def test_mason_failed_tools_reported_as_step_failure(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch.object(CommandNvim, "_read_mason_log_tail", return_value="some log content")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [
            self._result(),
            self._result(stdout="mason OK foo\nmason FAIL terraform-ls\nmason FAIL ast-grep\n"),
            self._result(),
        ]

        steps = list(CommandNvim().execute())

        assert not steps[1].success
        assert "terraform-ls" in steps[1].message
        assert "ast-grep" in steps[1].message
        assert "some log content" in steps[1].message

    def test_mason_inconclusive_is_non_fatal(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [
            self._result(),
            self._result(stdout="mason INCONCLUSIVE mason-tool-installer config unavailable\n"),
            self._result(),
        ]

        steps = list(CommandNvim().execute())

        assert steps[1].success
        assert "INCONCLUSIVE" in steps[1].message

    def test_mason_no_probe_output_is_inconclusive(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [self._result(), self._result(stdout=""), self._result()]

        steps = list(CommandNvim().execute())

        assert steps[1].success
        assert "INCONCLUSIVE" in steps[1].message

    def test_mason_nonzero_returncode_includes_stdout_and_stderr(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        mock_run.side_effect = [
            self._result(),
            self._result(returncode=1, stdout="stdout line", stderr="stderr line"),
            self._result(),
        ]

        steps = list(CommandNvim().execute())

        assert not steps[1].success
        assert "stdout line" in steps[1].message
        assert "stderr line" in steps[1].message

    def test_mason_timeout_includes_log_tail(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch.object(CommandNvim, "_read_mason_log_tail", return_value="tail text")
        mock_run = mocker.patch("sysup.commands.nvim.nvim.subprocess.run")
        exc = subprocess.TimeoutExpired(cmd="nvim", timeout=300)
        exc.stderr = b"installing foo\n"
        mock_run.side_effect = [self._result(), exc, self._result()]

        steps = list(CommandNvim().execute())

        assert not steps[1].success
        assert "timed out" in steps[1].message
        assert "installing foo" in steps[1].message
        assert "tail text" in steps[1].message

    def test_read_mason_log_tail_missing_file(self, mocker, tmp_path: Path) -> None:
        mocker.patch.dict(
            "sysup.commands.nvim.nvim.os.environ",
            {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "missing")},
            clear=False,
        )

        assert CommandNvim()._read_mason_log_tail() == ""

    def test_read_mason_log_tail_truncates_to_8kib(self, mocker, tmp_path: Path) -> None:
        state_dir = tmp_path / "nvim"
        state_dir.mkdir()
        log = state_dir / "mason.log"
        line = "a" * 100 + "\n"
        log.write_text(line * 300)
        mocker.patch.dict(
            "sysup.commands.nvim.nvim.os.environ",
            {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path)},
            clear=False,
        )

        tail = CommandNvim()._read_mason_log_tail()

        assert tail
        assert len(tail.encode()) <= 8192

    def test_read_mason_log_tail_keeps_last_200_lines(self, mocker, tmp_path: Path) -> None:
        state_dir = tmp_path / "nvim"
        state_dir.mkdir()
        log = state_dir / "mason.log"
        log.write_text("\n".join(str(i) for i in range(1, 501)) + "\n")
        mocker.patch.dict(
            "sysup.commands.nvim.nvim.os.environ",
            {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path)},
            clear=False,
        )

        tail = CommandNvim()._read_mason_log_tail()

        lines = tail.splitlines()
        assert "500" in lines
        assert "301" in lines
        assert "300" not in lines

    def test_on_step_start_callback(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch("sysup.commands.nvim.nvim.subprocess.run", return_value=self._result())
        started: list[str] = []

        list(CommandNvim().execute(on_step_start=started.append))

        assert started == ["lazy", "mason", "treesitter"]
