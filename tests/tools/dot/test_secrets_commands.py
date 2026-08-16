from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from buvis.pybase.result import CommandResult
from dot.git.service import DotGitService
from dot.tui.commands.secrets import (
    SecretEntry,
    hide_all,
    list_secrets,
    register_secret,
    reveal_all,
    unregister_secret,
)


@pytest.fixture
def shell() -> MagicMock:
    mock = MagicMock()
    mock.exe.return_value = ("", "")
    return mock


@pytest.fixture
def git_ops(shell: MagicMock, tmp_path: Path) -> DotGitService:
    service = DotGitService(shell=shell, dotfiles_root=str(tmp_path))
    service.is_secret_tool_available = MagicMock(return_value=True)
    service.list_secrets = MagicMock(return_value=[])
    service.register_secret = MagicMock(return_value=CommandResult(success=True))
    service.unregister_secret = MagicMock(return_value=CommandResult(success=True))
    service.reveal_secrets = MagicMock(return_value=CommandResult(success=True))
    service.hide_secrets = MagicMock(return_value=CommandResult(success=True))
    return service


class TestListSecrets:
    def test_returns_empty_list_without_calling_list_secrets_when_tool_unavailable(
        self, git_ops: DotGitService
    ) -> None:
        git_ops.is_secret_tool_available.return_value = False

        result = list_secrets(git_ops)

        assert result == []
        git_ops.list_secrets.assert_not_called()

    def test_calls_list_secrets_when_tool_available(self, git_ops: DotGitService) -> None:
        list_secrets(git_ops)

        git_ops.list_secrets.assert_called_once_with()

    def test_returns_empty_list_when_service_reports_no_secrets(self, git_ops: DotGitService) -> None:
        git_ops.list_secrets.return_value = []

        result = list_secrets(git_ops)

        assert result == []

    def test_revealed_status_when_path_exists_on_disk(self, git_ops: DotGitService, tmp_path: Path) -> None:
        git_ops.list_secrets.return_value = [".ssh/config"]
        (tmp_path / ".ssh").mkdir()
        (tmp_path / ".ssh" / "config").write_text("host data")

        result = list_secrets(git_ops)

        assert result == [SecretEntry(path=".ssh/config", status="revealed")]

    def test_hidden_status_when_path_absent_on_disk(self, git_ops: DotGitService) -> None:
        git_ops.list_secrets.return_value = [".ssh/config"]

        result = list_secrets(git_ops)

        assert result == [SecretEntry(path=".ssh/config", status="hidden")]

    def test_mixed_revealed_and_hidden_statuses(self, git_ops: DotGitService, tmp_path: Path) -> None:
        git_ops.list_secrets.return_value = [".ssh/config", ".gnupg/keys", ".env"]
        (tmp_path / ".ssh").mkdir()
        (tmp_path / ".ssh" / "config").write_text("host data")
        (tmp_path / ".env").write_text("SECRET=val")

        result = list_secrets(git_ops)

        assert len(result) == 3
        assert SecretEntry(path=".ssh/config", status="revealed") in result
        assert SecretEntry(path=".gnupg/keys", status="hidden") in result
        assert SecretEntry(path=".env", status="revealed") in result


class TestRegisterSecret:
    def test_returns_error_without_calling_register_secret_when_tool_unavailable(self, git_ops: DotGitService) -> None:
        git_ops.is_secret_tool_available.return_value = False

        result = register_secret(git_ops, ".ssh/config")

        assert result.success is False
        assert result.error == "git-secret not installed"
        git_ops.register_secret.assert_not_called()

    def test_calls_register_secret_with_exact_path(self, git_ops: DotGitService) -> None:
        register_secret(git_ops, ".ssh/config")

        git_ops.register_secret.assert_called_once_with(".ssh/config")

    def test_returns_service_success_result_unchanged(self, git_ops: DotGitService) -> None:
        expected = CommandResult(success=True)
        git_ops.register_secret.return_value = expected

        result = register_secret(git_ops, ".ssh/config")

        assert result is expected

    def test_returns_service_failure_result_unchanged(self, git_ops: DotGitService) -> None:
        expected = CommandResult(success=False, error="cannot add file")
        git_ops.register_secret.return_value = expected

        result = register_secret(git_ops, ".ssh/config")

        assert result is expected


class TestUnregisterSecret:
    def test_returns_error_without_calling_unregister_secret_when_tool_unavailable(
        self, git_ops: DotGitService
    ) -> None:
        git_ops.is_secret_tool_available.return_value = False

        result = unregister_secret(git_ops, ".ssh/config")

        assert result.success is False
        assert result.error == "git-secret not installed"
        git_ops.unregister_secret.assert_not_called()

    def test_calls_unregister_secret_with_exact_path(self, git_ops: DotGitService) -> None:
        unregister_secret(git_ops, ".ssh/config")

        git_ops.unregister_secret.assert_called_once_with(".ssh/config")

    def test_returns_service_success_result_unchanged(self, git_ops: DotGitService) -> None:
        expected = CommandResult(success=True)
        git_ops.unregister_secret.return_value = expected

        result = unregister_secret(git_ops, ".ssh/config")

        assert result is expected

    def test_returns_service_failure_result_unchanged(self, git_ops: DotGitService) -> None:
        expected = CommandResult(success=False, error="remove failed")
        git_ops.unregister_secret.return_value = expected

        result = unregister_secret(git_ops, ".ssh/config")

        assert result is expected


class TestRevealAll:
    def test_returns_error_without_calling_reveal_secrets_when_tool_unavailable(self, git_ops: DotGitService) -> None:
        git_ops.is_secret_tool_available.return_value = False

        result = reveal_all(git_ops)

        assert result.success is False
        assert result.error == "git-secret not installed"
        git_ops.reveal_secrets.assert_not_called()

    def test_calls_reveal_secrets_with_none_when_no_passphrase_given(self, git_ops: DotGitService) -> None:
        reveal_all(git_ops)

        git_ops.reveal_secrets.assert_called_once_with(None)

    def test_calls_reveal_secrets_with_given_passphrase(self, git_ops: DotGitService) -> None:
        reveal_all(git_ops, "hunter2")

        git_ops.reveal_secrets.assert_called_once_with("hunter2")

    def test_returns_service_success_result_unchanged(self, git_ops: DotGitService) -> None:
        expected = CommandResult(success=True)
        git_ops.reveal_secrets.return_value = expected

        result = reveal_all(git_ops)

        assert result is expected

    def test_returns_service_failure_result_unchanged(self, git_ops: DotGitService) -> None:
        expected = CommandResult(success=False, error="reveal failed")
        git_ops.reveal_secrets.return_value = expected

        result = reveal_all(git_ops)

        assert result is expected


class TestHideAll:
    def test_returns_error_without_calling_hide_secrets_when_tool_unavailable(self, git_ops: DotGitService) -> None:
        git_ops.is_secret_tool_available.return_value = False

        result = hide_all(git_ops)

        assert result.success is False
        assert result.error == "git-secret not installed"
        git_ops.hide_secrets.assert_not_called()

    def test_calls_hide_secrets_with_no_arguments(self, git_ops: DotGitService) -> None:
        hide_all(git_ops)

        git_ops.hide_secrets.assert_called_once_with()

    def test_returns_service_success_result_unchanged(self, git_ops: DotGitService) -> None:
        expected = CommandResult(success=True)
        git_ops.hide_secrets.return_value = expected

        result = hide_all(git_ops)

        assert result is expected

    def test_returns_service_failure_result_unchanged(self, git_ops: DotGitService) -> None:
        expected = CommandResult(success=False, error="hide failed")
        git_ops.hide_secrets.return_value = expected

        result = hide_all(git_ops)

        assert result is expected
