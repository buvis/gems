"""Tests for the localize command."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.adapters.shell.shell import ShellAdapter
from buvis.pybase.result import CommandResult
from dot.commands.localize.localize import CommandLocalize
from dot.hostlinks.manifest import MANIFEST_PATH, read_manifest


@pytest.fixture
def shell() -> MagicMock:
    mock = MagicMock()
    mock.exe.return_value = ("", "")
    return mock


class TestCommandLocalizePreconditons:
    def test_refuses_missing_target(self, tmp_path: Path, shell: MagicMock) -> None:
        with patch("dot.commands.localize.localize.DotGitService"):
            cmd = CommandLocalize(
                shell=shell,
                dotfiles_root=str(tmp_path),
                path=".zshrc",
            )
            result = cmd.execute()

        assert not result.success
        assert ".zshrc does not exist" in result.error

    def test_refuses_target_is_link(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".local").mkdir()
        (tmp_path / ".local/.zshrc").write_text("content")
        (tmp_path / ".zshrc").symlink_to(".local/.zshrc")

        with patch("dot.commands.localize.localize.DotGitService"):
            cmd = CommandLocalize(
                shell=shell,
                dotfiles_root=str(tmp_path),
                path=".zshrc",
            )
            result = cmd.execute()

        assert not result.success
        assert ".zshrc is already a link" in result.error

    def test_refuses_source_exists(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".zshrc").write_text("config")
        (tmp_path / ".local").mkdir()
        (tmp_path / ".local/.zshrc").write_text("existing")

        with patch("dot.commands.localize.localize.DotGitService"):
            cmd = CommandLocalize(
                shell=shell,
                dotfiles_root=str(tmp_path),
                path=".zshrc",
            )
            result = cmd.execute()

        assert not result.success
        assert ".local/.zshrc already exists" in result.error

    def test_refuses_already_in_manifest(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".zshrc").write_text("config")
        manifest = tmp_path / MANIFEST_PATH
        manifest.parent.mkdir(parents=True)
        manifest.write_text(".zshrc => .local/.zshrc\n")

        with patch("dot.commands.localize.localize.DotGitService") as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.list_secrets.return_value = []
            mock_service.ls_files.return_value = set()
            cmd = CommandLocalize(
                shell=shell,
                dotfiles_root=str(tmp_path),
                path=".zshrc",
            )
            result = cmd.execute()

        assert not result.success
        assert ".zshrc already listed in host-links manifest" in result.error

    def test_refuses_git_secret_file(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".ssh").mkdir()
        (tmp_path / ".ssh/config").write_text("secret config")

        with patch("dot.commands.localize.localize.DotGitService") as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.list_secrets.return_value = [".ssh/config"]
            mock_service.ls_files.return_value = {".ssh/config"}
            cmd = CommandLocalize(
                shell=shell,
                dotfiles_root=str(tmp_path),
                path=".ssh/config",
            )
            result = cmd.execute()

        assert not result.success
        assert ".ssh/config is a git-secret file; localize refused" in result.error


class TestCommandLocalizeSuccess:
    def test_localizes_tracked_file(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".zshrc").write_text("my config")

        with patch("dot.commands.localize.localize.DotGitService") as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.list_secrets.return_value = []
            mock_service.ls_files.return_value = {".zshrc"}
            mock_service.untrack.return_value = CommandResult(success=True)
            mock_service.stage.return_value = CommandResult(success=True)

            cmd = CommandLocalize(
                shell=shell,
                dotfiles_root=str(tmp_path),
                path=".zshrc",
            )
            result = cmd.execute()

        assert result.success
        # Target is now a link
        assert (tmp_path / ".zshrc").is_symlink()
        # Source has the original content
        assert (tmp_path / ".local/.zshrc").read_text() == "my config"
        # Manifest updated
        links, _ = read_manifest(tmp_path)
        assert any(link.target == ".zshrc" and link.source == ".local/.zshrc" for link in links)
        # Info lines
        assert any("moved" in i for i in result.info)
        assert any("linked" in i for i in result.info)
        assert any("untracked" in i for i in result.info)

    def test_localizes_tracked_directory(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".config/app").mkdir(parents=True)
        (tmp_path / ".config/app/settings.json").write_text('{"key": "value"}')

        with patch("dot.commands.localize.localize.DotGitService") as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.list_secrets.return_value = []
            mock_service.ls_files.return_value = {".config/app/settings.json"}
            mock_service.untrack.return_value = CommandResult(success=True)
            mock_service.stage.return_value = CommandResult(success=True)

            cmd = CommandLocalize(
                shell=shell,
                dotfiles_root=str(tmp_path),
                path=".config/app",
            )
            result = cmd.execute()

        assert result.success
        assert (tmp_path / ".config/app").is_symlink()
        assert (tmp_path / ".local/.config/app/settings.json").read_text() == '{"key": "value"}'

    def test_default_source_is_dot_local(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".bashrc").write_text("content")

        with patch("dot.commands.localize.localize.DotGitService") as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.list_secrets.return_value = []
            mock_service.ls_files.return_value = set()
            mock_service.stage.return_value = CommandResult(success=True)

            cmd = CommandLocalize(
                shell=shell,
                dotfiles_root=str(tmp_path),
                path=".bashrc",
            )
            result = cmd.execute()

        assert result.success
        assert (tmp_path / ".local/.bashrc").exists()

    def test_custom_source_with_to_option(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".bashrc").write_text("content")

        with patch("dot.commands.localize.localize.DotGitService") as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.list_secrets.return_value = []
            mock_service.ls_files.return_value = set()
            mock_service.stage.return_value = CommandResult(success=True)

            cmd = CommandLocalize(
                shell=shell,
                dotfiles_root=str(tmp_path),
                path=".bashrc",
                source=".host-config/.bashrc",
            )
            result = cmd.execute()

        assert result.success
        assert (tmp_path / ".host-config/.bashrc").exists()
        links, _ = read_manifest(tmp_path)
        assert any(link.source == ".host-config/.bashrc" for link in links)

    def test_untracked_file_skips_untrack_step(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".newrc").write_text("content")

        with patch("dot.commands.localize.localize.DotGitService") as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.list_secrets.return_value = []
            mock_service.ls_files.return_value = set()  # Not tracked
            mock_service.stage.return_value = CommandResult(success=True)

            cmd = CommandLocalize(
                shell=shell,
                dotfiles_root=str(tmp_path),
                path=".newrc",
            )
            result = cmd.execute()

        assert result.success
        mock_service.untrack.assert_not_called()
        assert not any("untracked" in i for i in result.info)


class TestCommandLocalizeFailureAndRollback:
    def test_untrack_failure_changes_nothing(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".zshrc").write_text("original content")

        with patch("dot.commands.localize.localize.DotGitService") as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.list_secrets.return_value = []
            mock_service.ls_files.return_value = {".zshrc"}
            mock_service.untrack.return_value = CommandResult(success=False, error="untrack error")

            cmd = CommandLocalize(
                shell=shell,
                dotfiles_root=str(tmp_path),
                path=".zshrc",
            )
            result = cmd.execute()

        assert not result.success
        assert "untrack failed" in result.error
        # Nothing changed
        assert (tmp_path / ".zshrc").read_text() == "original content"
        assert not (tmp_path / ".zshrc").is_symlink()
        assert not (tmp_path / ".local/.zshrc").exists()

    def test_link_failure_rolls_back(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".zshrc").write_text("original content")

        with patch("dot.commands.localize.localize.DotGitService") as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.list_secrets.return_value = []
            mock_service.ls_files.return_value = {".zshrc"}
            mock_service.untrack.return_value = CommandResult(success=True)

            with patch("dot.commands.localize.localize._create_link") as mock_link:
                mock_link.return_value = "symlink refused; enable Developer Mode"

                cmd = CommandLocalize(
                    shell=shell,
                    dotfiles_root=str(tmp_path),
                    path=".zshrc",
                )
                result = cmd.execute()

        assert not result.success
        assert "link creation failed" in result.error
        # Rolled back - file is back at target
        assert (tmp_path / ".zshrc").read_text() == "original content"
        assert not (tmp_path / ".zshrc").is_symlink()
        # unstage was called to undo untrack
        mock_service.unstage.assert_called_once_with(".zshrc")

    def test_manifest_failure_rolls_back(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".zshrc").write_text("original content")

        with patch("dot.commands.localize.localize.DotGitService") as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.list_secrets.return_value = []
            mock_service.ls_files.return_value = {".zshrc"}
            mock_service.untrack.return_value = CommandResult(success=True)

            with patch("dot.commands.localize.localize.append_entry") as mock_append:
                mock_append.side_effect = OSError("Permission denied")

                cmd = CommandLocalize(
                    shell=shell,
                    dotfiles_root=str(tmp_path),
                    path=".zshrc",
                )
                result = cmd.execute()

        assert not result.success
        # Rolled back - file is back at target
        assert (tmp_path / ".zshrc").read_text() == "original content"
        assert not (tmp_path / ".zshrc").is_symlink()

    def test_stage_failure_returns_warning(self, tmp_path: Path, shell: MagicMock) -> None:
        (tmp_path / ".zshrc").write_text("content")

        with patch("dot.commands.localize.localize.DotGitService") as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.list_secrets.return_value = []
            mock_service.ls_files.return_value = set()
            mock_service.stage.return_value = CommandResult(success=False, error="stage error")

            cmd = CommandLocalize(
                shell=shell,
                dotfiles_root=str(tmp_path),
                path=".zshrc",
            )
            result = cmd.execute()

        # Still successful (main operation completed)
        assert result.success
        # But has a warning
        assert len(result.warnings) > 0
        assert any("stage failed" in w for w in result.warnings)
        assert any("dot add" in w for w in result.warnings)


class TestCommandLocalizeRealGit:
    """Real git tests - uses actual git commands, not mocks."""

    @pytest.fixture
    def git_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Create a real git bare repo setup."""
        root = tmp_path / "dotfiles"
        root.mkdir()
        buvis_dir = root / ".buvis"

        # Initialize bare repo
        subprocess.run(
            ["git", "init", "--bare", str(buvis_dir)],
            check=True,
            capture_output=True,
        )

        # Set git identity
        monkeypatch.setenv("GIT_AUTHOR_NAME", "Test User")
        monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@test.local")
        monkeypatch.setenv("GIT_COMMITTER_NAME", "Test User")
        monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@test.local")

        # Configure the repo
        git_cmd = ["git", f"--git-dir={buvis_dir}", f"--work-tree={root}"]
        subprocess.run(
            [*git_cmd, "config", "user.email", "test@test.local"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [*git_cmd, "config", "user.name", "Test User"],
            check=True,
            capture_output=True,
        )

        # Create a tracked directory with files
        config_dir = root / ".config/app"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text('{"setting": "value"}')
        (config_dir / "cache.db").write_text("cache data")

        # Stage and commit
        subprocess.run(
            [*git_cmd, "add", ".config/app"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [*git_cmd, "commit", "-m", "Initial commit"],
            check=True,
            capture_output=True,
        )

        return root

    def test_real_git_localize_untracks(self, git_repo: Path) -> None:
        """Localize a tracked dir with real git: ls_files should be empty afterwards."""
        shell = ShellAdapter(suppress_logging=True)

        cmd = CommandLocalize(
            shell=shell,
            dotfiles_root=str(git_repo),
            path=".config/app",
        )
        result = cmd.execute()

        assert result.success, result.error

        # Verify the link exists
        assert (git_repo / ".config/app").is_symlink()

        # Verify the source has the content
        assert (git_repo / ".local/.config/app/settings.json").read_text() == '{"setting": "value"}'

        # Verify the files are untracked now
        from dot.git.service import DotGitService

        git_service = DotGitService(shell, str(git_repo))
        tracked = git_service.ls_files(".config/app")
        assert tracked == set(), f"Expected empty, got: {tracked}"

        # Verify manifest is staged
        # Check git status to confirm manifest is staged
        buvis_dir = git_repo / ".buvis"
        git_cmd = ["git", f"--git-dir={buvis_dir}", f"--work-tree={git_repo}"]
        result_status = subprocess.run(
            [*git_cmd, "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        assert MANIFEST_PATH in result_status.stdout
