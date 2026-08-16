from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from dot.commands.pull.pull import CommandPull


class TestCommandPullInit:
    @patch("dot.commands.pull.pull.DotGitService")
    def test_constructs_dot_git_service_with_shell_and_dotfiles_root(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))

        mock_service_cls.assert_called_once_with(shell, str(dotfiles_root))

    def test_does_not_mutate_environment(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        shell = MagicMock()

        with patch("dot.commands.pull.pull.DotGitService"):
            CommandPull(shell=shell, dotfiles_root=str(tmp_path))

        assert "DOTFILES_ROOT" not in os.environ

    @patch("dot.commands.pull.pull.DotGitService")
    def test_does_not_call_shell_alias(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))

        shell.alias.assert_not_called()


class TestCommandPullExecute:
    @patch("dot.commands.pull.pull.DotGitService")
    def test_execute_calls_service_pull_with_no_passphrase_and_returns_success(
        self, mock_service_cls, dotfiles_root
    ) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.pull.return_value = CommandResult(success=True, output="Dotfiles pulled successfully")
        shell = MagicMock()

        cmd = CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        mock_service.pull.assert_called_once_with(passphrase=None)
        assert result.success
        assert result.output == "Dotfiles pulled successfully"

    @patch("dot.commands.pull.pull.DotGitService")
    def test_execute_returns_service_failure_passthrough(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.pull.return_value = CommandResult(success=False, error="Pull failed: error msg")
        shell = MagicMock()

        cmd = CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert not result.success
        assert result.error == "Pull failed: error msg"

    @patch("dot.commands.pull.pull.DotGitService")
    def test_execute_never_calls_shell_directly(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.pull.return_value = CommandResult(success=True, output="Dotfiles pulled successfully")
        shell = MagicMock()

        cmd = CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))
        cmd.execute()

        shell.exe.assert_not_called()
        shell.interact.assert_not_called()
        shell.alias.assert_not_called()
