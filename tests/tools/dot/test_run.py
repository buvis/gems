from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from dot.commands.run.run import CommandRun


class TestCommandRunInit:
    def test_init_sets_env_and_alias(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        monkeypatch.setattr("dot.commands.run.run.Path.home", staticmethod(lambda: tmp_path))
        shell = MagicMock()

        cmd = CommandRun(shell=shell, args=("log",))

        import os

        assert os.environ["DOTFILES_ROOT"] == str(tmp_path.resolve())
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        assert cmd.args == ("log",)


class TestCommandRunExecute:
    def test_passes_args_to_cfg(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "abc123 initial commit")

        cmd = CommandRun(shell=shell, args=("log", "--oneline", "-1"))
        result = cmd.execute()

        assert result.success
        assert "abc123" in result.output
        shell.exe.assert_called_once_with("cfg log --oneline -1", dotfiles_root)

    def test_returns_done_on_empty_output(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "")

        cmd = CommandRun(shell=shell, args=("checkout", "-b", "test"))
        result = cmd.execute()

        assert result.success
        assert result.output == "Done"

    def test_fails_on_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("fatal: not a git repository", "")

        cmd = CommandRun(shell=shell, args=("log",))
        result = cmd.execute()

        assert not result.success
        assert "fatal" in result.error

    def test_no_args_runs_bare_cfg(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "usage: git ...")

        cmd = CommandRun(shell=shell, args=())
        result = cmd.execute()

        assert result.success
        shell.exe.assert_called_once_with("cfg ", dotfiles_root)
