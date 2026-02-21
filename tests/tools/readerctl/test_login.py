from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.result import FatalError
from readerctl.commands.login.login import CommandLogin


class TestCommandLogin:
    def test_valid_token_from_file(self, tmp_path) -> None:
        token_file = tmp_path / "token.txt"
        token_file.write_text("valid-token\n")

        mock_response = MagicMock()
        mock_response.is_ok.return_value = True

        with patch("readerctl.commands.login.login.ReaderAPIAdapter.check_token", return_value=mock_response):
            cmd = CommandLogin(token_file=token_file)
            result = cmd.execute()

        assert result.success
        assert result.metadata["token"] == "valid-token"

    def test_invalid_token_raises_fatal(self, tmp_path) -> None:
        token_file = tmp_path / "token.txt"
        token_file.write_text("bad-token\n")

        mock_response = MagicMock()
        mock_response.is_ok.return_value = False
        mock_response.code = 401
        mock_response.message = "Unauthorized"

        with (
            patch("readerctl.commands.login.login.ReaderAPIAdapter.check_token", return_value=mock_response),
            pytest.raises(FatalError, match="Token check failed"),
        ):
            cmd = CommandLogin(token_file=token_file)
            cmd.execute()

    def test_missing_file_prompts_for_token(self, tmp_path) -> None:
        token_file = tmp_path / "nonexistent" / "token.txt"

        mock_response = MagicMock()
        mock_response.is_ok.return_value = True

        with (
            patch("readerctl.commands.login.login.getpass.getpass", return_value="new-token"),
            patch("readerctl.commands.login.login.ReaderAPIAdapter.check_token", return_value=mock_response),
        ):
            cmd = CommandLogin(token_file=token_file)
            result = cmd.execute()

        assert result.success
        assert result.metadata["token"] == "new-token"
        assert token_file.read_text() == "new-token"
