from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from dot.commands.commit.commit import CommandCommit


class TestCommandCommitInit:
    def test_init_sets_env_and_alias(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr("dot.commands.commit.commit.Path.home", staticmethod(lambda: tmp_path))
        shell = MagicMock()

        cmd = CommandCommit(shell=shell, message="message")

        import os

        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.shell is shell
        assert cmd.message == "message"


class TestCommandCommitExecute:
    def test_execute_commits_without_git_secret(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "")

        cmd = CommandCommit(shell=shell, message="message")
        result = cmd.execute()

        assert result.success
        assert result.output == "Changes committed"
        assert result.warnings == []

    def test_execute_commits_with_git_secret_success(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [("", ""), ("", "")]

        cmd = CommandCommit(shell=shell, message="message")
        result = cmd.execute()

        assert result.success
        assert result.warnings == []
        assert shell.exe.call_count == 2
        shell.exe.assert_any_call("cfg secret hide -m", dotfiles_root)

    def test_execute_fails_on_git_secret_failure(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [("secret err", "details")]

        cmd = CommandCommit(shell=shell, message="message")
        result = cmd.execute()

        assert not result.success
        assert "Error hiding secrets" in result.error

    def test_execute_fails_on_commit_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("commit error", "")

        cmd = CommandCommit(shell=shell, message="message")
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Commit failed")

    def test_execute_quotes_message(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("", "")

        cmd = CommandCommit(shell=shell, message="hello world")
        result = cmd.execute()

        assert result.success
        command = shell.exe.call_args.args[0]
        assert "'hello world'" in command
