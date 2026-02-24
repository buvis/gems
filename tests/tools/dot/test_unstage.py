from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from dot.commands.unstage.unstage import CommandUnstage


class TestCommandUnstageInit:
    def test_init_sets_env_and_alias(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr("dot.commands.unstage.unstage.Path.home", staticmethod(lambda: tmp_path))
        shell = MagicMock()

        cmd = CommandUnstage(shell=shell)

        import os

        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.shell is shell


class TestCommandUnstageExecute:
    def test_unstage_all(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "")

        cmd = CommandUnstage(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "All files unstaged"
        shell.exe.assert_called_once_with("cfg reset HEAD", dotfiles_root)

    def test_unstage_specific_file(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "")

        cmd = CommandUnstage(shell=shell, file_path=".bashrc")
        result = cmd.execute()

        assert result.success
        assert result.output == ".bashrc unstaged"
        shell.exe.assert_called_once_with("cfg reset HEAD -- .bashrc", dotfiles_root)

    def test_unstage_file_with_spaces(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "")

        cmd = CommandUnstage(shell=shell, file_path="my file.txt")
        result = cmd.execute()

        assert result.success
        command = shell.exe.call_args.args[0]
        assert "'my file.txt'" in command

    def test_fails_on_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("reset error", "")

        cmd = CommandUnstage(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert "Unstage failed" in result.error
