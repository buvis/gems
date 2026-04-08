from __future__ import annotations

import subprocess

import pytest
from buvis.pybase.result import FatalError

from sysup.commands.nvim.nvim import CommandNvim


class TestCommandNvim:
    @staticmethod
    def _result(returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr=stderr)

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

    def test_on_step_start_callback(self, mocker) -> None:
        mocker.patch("sysup.commands.nvim.nvim.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch("sysup.commands.nvim.nvim.subprocess.run", return_value=self._result())
        started: list[str] = []

        list(CommandNvim().execute(on_step_start=started.append))

        assert started == ["lazy", "mason", "treesitter"]
