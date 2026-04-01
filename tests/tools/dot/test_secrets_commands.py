from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dot.tui.commands.secrets import (
    SecretEntry,
    hide_all,
    list_secrets,
    register_secret,
    reveal_all,
    unregister_secret,
)
from dot.tui.git_ops import GitOps


@pytest.fixture
def shell() -> MagicMock:
    mock = MagicMock()
    mock.exe.return_value = ("", "")
    return mock


@pytest.fixture
def git_ops(shell: MagicMock, tmp_path: Path) -> GitOps:
    return GitOps(shell=shell, dotfiles_root=str(tmp_path))


class TestListSecrets:
    def test_empty_when_git_secret_not_installed(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False

        result = list_secrets(git_ops)

        assert result == []

    def test_empty_when_secret_list_returns_empty(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", "")

        result = list_secrets(git_ops)

        assert result == []

    def test_revealed_status_when_decrypted_file_exists(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", ".ssh/config\n")
        (tmp_path / ".ssh").mkdir()
        (tmp_path / ".ssh" / "config").write_text("host data")

        result = list_secrets(git_ops)

        assert result == [SecretEntry(path=".ssh/config", status="revealed")]

    def test_hidden_status_when_only_secret_file_exists(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", ".ssh/config\n")
        (tmp_path / ".ssh").mkdir()
        (tmp_path / ".ssh" / "config.secret").write_text("encrypted")

        result = list_secrets(git_ops)

        assert result == [SecretEntry(path=".ssh/config", status="hidden")]

    def test_mixed_revealed_and_hidden(self, git_ops: GitOps, shell: MagicMock, tmp_path: Path) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", ".ssh/config\n.gnupg/keys\n.env\n")
        (tmp_path / ".ssh").mkdir()
        (tmp_path / ".ssh" / "config").write_text("host data")
        (tmp_path / ".gnupg").mkdir()
        (tmp_path / ".gnupg" / "keys.secret").write_text("encrypted")
        (tmp_path / ".env").write_text("SECRET=val")

        result = list_secrets(git_ops)

        assert len(result) == 3
        assert SecretEntry(path=".ssh/config", status="revealed") in result
        assert SecretEntry(path=".gnupg/keys", status="hidden") in result
        assert SecretEntry(path=".env", status="revealed") in result

    def test_error_returns_empty_list(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("error listing secrets", "")

        result = list_secrets(git_ops)

        assert result == []


class TestRegisterSecret:
    def test_failure_when_git_secret_not_installed(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False

        result = register_secret(git_ops, ".ssh/config")

        assert result.success is False

    def test_success(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", "")

        result = register_secret(git_ops, ".ssh/config")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg secret add" in cmd
        assert ".ssh/config" in cmd

    def test_failure_on_command_error(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("cannot add file", "")

        result = register_secret(git_ops, ".ssh/config")

        assert result.success is False
        assert result.error


class TestUnregisterSecret:
    def test_failure_when_git_secret_not_installed(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False

        result = unregister_secret(git_ops, ".ssh/config")

        assert result.success is False

    def test_success(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", "")

        result = unregister_secret(git_ops, ".ssh/config")

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg secret remove" in cmd
        assert ".ssh/config" in cmd

    def test_failure_on_command_error(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("remove failed", "")

        result = unregister_secret(git_ops, ".ssh/config")

        assert result.success is False
        assert result.error


class TestRevealAll:
    def test_failure_when_git_secret_not_installed(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False

        result = reveal_all(git_ops)

        assert result.success is False

    def test_success(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", "")

        result = reveal_all(git_ops)

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg secret reveal" in cmd

    def test_failure_on_command_error(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("reveal failed", "")

        result = reveal_all(git_ops)

        assert result.success is False
        assert result.error


class TestHideAll:
    def test_failure_when_git_secret_not_installed(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = False

        result = hide_all(git_ops)

        assert result.success is False

    def test_success(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("", "")

        result = hide_all(git_ops)

        assert result.success is True
        cmd = shell.exe.call_args[0][0]
        assert "cfg secret hide" in cmd

    def test_failure_on_command_error(self, git_ops: GitOps, shell: MagicMock) -> None:
        shell.is_command_available.return_value = True
        shell.exe.return_value = ("hide failed", "")

        result = hide_all(git_ops)

        assert result.success is False
        assert result.error
