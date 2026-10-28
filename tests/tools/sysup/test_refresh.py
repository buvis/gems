from __future__ import annotations

import subprocess

import pytest

from sysup.config import RefreshSpec
from sysup.refresh import run_refresh


def _ok(returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr="")


def _spec(commands: list[object], instructions: str = "do it") -> RefreshSpec:
    return RefreshSpec.model_validate({"instructions": instructions, "commands": commands})


class TestRunRefresh:
    def test_shell_line_command_runs_through_bash(self, mocker) -> None:
        mocker.patch("sysup.refresh.shutil.which", side_effect=lambda n: "/bin/" + n)
        run = mocker.patch("sysup.refresh.subprocess.run", return_value=_ok())

        run_refresh("item", _spec(["gh auth status | head -1"]), lambda: "tok")

        assert run.call_args.args[0] == ["/bin/bash", "-eo", "pipefail", "-c", "gh auth status | head -1"]

    def test_secret_goes_only_to_stdin_of_the_declaring_command(self, mocker) -> None:
        mocker.patch("sysup.refresh.shutil.which", side_effect=lambda n: "/bin/" + n)
        run = mocker.patch("sysup.refresh.subprocess.run", return_value=_ok())
        spec = _spec(
            [
                {"argv": ["echo", "hello"]},
                {"argv": ["gh", "auth", "login", "--with-token"], "env": {"GH_CONFIG_DIR": "/c"}, "stdin": "secret"},
            ]
        )

        result = run_refresh("gh-agent", spec, lambda: "tok")

        assert result.success is True
        assert result.kind == "item"
        first, second = run.call_args_list
        assert "input" not in first.kwargs
        assert second.kwargs["input"] == "tok"
        for call in run.call_args_list:
            assert "tok" not in call.args[0]
            assert all("tok" not in value for value in call.kwargs["env"].values())

    def test_no_secret_prompt_without_stdin_secret(self, mocker) -> None:
        mocker.patch("sysup.refresh.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.refresh.subprocess.run", return_value=_ok())
        reader = mocker.MagicMock(return_value="tok")
        spec = _spec([{"argv": ["echo", "hi"]}])

        run_refresh("item", spec, reader)

        reader.assert_not_called()

    def test_failed_command_stops_and_reports_exit_code(self, mocker) -> None:
        mocker.patch("sysup.refresh.shutil.which", side_effect=lambda n: "/bin/" + n)
        run = mocker.patch("sysup.refresh.subprocess.run", side_effect=[_ok(returncode=1), _ok()])
        spec = _spec([{"argv": ["gh", "auth", "login"]}, {"argv": ["echo", "after"]}])

        result = run_refresh("gh-agent", spec, lambda: "tok")

        assert result.success is False
        assert result.message == "gh auth login failed: exit code 1"
        assert run.call_count == 1

    def test_missing_binary_reports_not_found(self, mocker) -> None:
        mocker.patch("sysup.refresh.shutil.which", return_value=None)
        run = mocker.patch("sysup.refresh.subprocess.run")
        spec = _spec([{"argv": ["ghost", "run"]}])

        result = run_refresh("item", spec, lambda: "tok")

        assert result.success is False
        assert result.message == "ghost not found"
        assert run.call_count == 0

    def test_env_values_are_tilde_expanded(self, mocker, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        mocker.patch("sysup.refresh.shutil.which", side_effect=lambda n: "/bin/" + n)
        run = mocker.patch("sysup.refresh.subprocess.run", return_value=_ok())
        spec = _spec([{"argv": ["gh", "auth"], "env": {"GH_CONFIG_DIR": "~/.config/gh-agent"}}])

        run_refresh("gh-agent", spec, lambda: "tok")

        env = run.call_args.kwargs["env"]
        assert env["GH_CONFIG_DIR"] == str(tmp_path / ".config/gh-agent")

    @pytest.mark.parametrize(
        "argv",
        [
            ["gh", "auth", "login", "--hostname", "github.com", "--with-token", "--insecure-storage"],
            "gh auth login --hostname github.com --with-token --insecure-storage",
        ],
    )
    def test_gh_refresh_ignores_ambient_auth_and_host(self, mocker, monkeypatch, tmp_path, argv: object) -> None:
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST"):
            monkeypatch.setenv(name, f"synthetic-{name}")
        monkeypatch.setenv("HOME", str(tmp_path))
        mocker.patch("sysup.refresh.shutil.which", side_effect=lambda n: "/bin/" + n)
        run = mocker.patch("sysup.refresh.subprocess.run", return_value=_ok())
        spec = _spec([{"argv": argv, "env": {"GH_CONFIG_DIR": "~/.config/gh-agent"}, "stdin": "secret"}])

        run_refresh("gh-agent", spec, lambda: "tok")

        call = run.call_args
        env = call.kwargs["env"]
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST"):
            assert name not in env
        assert env["GH_CONFIG_DIR"] == str(tmp_path / ".config/gh-agent")
        assert "--hostname github.com" in " ".join(call.args[0])
        assert call.kwargs["input"] == "tok"
        import os

        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST"):
            assert os.environ[name] == f"synthetic-{name}"
