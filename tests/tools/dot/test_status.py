from __future__ import annotations

from unittest.mock import MagicMock

from dot.commands.status.status import CommandStatus, parse_porcelain_status


class TestCommandStatusInit:
    def test_preserves_existing_dotfiles_root(self, tmp_path, monkeypatch) -> None:
        custom_root = tmp_path / "custom"
        custom_root.mkdir()
        monkeypatch.setenv("DOTFILES_ROOT", str(custom_root))
        shell = MagicMock()

        CommandStatus(shell=shell)

        import os

        assert os.environ["DOTFILES_ROOT"] == str(custom_root)

    def test_sets_dotfiles_root_when_missing(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        shell = MagicMock()

        CommandStatus(shell=shell)

        import os

        assert os.environ.get("DOTFILES_ROOT") is not None


class TestCommandStatusExecute:
    def test_git_secret_hide_success(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.side_effect = [
            ("", ""),  # cfg secret hide -m
            ("", ""),  # cfg status --porcelain (empty = clean)
            ("", ""),  # cfg rev-list (no upstream)
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "No modifications found"
        assert shell.exe.call_count == 3
        shell.exe.assert_any_call("cfg secret hide -m", dotfiles_root)

    def test_git_secret_hide_error(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("secret error", "details")

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert "Error hiding secrets" in result.error

    def test_cfg_status_error(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.return_value = ("git error", "")

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert not result.success
        assert "Error executing command" in result.error

    def test_nothing_to_commit(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", ""),  # cfg status --porcelain
            ("", ""),  # cfg rev-list
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "No modifications found"
        assert result.warnings == []

    def test_empty_output(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", ""),  # cfg status --porcelain
            ("", ""),  # cfg rev-list
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "No modifications found"

    def test_staged_modified_files(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "M  .bashrc\nM  .vimrc"),  # cfg status --porcelain
            ("", ""),  # cfg rev-list
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert len(result.info) == 2
        assert "staged: .bashrc modified" in result.info
        assert "staged: .vimrc modified" in result.info

    def test_unstaged_modified_files(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", " M .bashrc\n M .vimrc"),  # cfg status --porcelain
            ("", ""),  # cfg rev-list
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert len(result.warnings) == 2
        assert "unstaged: .bashrc modified" in result.warnings
        assert "unstaged: .vimrc modified" in result.warnings

    def test_staged_and_unstaged_mixed(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "M  .bashrc\n M .vimrc"),  # cfg status --porcelain
            ("", ""),  # cfg rev-list
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert len(result.info) == 1
        assert "staged: .bashrc modified" in result.info
        assert len(result.warnings) == 1
        assert "unstaged: .vimrc modified" in result.warnings

    def test_both_staged_and_unstaged_same_file(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "MM .bashrc"),  # cfg status --porcelain
            ("", ""),  # cfg rev-list
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert len(result.info) == 1
        assert "staged: .bashrc modified" in result.info
        assert len(result.warnings) == 1
        assert "unstaged: .bashrc modified" in result.warnings

    def test_deleted_files(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", " D .config/nushell/env.nu"),  # cfg status --porcelain
            ("", ""),  # cfg rev-list
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert len(result.warnings) == 1
        assert "unstaged: .config/nushell/env.nu deleted" in result.warnings

    def test_new_file_staged(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "A  .newrc"),  # cfg status --porcelain
            ("", ""),  # cfg rev-list
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert len(result.info) == 1
        assert "staged: .newrc new file" in result.info

    def test_untracked_files(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "?? .newrc"),  # cfg status --porcelain
            ("", ""),  # cfg rev-list (no upstream)
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert len(result.warnings) == 1
        assert "unstaged: .newrc untracked" in result.warnings

    def test_unpushed_commits(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", ""),  # cfg status --porcelain (clean)
            ("", "0\t3"),  # cfg rev-list: 0 behind, 3 ahead
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert len(result.warnings) == 1
        assert "3 commit(s) not pushed" in result.warnings

    def test_unpulled_commits(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", ""),  # cfg status --porcelain (clean)
            ("", "2\t0"),  # cfg rev-list: 2 behind, 0 ahead
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert len(result.warnings) == 1
        assert "2 commit(s) not pulled" in result.warnings

    def test_both_unpushed_and_unpulled(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", ""),  # cfg status --porcelain (clean)
            ("", "2\t3"),  # cfg rev-list: 2 behind, 3 ahead
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert len(result.warnings) == 2
        assert "3 commit(s) not pushed" in result.warnings
        assert "2 commit(s) not pulled" in result.warnings

    def test_no_upstream_tracking(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", ""),  # cfg status --porcelain (clean)
            ("fatal: no upstream", ""),  # cfg rev-list: error
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert result.output == "No modifications found"

    def test_staged_with_unpushed(self, dotfiles_root) -> None:
        shell = MagicMock()
        shell.is_command_available.return_value = False
        shell.exe.side_effect = [
            ("", "M  .bashrc"),  # cfg status --porcelain
            ("", "0\t1"),  # cfg rev-list: 1 ahead
        ]

        cmd = CommandStatus(shell=shell)
        result = cmd.execute()

        assert result.success
        assert "staged: .bashrc modified" in result.info
        assert "1 commit(s) not pushed" in result.warnings


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
