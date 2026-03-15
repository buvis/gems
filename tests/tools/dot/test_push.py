from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from dot.commands.push.push import CommandPush


class TestCommandPushInit:
    def test_init_sets_env_and_alias(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr("dot.commands.push.push.Path.home", staticmethod(lambda: tmp_path))
        shell = MagicMock()

        cmd = CommandPush(shell=shell)

        import os

        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.shell is shell


class TestCommandPushExecute:
    def test_execute_pushes_when_unpushed_commits(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.side_effect = [("", "1"), ("", "")]

        cmd = CommandPush(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "Changes pushed"
        assert shell.exe.call_count == 2

    def test_execute_nothing_to_push(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "0")

        cmd = CommandPush(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "Nothing to push"
        shell.exe.assert_called_once()

    def test_execute_fails_on_push_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.side_effect = [("", "2"), ("push error", "")]

        cmd = CommandPush(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Push failed")

    def test_execute_pushes_when_revlist_errors(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.side_effect = [("no upstream", ""), ("", "")]

        cmd = CommandPush(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "Changes pushed"
        assert shell.exe.call_count == 2

    def test_execute_nothing_to_push_when_no_output(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "")

        cmd = CommandPush(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "Nothing to push"
