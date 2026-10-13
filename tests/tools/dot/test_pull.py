from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from dot.commands.pull.pull import CommandPull


class TestCommandPullInit:
    @patch("dot.commands.pull.pull.DotGitService")
    def test_constructs_dot_git_service_with_shell_and_dotfiles_root(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))

        mock_service_cls.assert_called_once_with(shell, str(dotfiles_root))

    def test_does_not_mutate_environment(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("DOTFILES_ROOT", raising=False)
        shell = MagicMock()

        with patch("dot.commands.pull.pull.DotGitService"):
            CommandPull(shell=shell, dotfiles_root=str(tmp_path))

        assert "DOTFILES_ROOT" not in os.environ

    @patch("dot.commands.pull.pull.DotGitService")
    def test_does_not_call_shell_alias(self, mock_service_cls, dotfiles_root) -> None:
        shell = MagicMock()

        CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))

        shell.alias.assert_not_called()


class TestCommandPullExecute:
    @patch("dot.commands.pull.pull.CommandMaterialize")
    @patch("dot.commands.pull.pull.DotGitService")
    def test_execute_calls_service_pull_with_no_passphrase_and_returns_success(
        self, mock_service_cls, mock_mat_cls, dotfiles_root
    ) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.fetch.return_value = ""
        mock_service.has_upstream.return_value = False
        mock_service.pull.return_value = CommandResult(success=True, output="Dotfiles pulled successfully")
        mock_mat_cls.return_value.execute.return_value = CommandResult(success=True)
        shell = MagicMock()

        cmd = CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        mock_service.pull.assert_called_once_with(passphrase=None)
        assert result.success
        assert result.output == "Dotfiles pulled successfully"

    @patch("dot.commands.pull.pull.CommandMaterialize")
    @patch("dot.commands.pull.pull.DotGitService")
    def test_execute_returns_service_failure_passthrough(self, mock_service_cls, mock_mat_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.fetch.return_value = ""
        mock_service.has_upstream.return_value = False
        mock_service.pull.return_value = CommandResult(success=False, error="Pull failed: error msg")
        shell = MagicMock()

        cmd = CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert not result.success
        assert result.error == "Pull failed: error msg"

    @patch("dot.commands.pull.pull.CommandMaterialize")
    @patch("dot.commands.pull.pull.DotGitService")
    def test_execute_never_calls_shell_directly(self, mock_service_cls, mock_mat_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.fetch.return_value = ""
        mock_service.has_upstream.return_value = False
        mock_service.pull.return_value = CommandResult(success=True, output="Dotfiles pulled successfully")
        mock_mat_cls.return_value.execute.return_value = CommandResult(success=True)
        shell = MagicMock()

        cmd = CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))
        cmd.execute()

        shell.exe.assert_not_called()
        shell.interact.assert_not_called()
        shell.alias.assert_not_called()


class TestCommandPullRescue:
    @patch("dot.commands.pull.pull.CommandMaterialize")
    @patch("dot.commands.pull.pull.DotGitService")
    def test_noninteractive_collision_fails(self, mock_service_cls, mock_mat_cls, tmp_path, dotfiles_root) -> None:
        """Noninteractive collision -> failure, no merge."""
        mock_service = mock_service_cls.return_value
        mock_service.fetch.return_value = ""
        mock_service.has_upstream.return_value = True
        mock_service.show_upstream_file.return_value = ".vimrc => .local/.vimrc\n"
        mock_service.upstream_deleted_paths.return_value = [".vimrc"]

        # Create files for collision
        (dotfiles_root / ".vimrc").write_text("target bytes")
        (dotfiles_root / ".local").mkdir()
        (dotfiles_root / ".local/.vimrc").write_text("source bytes")

        shell = MagicMock()
        cmd = CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))

        # No resolutions provided (noninteractive)
        result = cmd.execute()

        assert not result.success
        assert "unresolved host-link collision(s): .vimrc" in result.error
        mock_service.pull.assert_not_called()

    @patch("dot.commands.pull.pull.CommandMaterialize")
    @patch("dot.commands.pull.pull.DotGitService")
    def test_collision_failure_leaves_paths_unchanged(
        self, mock_service_cls, mock_mat_cls, tmp_path, dotfiles_root
    ) -> None:
        """Noninteractive collision leaves both paths unchanged."""
        mock_service = mock_service_cls.return_value
        mock_service.fetch.return_value = ""
        mock_service.has_upstream.return_value = True
        mock_service.show_upstream_file.return_value = ".vimrc => .local/.vimrc\n"
        mock_service.upstream_deleted_paths.return_value = [".vimrc"]

        # Create files for collision
        (dotfiles_root / ".vimrc").write_text("target bytes")
        (dotfiles_root / ".local").mkdir()
        (dotfiles_root / ".local/.vimrc").write_text("source bytes")

        shell = MagicMock()
        cmd = CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))
        cmd.execute()

        # Both files unchanged
        assert (dotfiles_root / ".vimrc").read_text() == "target bytes"
        assert (dotfiles_root / ".local/.vimrc").read_text() == "source bytes"

    @patch("dot.commands.pull.pull.CommandMaterialize")
    @patch("dot.commands.pull.pull.DotGitService")
    def test_collision_failure_does_not_call_pull(
        self, mock_service_cls, mock_mat_cls, tmp_path, dotfiles_root
    ) -> None:
        """Noninteractive collision does not call pull."""
        mock_service = mock_service_cls.return_value
        mock_service.fetch.return_value = ""
        mock_service.has_upstream.return_value = True
        mock_service.show_upstream_file.return_value = ".vimrc => .local/.vimrc\n"
        mock_service.upstream_deleted_paths.return_value = [".vimrc"]

        # Create files for collision
        (dotfiles_root / ".vimrc").write_text("target bytes")
        (dotfiles_root / ".local").mkdir()
        (dotfiles_root / ".local/.vimrc").write_text("source bytes")

        shell = MagicMock()
        cmd = CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))
        cmd.execute()

        mock_service.pull.assert_not_called()

    @patch("dot.commands.pull.pull.DotGitService")
    def test_fetch_failure_returns_error(self, mock_service_cls, dotfiles_root) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.fetch.return_value = "fatal: unable to access remote"
        shell = MagicMock()

        cmd = CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert not result.success
        assert "Fetch failed" in result.error

    @patch("dot.commands.pull.pull.CommandMaterialize")
    @patch("dot.commands.pull.pull.DotGitService")
    def test_pull_failure_after_rescue_includes_rescue_info(
        self, mock_service_cls, mock_mat_cls, dotfiles_root
    ) -> None:
        mock_service = mock_service_cls.return_value
        mock_service.fetch.return_value = ""
        mock_service.has_upstream.return_value = True
        mock_service.show_upstream_file.return_value = ".zshrc => .local/.zshrc\n"
        mock_service.upstream_deleted_paths.return_value = [".zshrc"]
        mock_service.pull.return_value = CommandResult(success=False, error="merge conflict")

        # Create file for move
        (dotfiles_root / ".zshrc").write_text("my config")

        shell = MagicMock()
        cmd = CommandPull(shell=shell, dotfiles_root=str(dotfiles_root))
        result = cmd.execute()

        assert not result.success
        assert "rescued files are at:" in result.error
        assert ".local/.zshrc" in result.error
