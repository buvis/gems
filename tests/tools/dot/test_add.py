from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from dot.commands.add.add import CommandAdd


class TestCommandAddInit:
    @patch("dot.commands.add.add.DotGitService")
    def test_constructs_dot_git_service_with_shell_and_dotfiles_root(
        self, mock_service_cls, dotfiles_root: Path
    ) -> None:
        shell = MagicMock()

        CommandAdd(shell=shell, dotfiles_root=str(dotfiles_root))

        mock_service_cls.assert_called_once_with(shell, str(dotfiles_root))

    def test_does_not_mutate_environment(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        shell = MagicMock()

        with patch("dot.commands.add.add.DotGitService"):
            CommandAdd(shell=shell, dotfiles_root=str(tmp_path))

        assert "DOTFILES_ROOT" not in os.environ

    @patch("dot.commands.add.add.DotGitService")
    def test_does_not_call_shell_alias(self, mock_service_cls, dotfiles_root: Path) -> None:
        shell = MagicMock()

        CommandAdd(shell=shell, dotfiles_root=str(dotfiles_root))

        shell.alias.assert_not_called()

    @patch("dot.commands.add.add.DotGitService")
    def test_absolute_file_path_resolved(self, mock_service_cls, dotfiles_root: Path) -> None:
        target = dotfiles_root / "test.txt"
        target.write_text("hello", encoding="utf-8")
        shell = MagicMock()

        cmd = CommandAdd(shell=shell, dotfiles_root=str(dotfiles_root), file_path=str(target))

        assert cmd.file_path == Path(str(target))

    @patch("dot.commands.add.add.DotGitService")
    def test_relative_file_path_resolved_under_dotfiles_root(self, mock_service_cls, dotfiles_root: Path) -> None:
        target = dotfiles_root / ".bashrc"
        target.write_text("export FOO=1", encoding="utf-8")
        shell = MagicMock()

        cmd = CommandAdd(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".bashrc")

        assert cmd.file_path == dotfiles_root / ".bashrc"

    @patch("dot.commands.add.add.DotGitService")
    def test_absolute_dir_path_resolved(self, mock_service_cls, dotfiles_root: Path) -> None:
        target = dotfiles_root / "subdir"
        target.mkdir()
        shell = MagicMock()

        cmd = CommandAdd(shell=shell, dotfiles_root=str(dotfiles_root), file_path=str(target))

        assert cmd.file_path == target

    @patch("dot.commands.add.add.DotGitService")
    def test_relative_dir_path_resolved_under_dotfiles_root(self, mock_service_cls, dotfiles_root: Path) -> None:
        target = dotfiles_root / ".config"
        target.mkdir()
        shell = MagicMock()

        cmd = CommandAdd(shell=shell, dotfiles_root=str(dotfiles_root), file_path=".config")

        assert cmd.file_path == dotfiles_root / ".config"

    @patch("dot.commands.add.add.DotGitService")
    def test_nonexistent_path_resolves_to_none(self, mock_service_cls, dotfiles_root: Path) -> None:
        shell = MagicMock()

        cmd = CommandAdd(shell=shell, dotfiles_root=str(dotfiles_root), file_path="no_such_file.txt")

        assert cmd.file_path is None
        assert cmd.missing_path == "no_such_file.txt"

    @patch("dot.commands.add.add.DotGitService")
    def test_no_file_path(self, mock_service_cls, dotfiles_root: Path) -> None:
        shell = MagicMock()

        cmd = CommandAdd(shell=shell, dotfiles_root=str(dotfiles_root))

        assert cmd.file_path is None

    @patch("dot.commands.add.add.DotGitService")
    def test_relative_path_resolves_against_cwd_before_the_dotfiles_root(
        self, mock_service_cls, dotfiles_root: Path, monkeypatch
    ) -> None:
        folder = dotfiles_root / ".config" / "gh-agent"
        folder.mkdir(parents=True)
        target = folder / "config.yml"
        target.write_text("hello")
        monkeypatch.chdir(folder)
        cmd = CommandAdd(shell=MagicMock(), dotfiles_root=str(dotfiles_root), file_path="config.yml")
        assert cmd.file_path == target
        assert cmd.missing_path is None

    @patch("dot.commands.add.add.DotGitService")
    def test_symlink_is_kept_as_the_link_not_its_target(self, mock_service_cls, dotfiles_root: Path) -> None:
        real = dotfiles_root / "real"
        real.mkdir()
        link = dotfiles_root / "link"
        link.symlink_to(real, target_is_directory=True)
        cmd = CommandAdd(shell=MagicMock(), dotfiles_root=str(dotfiles_root), file_path=str(link))
        assert cmd.file_path == link

    @patch("dot.commands.add.add.DotGitService")
    def test_dangling_symlink_is_a_path_not_a_missing_file(self, mock_service_cls, dotfiles_root: Path) -> None:
        link = dotfiles_root / "link"
        link.symlink_to(dotfiles_root / "gone")
        cmd = CommandAdd(shell=MagicMock(), dotfiles_root=str(dotfiles_root), file_path=str(link))
        assert cmd.file_path == link
        assert cmd.missing_path is None


class TestCommandAddExecute:
    @patch("dot.commands.add.add.DotGitService")
    def test_no_file_calls_stage_interactive_with_none(self, mock_service_cls, dotfiles_root: Path) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.stage_interactive.return_value = CommandResult(success=True, output="Currently staged:\nA\tx")
        shell = MagicMock()

        cmd = CommandAdd(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result is mock_service.stage_interactive.return_value
        mock_service.stage_interactive.assert_called_once_with(None)

    @patch("dot.commands.add.add.DotGitService")
    def test_with_file_calls_stage_interactive_with_str_path(self, mock_service_cls, dotfiles_root: Path) -> None:
        target = dotfiles_root / "tracked.txt"
        target.write_text("content", encoding="utf-8")
        mock_service = mock_service_cls.return_value
        mock_service.stage_interactive.return_value = CommandResult(success=True, output="Currently staged:\nA\tx")
        shell = MagicMock()

        cmd = CommandAdd(shell=shell, dotfiles_root=str(dotfiles_root), file_path=str(target))
        result = cmd.execute()

        assert result is mock_service.stage_interactive.return_value
        mock_service.stage_interactive.assert_called_once_with(str(target))

    @patch("dot.commands.add.add.DotGitService")
    def test_nonexistent_path_fails_without_calling_the_service(self, mock_service_cls, dotfiles_root: Path) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.stage_interactive.return_value = CommandResult(success=True, output="Currently staged:\nA\tx")
        shell = MagicMock()

        cmd = CommandAdd(shell=shell, dotfiles_root=str(dotfiles_root), file_path="missing.txt")
        result = cmd.execute()

        assert result == CommandResult(success=False, error="Path missing.txt doesn't exist")
        mock_service.stage_interactive.assert_not_called()

    @patch("dot.commands.add.add.DotGitService")
    def test_execute_never_calls_shell_directly(self, mock_service_cls, dotfiles_root: Path) -> None:
        shell = MagicMock()

        cmd = CommandAdd(shell=shell, dotfiles_root=str(dotfiles_root))
        cmd.execute()

        shell.exe.assert_not_called()
        shell.interact.assert_not_called()
        shell.alias.assert_not_called()
