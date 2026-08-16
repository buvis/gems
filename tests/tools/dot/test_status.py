from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from dot.commands.status.status import CommandStatus, parse_porcelain_status
from dot.git.models import BranchInfo, FileEntry


class TestCommandStatusInit:
    @patch("dot.commands.status.status.DotGitService")
    def test_constructs_dot_git_service_with_shell_and_dotfiles_root(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))

        mock_service_cls.assert_called_once_with(shell, str(dotfiles_root))

    def test_does_not_mutate_environment(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        shell = MagicMock()

        with patch("dot.commands.status.status.DotGitService"):
            CommandStatus(shell=shell, dotfiles_root=str(tmp_path))

        assert "DOTFILES_ROOT" not in os.environ

    @patch("dot.commands.status.status.DotGitService")
    def test_does_not_call_shell_alias(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))

        shell.alias.assert_not_called()


class TestCommandStatusExecute:
    @patch("dot.commands.status.status.DotGitService")
    def test_returns_failure_when_secret_hide_errors(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([], "secret error")
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert not result.success
        assert result.error == "Error hiding secrets: secret error"
        mock_service.branch_info.assert_not_called()

    @patch("dot.commands.status.status.DotGitService")
    def test_nothing_to_commit(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([], None)
        mock_service.branch_info.return_value = BranchInfo(name="main")
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.output == "No modifications found"
        assert result.info == []
        assert result.warnings == []

    @patch("dot.commands.status.status.DotGitService")
    def test_staged_modified_files(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = (
            [
                FileEntry(path=".bashrc", status="M "),
                FileEntry(path=".vimrc", status="M "),
            ],
            None,
        )
        mock_service.branch_info.return_value = BranchInfo(name="main")
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.info == ["staged: .bashrc modified", "staged: .vimrc modified"]
        assert result.warnings == []

    @patch("dot.commands.status.status.DotGitService")
    def test_unstaged_modified_files(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = (
            [
                FileEntry(path=".bashrc", status=" M"),
                FileEntry(path=".vimrc", status=" M"),
            ],
            None,
        )
        mock_service.branch_info.return_value = BranchInfo(name="main")
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.info == []
        assert result.warnings == ["unstaged: .bashrc modified", "unstaged: .vimrc modified"]

    @patch("dot.commands.status.status.DotGitService")
    def test_staged_and_unstaged_mixed(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = (
            [
                FileEntry(path=".bashrc", status="M "),
                FileEntry(path=".vimrc", status=" M"),
            ],
            None,
        )
        mock_service.branch_info.return_value = BranchInfo(name="main")
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.info == ["staged: .bashrc modified"]
        assert result.warnings == ["unstaged: .vimrc modified"]

    @patch("dot.commands.status.status.DotGitService")
    def test_both_staged_and_unstaged_same_file(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([FileEntry(path=".bashrc", status="MM")], None)
        mock_service.branch_info.return_value = BranchInfo(name="main")
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.info == ["staged: .bashrc modified"]
        assert result.warnings == ["unstaged: .bashrc modified"]

    @patch("dot.commands.status.status.DotGitService")
    def test_deleted_file_unstaged(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([FileEntry(path=".config/nushell/env.nu", status=" D")], None)
        mock_service.branch_info.return_value = BranchInfo(name="main")
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.warnings == ["unstaged: .config/nushell/env.nu deleted"]

    @patch("dot.commands.status.status.DotGitService")
    def test_new_file_staged(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([FileEntry(path=".newrc", status="A ")], None)
        mock_service.branch_info.return_value = BranchInfo(name="main")
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.info == ["staged: .newrc new file"]

    @patch("dot.commands.status.status.DotGitService")
    def test_untracked_file(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([FileEntry(path=".newrc", status="??")], None)
        mock_service.branch_info.return_value = BranchInfo(name="main")
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.info == []
        assert result.warnings == ["unstaged: .newrc untracked"]

    @patch("dot.commands.status.status.DotGitService")
    def test_unpushed_commits(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([], None)
        mock_service.branch_info.return_value = BranchInfo(name="main", ahead=3)
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.warnings == ["3 commit(s) not pushed"]

    @patch("dot.commands.status.status.DotGitService")
    def test_unpulled_commits(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([], None)
        mock_service.branch_info.return_value = BranchInfo(name="main", behind=2)
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.warnings == ["2 commit(s) not pulled"]

    @patch("dot.commands.status.status.DotGitService")
    def test_both_unpushed_and_unpulled(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([], None)
        mock_service.branch_info.return_value = BranchInfo(name="main", ahead=3, behind=2)
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.warnings == ["3 commit(s) not pushed", "2 commit(s) not pulled"]

    @patch("dot.commands.status.status.DotGitService")
    def test_staged_with_unpushed(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([FileEntry(path=".bashrc", status="M ")], None)
        mock_service.branch_info.return_value = BranchInfo(name="main", ahead=1)
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert result.success
        assert result.info == ["staged: .bashrc modified"]
        assert result.warnings == ["1 commit(s) not pushed"]

    @patch("dot.commands.status.status.DotGitService")
    def test_execute_never_calls_shell_directly(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([], None)
        mock_service.branch_info.return_value = BranchInfo(name="main")
        shell = MagicMock()

        cmd = CommandStatus(shell=shell, dotfiles_root=str(dotfiles_root))
        cmd.execute()

        shell.exe.assert_not_called()
        shell.interact.assert_not_called()
        shell.alias.assert_not_called()


class TestParsePorcelainStatus:
    def test_empty_output(self) -> None:
        staged, unstaged = parse_porcelain_status("")

        assert staged == []
        assert unstaged == []

    def test_staged_modified(self) -> None:
        staged, unstaged = parse_porcelain_status("M  config.yaml")

        assert len(staged) == 1
        assert staged[0] == ("config.yaml", "modified")
        assert unstaged == []

    def test_unstaged_modified(self) -> None:
        staged, unstaged = parse_porcelain_status(" M config.yaml")

        assert staged == []
        assert len(unstaged) == 1
        assert unstaged[0] == ("config.yaml", "modified")

    def test_both_staged_and_unstaged(self) -> None:
        staged, unstaged = parse_porcelain_status("MM config.yaml")

        assert len(staged) == 1
        assert len(unstaged) == 1
        assert staged[0] == ("config.yaml", "modified")
        assert unstaged[0] == ("config.yaml", "modified")

    def test_mixed_changes(self) -> None:
        output = "A  readme.md\nM  config.yaml\n D old.txt\n"

        staged, unstaged = parse_porcelain_status(output)

        assert len(staged) == 2
        assert staged[0] == ("readme.md", "new file")
        assert staged[1] == ("config.yaml", "modified")
        assert len(unstaged) == 1
        assert unstaged[0] == ("old.txt", "deleted")

    def test_untracked(self) -> None:
        staged, unstaged = parse_porcelain_status("?? newfile.txt")

        assert staged == []
        assert len(unstaged) == 1
        assert unstaged[0] == ("newfile.txt", "untracked")

    def test_renamed(self) -> None:
        staged, unstaged = parse_porcelain_status("R  old.conf -> new.conf")

        assert len(staged) == 1
        assert staged[0] == ("old.conf -> new.conf", "renamed")
        assert unstaged == []

    def test_short_lines_skipped(self) -> None:
        staged, unstaged = parse_porcelain_status("ab\n\n")

        assert staged == []
        assert unstaged == []
