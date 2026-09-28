from __future__ import annotations

import subprocess

import pytest
from postup.adapters.claude import ClaudeAdapter, ClaudeError


class _Proc:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class TestIsAvailable:
    def test_present_when_which_resolves(self, mocker):
        mocker.patch("postup.adapters.claude.shutil.which", return_value="/usr/bin/claude")
        assert ClaudeAdapter().is_available() is True

    def test_absent_when_which_returns_none(self, mocker):
        mocker.patch("postup.adapters.claude.shutil.which", return_value=None)
        assert ClaudeAdapter().is_available() is False


class TestPrompt:
    def test_returns_stripped_stdout(self, mocker):
        run = mocker.patch("postup.adapters.claude.subprocess.run", return_value=_Proc(stdout='  {"ok": 1}\n '))
        result = ClaudeAdapter().prompt("hi")
        assert result == '{"ok": 1}'
        argv = run.call_args.args[0]
        assert argv[:3] == ["claude", "-p", "hi"]

    def test_model_flag_passed_only_when_set(self, mocker):
        run = mocker.patch("postup.adapters.claude.subprocess.run", return_value=_Proc(stdout="x"))
        ClaudeAdapter().prompt("hi", model="claude-sonnet")
        assert run.call_args.args[0] == ["claude", "-p", "hi", "--model", "claude-sonnet"]

    def test_no_model_flag_when_unset(self, mocker):
        run = mocker.patch("postup.adapters.claude.subprocess.run", return_value=_Proc(stdout="x"))
        ClaudeAdapter().prompt("hi", model=None)
        assert "--model" not in run.call_args.args[0]

    def test_nonzero_exit_raises(self, mocker):
        mocker.patch("postup.adapters.claude.subprocess.run", return_value=_Proc(stderr="quota exceeded", returncode=1))
        with pytest.raises(ClaudeError, match="quota exceeded"):
            ClaudeAdapter().prompt("hi")

    def test_timeout_raises(self, mocker):
        mocker.patch(
            "postup.adapters.claude.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude -p", timeout=300),
        )
        with pytest.raises(ClaudeError):
            ClaudeAdapter().prompt("hi")

    def test_missing_binary_raises(self, mocker):
        mocker.patch("postup.adapters.claude.subprocess.run", side_effect=FileNotFoundError("claude"))
        with pytest.raises(ClaudeError):
            ClaudeAdapter().prompt("hi")

    def test_empty_output_raises(self, mocker):
        mocker.patch("postup.adapters.claude.subprocess.run", return_value=_Proc(stdout="   \n"))
        with pytest.raises(ClaudeError, match="empty response"):
            ClaudeAdapter().prompt("hi")
