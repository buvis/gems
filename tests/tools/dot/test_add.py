from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

from buvis.pybase.result import CommandResult
from dot.commands.add.add import CommandAdd


class TestCommandAddInit:
    def test_preserves_existing_dotfiles_root(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        CommandAdd(shell=shell)
        assert os.environ["DOTFILES_ROOT"] == str(dotfiles_root)

    def test_sets_dotfiles_root_when_missing(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        shell = MagicMock()
        CommandAdd(shell=shell)
        assert os.environ["DOTFILES_ROOT"] == str(Path.home().resolve())

    def test_alias_defined(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        CommandAdd(shell=shell)
        shell.alias.assert_called_once_with(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

    def test_absolute_file_path_resolved(self, dotfiles_root: Path) -> None:
        target = dotfiles_root / "test.txt"
        target.write_text("hello", encoding="utf-8")
        shell = MagicMock()
        cmd = CommandAdd(shell=shell, file_path=str(target))
        assert cmd.file_path == Path(str(target))
        assert cmd.warnings == []

    def test_relative_file_path_resolved_under_dotfiles(self, dotfiles_root: Path) -> None:
        target = dotfiles_root / ".bashrc"
        target.write_text("export FOO=1", encoding="utf-8")
        shell = MagicMock()
        cmd = CommandAdd(shell=shell, file_path=".bashrc")
        assert cmd.file_path == dotfiles_root / ".bashrc"
        assert cmd.warnings == []

    def test_nonexistent_file_warns(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        cmd = CommandAdd(shell=shell, file_path="no_such_file.txt")
        assert cmd.file_path is None
        assert len(cmd.warnings) == 1
        assert "doesn't exist" in cmd.warnings[0]

    def test_no_file_path(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        cmd = CommandAdd(shell=shell)
        assert cmd.file_path is None
        assert cmd.warnings == []


class TestCommandAddExecute:
    def test_no_file_runs_add_all(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        cmd = CommandAdd(shell=shell)
        result = cmd.execute()

        assert isinstance(result, CommandResult)
        assert result.success is True
        shell.interact.assert_called_once_with(
            "cfg add -p",
            dotfiles_root,
        )

    def test_tracked_file_runs_add_patch(self, dotfiles_root: Path) -> None:
        target = dotfiles_root / "tracked.txt"
        target.write_text("content", encoding="utf-8")
        shell = MagicMock()
        shell.exe.return_value = ("", str(target))

        cmd = CommandAdd(shell=shell, file_path=str(target))
        result = cmd.execute()

        assert result.success is True
        shell.exe.assert_called_once()
        shell.interact.assert_called_once_with(
            f"cfg add -p {target}",
            dotfiles_root,
        )

    def test_untracked_file_runs_add_without_patch(self, dotfiles_root: Path) -> None:
        target = dotfiles_root / "newfile.txt"
        target.write_text("content", encoding="utf-8")
        shell = MagicMock()
        shell.exe.return_value = ("returned non-zero exit status 1", "")

        cmd = CommandAdd(shell=shell, file_path=str(target))
        result = cmd.execute()

        assert result.success is True
        shell.interact.assert_called_once_with(
            f"cfg add {target}",
            dotfiles_root,
        )

    def test_warnings_propagated(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        cmd = CommandAdd(shell=shell, file_path="missing.txt")
        result = cmd.execute()

        assert result.success is True
        assert len(result.warnings) == 1
        assert "doesn't exist" in result.warnings[0]
