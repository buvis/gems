from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from dot.commands.commit.commit import CommandCommit


class TestCommandCommitInit:
    @patch("dot.commands.commit.commit.DotGitService")
    def test_constructs_dot_git_service_with_shell_and_dotfiles_root(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandCommit(shell=shell, dotfiles_root=str(dotfiles_root), message="message")

        mock_service_cls.assert_called_once_with(shell, str(dotfiles_root))

    def test_does_not_mutate_environment(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        shell = MagicMock()

        with patch("dot.commands.commit.commit.DotGitService"):
            CommandCommit(shell=shell, dotfiles_root=str(tmp_path), message="message")

        assert "DOTFILES_ROOT" not in os.environ

    @patch("dot.commands.commit.commit.DotGitService")
    def test_does_not_call_shell_alias(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandCommit(shell=shell, dotfiles_root=str(dotfiles_root), message="message")

        shell.alias.assert_not_called()


class TestCommandCommitExecute:
    @patch("dot.commands.commit.commit.DotGitService")
    def test_execute_commits_via_service_with_message_and_returns_success(
        self, mock_service_cls, dotfiles_root
    ) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.commit.return_value = CommandResult(success=True, output="Changes committed", warnings=[])
        shell = MagicMock()

        cmd = CommandCommit(shell=shell, dotfiles_root=str(dotfiles_root), message="my message")
        result = cmd.execute()

        mock_service.commit.assert_called_once_with("my message")
        assert result.success
        assert result.output == "Changes committed"
        assert result.warnings == []

    @patch("dot.commands.commit.commit.DotGitService")
    def test_execute_returns_service_failure_passthrough(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.commit.return_value = CommandResult(success=False, error="secret error")
        shell = MagicMock()

        cmd = CommandCommit(shell=shell, dotfiles_root=str(dotfiles_root), message="message")
        result = cmd.execute()

        assert not result.success
        assert result.error == "secret error"

    @patch("dot.commands.commit.commit.DotGitService")
    def test_execute_never_calls_shell_directly(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.commit.return_value = CommandResult(success=True, output="Changes committed", warnings=[])
        shell = MagicMock()

        cmd = CommandCommit(shell=shell, dotfiles_root=str(dotfiles_root), message="message")
        cmd.execute()

        shell.exe.assert_not_called()
        shell.interact.assert_not_called()
        shell.alias.assert_not_called()
