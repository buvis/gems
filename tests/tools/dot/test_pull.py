from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from dot.commands.pull.pull import CommandPull


class TestCommandPullInit:
    def test_init_sets_env_and_alias(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr("dot.commands.pull.pull.Path.home", staticmethod(lambda: tmp_path))
        shell = MagicMock()

        cmd = CommandPull(shell=shell)

        import os

        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.shell is shell


class TestCommandPullExecute:
    def test_execute_pulls_and_updates_submodules(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [("", ""), ("", ""), ("", ""), ("", "")]

        cmd = CommandPull(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "Dotfiles pulled successfully"
        assert shell.exe.call_count == 4
        shell.exe.assert_any_call("cfg pull", dotfiles_root)
        shell.exe.assert_any_call("cfg submodule foreach git reset --hard", dotfiles_root)
        shell.exe.assert_any_call("cfg submodule update --init", dotfiles_root)
        shell.exe.assert_any_call("cfg submodule update --remote --merge", dotfiles_root)

    def test_execute_with_git_secret_reveal(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [("", ""), ("", ""), ("", ""), ("", ""), ("", "")]

        cmd = CommandPull(shell=shell)
        result = cmd.execute()

        assert result.success
        assert shell.exe.call_count == 5
        shell.exe.assert_any_call("cfg secret reveal -f", dotfiles_root)

    def test_execute_git_secret_reveal_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [("", ""), ("", ""), ("", ""), ("", ""), ("reveal error", "")]

        cmd = CommandPull(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Secret reveal failed")

    def test_execute_fails_on_pull_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.side_effect = [("error msg", "")]

        cmd = CommandPull(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Pull failed")

    def test_execute_fails_on_submodule_reset_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.side_effect = [("", ""), ("error msg", "")]

        cmd = CommandPull(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Submodule reset failed")

    def test_execute_fails_on_submodule_init_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.side_effect = [("", ""), ("", ""), ("error msg", "")]

        cmd = CommandPull(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Submodule init failed")

    def test_execute_fails_on_submodule_update_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.side_effect = [("", ""), ("", ""), ("", ""), ("error msg", "")]

        cmd = CommandPull(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert result.error.startswith("Submodule update failed")
