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
    def test_execute_pushes_successfully(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "")

        cmd = CommandPush(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "Changes pushed"

    def test_execute_fails_on_push_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("push error", "")

        cmd = CommandPush(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Push failed")
