from __future__ import annotations

import subprocess

import pytest
from buvis.pybase.result import FatalError

from sysup.commands.mac.mac import CommandMac


class TestCommandMac:
    @staticmethod
    def _result(args: list[str], returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=returncode, stdout="", stderr=stderr)

    def test_all_steps_succeed(self, mocker) -> None:
        mocker.patch(
            "sysup.commands.mac.mac.shutil.which",
            side_effect=lambda name: f"/usr/local/bin/{name}",
        )
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"]),
            self._result(["/usr/local/bin/brew", "upgrade"]),
            self._result(["/usr/local/bin/brew", "cleanup"]),
            self._result(["/usr/local/bin/mise", "upgrade"]),
            self._result(["/usr/local/bin/npm-check", "-gu"]),
            self._result(["/usr/local/bin/uv", "tool", "upgrade", "--all"]),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = CommandMac().execute()

        labels = [s.label for s in steps if s.success]
        assert "brew" in labels
        assert "mise" in labels
        assert "npm-check" in labels
        assert "uv tools" in labels
        assert "helm repos" in labels

    def test_brew_missing_raises(self, mocker) -> None:
        mocker.patch("sysup.commands.mac.mac.shutil.which", return_value=None)

        with pytest.raises(FatalError, match="brew not found"):
            CommandMac().execute()

    def test_brew_update_fails(self, mocker) -> None:
        mocker.patch(
            "sysup.commands.mac.mac.shutil.which",
            side_effect=lambda name: f"/usr/local/bin/{name}",
        )
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"], returncode=1, stderr="boom"),
            self._result(["/usr/local/bin/mise", "upgrade"]),
            self._result(["/usr/local/bin/npm-check", "-gu"]),
            self._result(["/usr/local/bin/uv", "tool", "upgrade", "--all"]),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = CommandMac().execute()

        brew_step = next(s for s in steps if s.label == "brew")
        assert brew_step.success is False
        assert "boom" in brew_step.message

    def test_optional_tool_missing_continues(self, mocker) -> None:
        mapping = {
            "brew": "/usr/local/bin/brew",
            "npm-check": "/usr/local/bin/npm-check",
            "uv": "/usr/local/bin/uv",
            "helm": "/usr/local/bin/helm",
        }
        mocker.patch("sysup.commands.mac.mac.shutil.which", side_effect=lambda name: mapping.get(name))
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"]),
            self._result(["/usr/local/bin/brew", "upgrade"]),
            self._result(["/usr/local/bin/brew", "cleanup"]),
            self._result(["/usr/local/bin/npm-check", "-gu"]),
            self._result(["/usr/local/bin/uv", "tool", "upgrade", "--all"]),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = CommandMac().execute()

        mise_step = next(s for s in steps if s.label == "mise")
        assert mise_step.success is False
        assert "not found" in mise_step.message
        assert any(s.label == "uv tools" and s.success for s in steps)
        assert any(s.label == "helm repos" and s.success for s in steps)

    def test_optional_tool_fails_continues(self, mocker) -> None:
        mocker.patch(
            "sysup.commands.mac.mac.shutil.which",
            side_effect=lambda name: f"/usr/local/bin/{name}",
        )
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"]),
            self._result(["/usr/local/bin/brew", "upgrade"]),
            self._result(["/usr/local/bin/brew", "cleanup"]),
            self._result(["/usr/local/bin/mise", "upgrade"], returncode=1, stderr="mise broken"),
            self._result(["/usr/local/bin/npm-check", "-gu"]),
            self._result(["/usr/local/bin/uv", "tool", "upgrade", "--all"]),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = CommandMac().execute()

        mise_step = next(s for s in steps if s.label == "mise")
        assert mise_step.success is False
        assert "mise broken" in mise_step.message
        assert any(s.label == "uv tools" and s.success for s in steps)

    def test_npm_check_interactive(self, mocker) -> None:
        mocker.patch(
            "sysup.commands.mac.mac.shutil.which",
            side_effect=lambda name: f"/usr/local/bin/{name}",
        )
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"]),
            self._result(["/usr/local/bin/brew", "upgrade"]),
            self._result(["/usr/local/bin/brew", "cleanup"]),
            self._result(["/usr/local/bin/mise", "upgrade"]),
            self._result(["/usr/local/bin/npm-check", "-gu"]),
            self._result(["/usr/local/bin/uv", "tool", "upgrade", "--all"]),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        CommandMac().execute()

        npm_call = next(
            call_item
            for call_item in mock_run.call_args_list
            if call_item.args[0] == ["/usr/local/bin/npm-check", "-gu"]
        )
        assert npm_call.kwargs == {"check": False}

    def test_brew_upgrade_fails_breaks_loop(self, mocker) -> None:
        """When brew upgrade (second step) fails, cleanup is skipped."""
        mocker.patch(
            "sysup.commands.mac.mac.shutil.which",
            side_effect=lambda name: f"/usr/local/bin/{name}",
        )
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"]),
            self._result(["/usr/local/bin/brew", "upgrade"], returncode=1, stderr="upgrade fail"),
            # cleanup is skipped due to break
            self._result(["/usr/local/bin/mise", "upgrade"]),
            self._result(["/usr/local/bin/npm-check", "-gu"]),
            self._result(["/usr/local/bin/uv", "tool", "upgrade", "--all"]),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = CommandMac().execute()

        brew_step = next(s for s in steps if s.label == "brew")
        assert brew_step.success is False
        assert "upgrade fail" in brew_step.message

    def test_brew_cleanup_fails(self, mocker) -> None:
        mocker.patch(
            "sysup.commands.mac.mac.shutil.which",
            side_effect=lambda name: f"/usr/local/bin/{name}",
        )
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"]),
            self._result(["/usr/local/bin/brew", "upgrade"]),
            self._result(["/usr/local/bin/brew", "cleanup"], returncode=1, stderr="cleanup fail"),
            self._result(["/usr/local/bin/mise", "upgrade"]),
            self._result(["/usr/local/bin/npm-check", "-gu"]),
            self._result(["/usr/local/bin/uv", "tool", "upgrade", "--all"]),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = CommandMac().execute()

        brew_step = next(s for s in steps if s.label == "brew")
        assert brew_step.success is False
        assert "cleanup fail" in brew_step.message

    def test_brew_fails_empty_stderr_uses_unknown(self, mocker) -> None:
        mocker.patch(
            "sysup.commands.mac.mac.shutil.which",
            side_effect=lambda name: f"/usr/local/bin/{name}",
        )
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"], returncode=1, stderr=""),
            self._result(["/usr/local/bin/mise", "upgrade"]),
            self._result(["/usr/local/bin/npm-check", "-gu"]),
            self._result(["/usr/local/bin/uv", "tool", "upgrade", "--all"]),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = CommandMac().execute()

        brew_step = next(s for s in steps if s.label == "brew")
        assert brew_step.success is False
        assert "unknown error" in brew_step.message

    def test_optional_fails_empty_stderr_uses_unknown(self, mocker) -> None:
        mocker.patch(
            "sysup.commands.mac.mac.shutil.which",
            side_effect=lambda name: f"/usr/local/bin/{name}",
        )
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"]),
            self._result(["/usr/local/bin/brew", "upgrade"]),
            self._result(["/usr/local/bin/brew", "cleanup"]),
            self._result(["/usr/local/bin/mise", "upgrade"], returncode=1, stderr=""),
            self._result(["/usr/local/bin/npm-check", "-gu"]),
            self._result(["/usr/local/bin/uv", "tool", "upgrade", "--all"]),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = CommandMac().execute()

        mise_step = next(s for s in steps if s.label == "mise")
        assert mise_step.success is False
        assert "unknown error" in mise_step.message

    def test_npm_check_missing(self, mocker) -> None:
        mapping = {
            "brew": "/usr/local/bin/brew",
            "mise": "/usr/local/bin/mise",
            "uv": "/usr/local/bin/uv",
            "helm": "/usr/local/bin/helm",
        }
        mocker.patch("sysup.commands.mac.mac.shutil.which", side_effect=lambda name: mapping.get(name))
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"]),
            self._result(["/usr/local/bin/brew", "upgrade"]),
            self._result(["/usr/local/bin/brew", "cleanup"]),
            self._result(["/usr/local/bin/mise", "upgrade"]),
            self._result(["/usr/local/bin/uv", "tool", "upgrade", "--all"]),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = CommandMac().execute()

        npm_step = next(s for s in steps if s.label == "npm-check")
        assert npm_step.success is False
        assert "not found" in npm_step.message

    def test_npm_check_interactive_fails(self, mocker) -> None:
        mocker.patch(
            "sysup.commands.mac.mac.shutil.which",
            side_effect=lambda name: f"/usr/local/bin/{name}",
        )
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"]),
            self._result(["/usr/local/bin/brew", "upgrade"]),
            self._result(["/usr/local/bin/brew", "cleanup"]),
            self._result(["/usr/local/bin/mise", "upgrade"]),
            subprocess.CompletedProcess(
                args=["/usr/local/bin/npm-check", "-gu"], returncode=1, stdout=None, stderr=None
            ),
            self._result(["/usr/local/bin/uv", "tool", "upgrade", "--all"]),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = CommandMac().execute()

        npm_step = next(s for s in steps if s.label == "npm-check")
        assert npm_step.success is False
        assert "exit code 1" in npm_step.message

    def test_helm_fails(self, mocker) -> None:
        mocker.patch(
            "sysup.commands.mac.mac.shutil.which",
            side_effect=lambda name: f"/usr/local/bin/{name}",
        )
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"]),
            self._result(["/usr/local/bin/brew", "upgrade"]),
            self._result(["/usr/local/bin/brew", "cleanup"]),
            self._result(["/usr/local/bin/mise", "upgrade"]),
            self._result(["/usr/local/bin/npm-check", "-gu"]),
            self._result(["/usr/local/bin/uv", "tool", "upgrade", "--all"]),
            self._result(["/usr/local/bin/helm", "repo", "update"], returncode=1, stderr="helm error"),
        ]

        steps = CommandMac().execute()

        helm_step = next(s for s in steps if s.label == "helm repos")
        assert helm_step.success is False
        assert "helm error" in helm_step.message

    def test_uv_missing(self, mocker) -> None:
        mapping = {
            "brew": "/usr/local/bin/brew",
            "mise": "/usr/local/bin/mise",
            "npm-check": "/usr/local/bin/npm-check",
            "helm": "/usr/local/bin/helm",
        }
        mocker.patch("sysup.commands.mac.mac.shutil.which", side_effect=lambda name: mapping.get(name))
        mock_run = mocker.patch("sysup.commands.mac.mac.subprocess.run")
        mock_pip = mocker.patch("sysup.commands.pip.pip.CommandPip")
        mock_pip.return_value.execute.return_value = []
        mock_run.side_effect = [
            self._result(["/usr/local/bin/brew", "update"]),
            self._result(["/usr/local/bin/brew", "upgrade"]),
            self._result(["/usr/local/bin/brew", "cleanup"]),
            self._result(["/usr/local/bin/mise", "upgrade"]),
            self._result(["/usr/local/bin/npm-check", "-gu"]),
            self._result(["/usr/local/bin/helm", "repo", "update"]),
        ]

        steps = CommandMac().execute()

        uv_step = next(s for s in steps if s.label == "uv tools")
        assert uv_step.success is False
        assert "not found" in uv_step.message
