from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from dot.commands.push.push import CommandPush


class TestCommandPushInit:
    @patch("dot.commands.push.push.DotGitService")
    def test_constructs_dot_git_service_with_shell_and_dotfiles_root(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandPush(shell=shell, dotfiles_root=str(dotfiles_root))

        mock_service_cls.assert_called_once_with(shell, str(dotfiles_root))

    def test_does_not_mutate_environment(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        shell = MagicMock()

        with patch("dot.commands.push.push.DotGitService"):
            CommandPush(shell=shell, dotfiles_root=str(tmp_path))

        assert "DOTFILES_ROOT" not in os.environ

    @patch("dot.commands.push.push.DotGitService")
    def test_does_not_call_shell_alias(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandPush(shell=shell, dotfiles_root=str(dotfiles_root))

        shell.alias.assert_not_called()


class TestCommandPushExecute:
    @patch("dot.commands.push.push.DotGitService")
    def test_execute_returns_nothing_to_push_from_service(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.push.return_value = CommandResult(success=True, output="Nothing to push")
        shell = MagicMock()

        cmd = CommandPush(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        mock_service.push.assert_called_once_with()
        assert result.success
        assert result.output == "Nothing to push"

    @patch("dot.commands.push.push.DotGitService")
    def test_execute_returns_changes_pushed_from_service(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.push.return_value = CommandResult(success=True, output="Changes pushed")
        shell = MagicMock()

        cmd = CommandPush(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.output == "Changes pushed"

    @patch("dot.commands.push.push.DotGitService")
    def test_execute_returns_service_failure_passthrough(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.push.return_value = CommandResult(success=False, error="Push failed: push error")
        shell = MagicMock()

        cmd = CommandPush(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert not result.success
        assert result.error == "Push failed: push error"

    @patch("dot.commands.push.push.DotGitService")
    def test_execute_never_calls_shell_directly(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.push.return_value = CommandResult(success=True, output="Nothing to push")
        shell = MagicMock()

        cmd = CommandPush(shell=shell, dotfiles_root=str(dotfiles_root))
        cmd.execute()

        shell.exe.assert_not_called()
        shell.interact.assert_not_called()
        shell.alias.assert_not_called()
