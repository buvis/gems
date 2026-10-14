from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from dot.commands.status.status import CommandStatus
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


def _write_manifest(root, *lines: str) -> None:
    manifest = root / ".config" / "buvis" / "host-links"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("\n".join(lines) + "\n")


class TestCommandStatusHostLinks:
    @staticmethod
    def _clean_service(mock_service_cls) -> MagicMock:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([], None)
        mock_service.branch_info.return_value = BranchInfo(name="main")
        return mock_service

    @patch("dot.commands.status.status.DotGitService")
    def test_warns_when_host_file_is_missing(self, mock_service_cls, dotfiles_root) -> None:
        self._clean_service(mock_service_cls)
        _write_manifest(dotfiles_root, ".gitconfig => hosts/laptop/gitconfig")

        result = CommandStatus(shell=MagicMock(), dotfiles_root=str(dotfiles_root)).execute()

        assert result.success
        assert ".gitconfig: no host file at hosts/laptop/gitconfig" in result.warnings
        assert result.output != "No modifications found"

    @patch("dot.commands.status.status.DotGitService")
    def test_warns_when_link_missing_and_creates_nothing(self, mock_service_cls, dotfiles_root) -> None:
        self._clean_service(mock_service_cls)
        source = dotfiles_root / "hosts" / "laptop" / "gitconfig"
        source.parent.mkdir(parents=True)
        source.write_text("[user]\n")
        _write_manifest(dotfiles_root, ".gitconfig => hosts/laptop/gitconfig")

        result = CommandStatus(shell=MagicMock(), dotfiles_root=str(dotfiles_root)).execute()

        assert ".gitconfig: link missing; run 'dot materialize'" in result.warnings
        assert not (dotfiles_root / ".gitconfig").exists()
        assert not (dotfiles_root / ".gitconfig").is_symlink()

    @patch("dot.commands.status.status.DotGitService")
    def test_link_warnings_come_after_git_warnings(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = self._clean_service(mock_service_cls)
        mock_service.status.return_value = ([FileEntry(path=".bashrc", status=" M")], None)
        mock_service.branch_info.return_value = BranchInfo(name="main", ahead=2)
        _write_manifest(dotfiles_root, ".gitconfig => hosts/laptop/gitconfig")

        result = CommandStatus(shell=MagicMock(), dotfiles_root=str(dotfiles_root)).execute()

        assert result.warnings == [
            "unstaged: .bashrc modified",
            "2 commit(s) not pushed",
            ".gitconfig: no host file at hosts/laptop/gitconfig",
        ]

    @patch("dot.commands.status.status.DotGitService")
    def test_reports_no_modifications_without_manifest(self, mock_service_cls, dotfiles_root) -> None:
        self._clean_service(mock_service_cls)

        result = CommandStatus(shell=MagicMock(), dotfiles_root=str(dotfiles_root)).execute()

        assert result.success
        assert result.output == "No modifications found"
        assert result.warnings == []

    @patch("dot.commands.status.status.DotGitService")
    def test_secret_hide_failure_returns_without_link_warnings(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([], "secret error")
        _write_manifest(dotfiles_root, ".gitconfig => hosts/laptop/gitconfig")

        result = CommandStatus(shell=MagicMock(), dotfiles_root=str(dotfiles_root)).execute()

        assert not result.success
        assert result.error == "Error hiding secrets: secret error"
        assert result.warnings == []


class TestCommandStatusHookHealth:
    @staticmethod
    def _clean_service(mock_service_cls) -> MagicMock:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([], None)
        mock_service.branch_info.return_value = BranchInfo(name="main")
        mock_service.check_hooks.return_value = []
        return mock_service

    @patch("dot.commands.status.status.DotGitService")
    def test_missing_pre_commit_hook_is_reported_as_warning(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = self._clean_service(mock_service_cls)
        mock_service.check_hooks.return_value = ["pre-commit hook missing: /h/pre-commit"]

        result = CommandStatus(shell=MagicMock(), dotfiles_root=str(dotfiles_root)).execute()

        assert result.success
        assert result.warnings == ["pre-commit hook missing: /h/pre-commit"]
        assert result.output != "No modifications found"

    @patch("dot.commands.status.status.DotGitService")
    def test_hook_warnings_come_after_link_warnings(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = self._clean_service(mock_service_cls)
        mock_service.branch_info.return_value = BranchInfo(name="main", ahead=1)
        mock_service.check_hooks.return_value = ["hooks dir missing: /h"]
        _write_manifest(dotfiles_root, ".gitconfig => hosts/laptop/gitconfig")

        result = CommandStatus(shell=MagicMock(), dotfiles_root=str(dotfiles_root)).execute()

        assert result.warnings == [
            "1 commit(s) not pushed",
            ".gitconfig: no host file at hosts/laptop/gitconfig",
            "hooks dir missing: /h",
        ]

    @patch("dot.commands.status.status.DotGitService")
    def test_secret_hide_failure_skips_hook_check(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.status.return_value = ([], "secret error")

        result = CommandStatus(shell=MagicMock(), dotfiles_root=str(dotfiles_root)).execute()

        assert not result.success
        mock_service.check_hooks.assert_not_called()
