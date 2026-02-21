from __future__ import annotations

from unittest.mock import MagicMock, patch

from readerctl.commands.add.add import CommandAdd


class TestCommandAdd:
    def test_add_url_success(self) -> None:
        mock_response = MagicMock()
        mock_response.is_ok.return_value = True
        mock_response.message = "Added"

        with patch("readerctl.commands.add.add.ReaderAPIAdapter") as mock_api_cls:
            mock_api_cls.return_value.add_url.return_value = mock_response
            cmd = CommandAdd(token="test-token")
            result = cmd.execute("https://example.com")

        assert result.success
        assert result.output == "Added"

    def test_add_url_failure(self) -> None:
        mock_response = MagicMock()
        mock_response.is_ok.return_value = False
        mock_response.message = "Already exists"

        with patch("readerctl.commands.add.add.ReaderAPIAdapter") as mock_api_cls:
            mock_api_cls.return_value.add_url.return_value = mock_response
            cmd = CommandAdd(token="test-token")
            result = cmd.execute("https://example.com")

        assert not result.success
        assert result.error == "Already exists"
