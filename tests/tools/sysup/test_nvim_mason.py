from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from buvis.pybase.result import FatalError

from sysup.capabilities.nvim_mason import NvimMason


class TestNvimMason:
    @staticmethod
    def _result(returncode: int = 0, stderr: str = "", stdout: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)

    def test_nvim_missing_raises(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value=None)
        with pytest.raises(FatalError, match="nvim not found"):
            list(NvimMason().run())

    def test_invocation_force_loads_plugins_and_uses_sync(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.capabilities.nvim_mason.subprocess.run", return_value=self._result())

        list(NvimMason().run())

        mason_args = mock_run.call_args_list[0].args[0]
        assert "Lazy load mason.nvim mason-tool-installer.nvim" in mason_args
        assert "MasonToolsUpdateSync" in mason_args
        assert "+qa" in mason_args
        assert mock_run.call_args_list[0].kwargs["timeout"] == 600
        listener_args = [a for a in mason_args if "package:install:failed" in a]
        assert listener_args
        listener = listener_args[0]
        assert "mason-registry" in listener
        assert "_sysup_mason_failed" in listener
        report_args = [a for a in mason_args if "mason DONE" in a]
        assert report_args
        report = report_args[0]
        assert "mason FAIL" in report
        assert "_sysup_mason_failed" in report
        listener_idx = mason_args.index(listener)
        sync_idx = mason_args.index("MasonToolsUpdateSync")
        report_idx = mason_args.index(report)
        assert listener_idx < sync_idx < report_idx

    def test_timeout_input_overrides_default(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value="/usr/local/bin/nvim")
        mock_run = mocker.patch("sysup.capabilities.nvim_mason.subprocess.run", return_value=self._result())

        list(NvimMason().run(timeout=42))

        assert mock_run.call_args_list[0].kwargs["timeout"] == 42

    def test_default_timeout_is_600(self) -> None:
        assert dict(NvimMason().inputs) == {"timeout": 600}

    def test_all_tools_installed_succeeds_silently(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch("sysup.capabilities.nvim_mason.subprocess.run", return_value=self._result(stdout="mason DONE\n"))

        steps = list(NvimMason().run())

        assert steps[0].success
        assert steps[0].message == ""

    def test_failed_tools_reported_with_log_tail(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch.object(NvimMason, "_read_mason_log_tail", return_value="some log content")
        mocker.patch(
            "sysup.capabilities.nvim_mason.subprocess.run",
            return_value=self._result(stdout="mason FAIL terraform-ls\nmason FAIL ast-grep\nmason DONE\n"),
        )

        steps = list(NvimMason().run())

        assert not steps[0].success
        assert "terraform-ls" in steps[0].message
        assert "ast-grep" in steps[0].message
        assert "some log content" in steps[0].message

    def test_inconclusive_is_non_fatal(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch(
            "sysup.capabilities.nvim_mason.subprocess.run",
            return_value=self._result(stdout="mason INCONCLUSIVE mason-registry unavailable\n"),
        )

        steps = list(NvimMason().run())

        assert steps[0].success
        assert "mason-registry unavailable" in steps[0].message

    def test_no_probe_output_is_inconclusive(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch("sysup.capabilities.nvim_mason.subprocess.run", return_value=self._result(stdout=""))

        steps = list(NvimMason().run())

        assert steps[0].success
        assert "INCONCLUSIVE" in steps[0].message

    def test_reads_probe_output_from_stderr(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch.object(NvimMason, "_read_mason_log_tail", return_value="")
        mocker.patch(
            "sysup.capabilities.nvim_mason.subprocess.run",
            return_value=self._result(stdout="", stderr="mason FAIL bar\nmason DONE\n"),
        )

        steps = list(NvimMason().run())

        assert not steps[0].success
        assert "bar" in steps[0].message

    def test_timeout_includes_captured_output_and_log_tail(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch.object(NvimMason, "_read_mason_log_tail", return_value="tail text")
        exc = subprocess.TimeoutExpired(cmd="nvim", timeout=600)
        exc.stderr = b"installing foo\n"
        mocker.patch("sysup.capabilities.nvim_mason.subprocess.run", side_effect=exc)

        steps = list(NvimMason().run())

        assert not steps[0].success
        assert "timed out" in steps[0].message
        assert "installing foo" in steps[0].message
        assert "tail text" in steps[0].message

    def test_timeout_strips_ansi_from_captured_output(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch.object(NvimMason, "_read_mason_log_tail", return_value="")
        exc = subprocess.TimeoutExpired(cmd="nvim", timeout=600)
        exc.stdout = b"\x1b]1337;SetUserVar=IS_NVIM=dHJ1ZQ==\x07installing foo\n"
        mocker.patch("sysup.capabilities.nvim_mason.subprocess.run", side_effect=exc)

        steps = list(NvimMason().run())

        assert not steps[0].success
        assert "installing foo" in steps[0].message
        assert "1337" not in steps[0].message

    def test_strips_iterm_osc_around_sentinel(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch.object(NvimMason, "_read_mason_log_tail", return_value="")
        osc_open = "\x1b]1337;SetUserVar=IS_NVIM=dHJ1ZQ==\x07"
        osc_close = "\x1b]1337;SetUserVar=IS_NVIM=ZmFsc2U=\x07"
        mocker.patch(
            "sysup.capabilities.nvim_mason.subprocess.run",
            return_value=self._result(stderr=f"{osc_open}mason FAIL terraform-ls\nmason DONE{osc_close}"),
        )

        steps = list(NvimMason().run())

        assert not steps[0].success
        assert "terraform-ls" in steps[0].message

    def test_nonzero_returncode_includes_stdout_and_stderr(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch(
            "sysup.capabilities.nvim_mason.subprocess.run",
            return_value=self._result(returncode=1, stdout="stdout line", stderr="stderr line"),
        )

        steps = list(NvimMason().run())

        assert not steps[0].success
        assert "stdout line" in steps[0].message
        assert "stderr line" in steps[0].message

    def test_oserror_becomes_failed_step(self, mocker) -> None:
        mocker.patch("sysup.capabilities.nvim_mason.shutil.which", return_value="/usr/local/bin/nvim")
        mocker.patch(
            "sysup.capabilities.nvim_mason.subprocess.run",
            side_effect=FileNotFoundError(2, "No such file or directory"),
        )

        steps = list(NvimMason().run())

        assert not steps[0].success
        assert "mason update failed" in steps[0].message

    def test_read_mason_log_tail_missing_file(self, mocker, tmp_path: Path) -> None:
        mocker.patch.dict(
            "sysup.capabilities.nvim_mason.os.environ",
            {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "missing")},
            clear=False,
        )
        assert NvimMason()._read_mason_log_tail() == ""

    def test_read_mason_log_tail_truncates_to_8kib(self, mocker, tmp_path: Path) -> None:
        state_dir = tmp_path / "nvim"
        state_dir.mkdir()
        (state_dir / "mason.log").write_text(("a" * 100 + "\n") * 300)
        mocker.patch.dict(
            "sysup.capabilities.nvim_mason.os.environ",
            {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path)},
            clear=False,
        )
        tail = NvimMason()._read_mason_log_tail()
        assert tail
        assert len(tail.encode()) <= 8192

    def test_read_mason_log_tail_keeps_last_200_lines(self, mocker, tmp_path: Path) -> None:
        state_dir = tmp_path / "nvim"
        state_dir.mkdir()
        (state_dir / "mason.log").write_text("\n".join(str(i) for i in range(1, 501)) + "\n")
        mocker.patch.dict(
            "sysup.capabilities.nvim_mason.os.environ",
            {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path)},
            clear=False,
        )
        lines = NvimMason()._read_mason_log_tail().splitlines()
        assert "500" in lines
        assert "301" in lines
        assert "300" not in lines
