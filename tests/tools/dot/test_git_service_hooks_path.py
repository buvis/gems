from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dot.git.service import DotGitService


@pytest.fixture
def shell() -> MagicMock:
    mock = MagicMock()
    mock.exe.return_value = ("", "")
    return mock


@pytest.fixture
def git_service(shell: MagicMock) -> DotGitService:
    svc = DotGitService(shell=shell, dotfiles_root="/home/user/dotfiles")
    shell.exe.reset_mock()
    return svc


class TestHooksPathQuery:
    def test_queries_git_config_exactly_once_against_dotfiles_root(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.exe.return_value = ("", "/opt/hooks\n")

        git_service.hooks_path()

        shell.exe.assert_called_once_with("cfg config core.hooksPath", Path("/home/user/dotfiles"))


class TestHooksPathUnset:
    def test_returns_none_when_key_is_unset(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("Command failed with exit code 1", "")

        assert git_service.hooks_path() is None

    def test_returns_none_when_error_is_set_even_if_stdout_has_value(
        self, git_service: DotGitService, shell: MagicMock
    ) -> None:
        shell.exe.return_value = ("Command failed with exit code 1", "/opt/hooks\n")

        assert git_service.hooks_path() is None

    def test_returns_none_for_empty_stdout(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "")

        assert git_service.hooks_path() is None

    def test_returns_none_for_whitespace_only_stdout(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "  \n\t\n")

        assert git_service.hooks_path() is None


class TestHooksPathResolution:
    def test_expands_tilde_to_home(
        self,
        git_service: DotGitService,
        shell: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        shell.exe.return_value = ("", "~/.config/buvis/hooks\n")

        assert git_service.hooks_path() == tmp_path / ".config/buvis/hooks"

    def test_resolves_relative_value_against_dotfiles_root(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "hooks\n")

        assert git_service.hooks_path() == Path("/home/user/dotfiles/hooks")

    def test_returns_absolute_value_unchanged(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "/opt/hooks\n")

        assert git_service.hooks_path() == Path("/opt/hooks")

    def test_strips_surrounding_whitespace_and_newline(self, git_service: DotGitService, shell: MagicMock) -> None:
        shell.exe.return_value = ("", "  /opt/hooks \n")

        assert git_service.hooks_path() == Path("/opt/hooks")
