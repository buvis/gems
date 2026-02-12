from unittest.mock import MagicMock, patch

from readerctl.adapters.reader_api.reader_api import ReaderAPIAdapter


class TestCheckToken:
    @patch("readerctl.adapters.reader_api.reader_api.requests")
    def test_valid_token(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_requests.get.return_value = mock_response

        result = ReaderAPIAdapter.check_token("valid-token")

        assert result.is_ok() is True
        assert result.message == "Token is valid"
        mock_requests.get.assert_called_once()

    @patch("readerctl.adapters.reader_api.reader_api.requests")
    def test_invalid_token(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_requests.get.return_value = mock_response

        result = ReaderAPIAdapter.check_token("bad-token")

        assert result.is_nok() is True
        assert result.code == 401


class TestAddUrl:
    @patch("readerctl.adapters.reader_api.reader_api.requests")
    def test_add_url_success(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"url": "https://reader.example.com/doc/123"}
        mock_requests.post.return_value = mock_response

        api = ReaderAPIAdapter("test-token")
        result = api.add_url("https://example.com/article")

        assert result.is_ok() is True
        assert "added to Reader" in result.message

    @patch("readerctl.adapters.reader_api.reader_api.requests")
    def test_add_url_error(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"url": ["Invalid URL"]}
        mock_requests.post.return_value = mock_response

        api = ReaderAPIAdapter("test-token")
        result = api.add_url("not-a-url")

        assert result.is_nok() is True

    @patch("readerctl.adapters.reader_api.reader_api.time")
    @patch("readerctl.adapters.reader_api.reader_api.requests")
    @patch("readerctl.adapters.reader_api.reader_api.console")
    def test_add_url_rate_limited(self, mock_console, mock_requests, mock_time):
        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "1"}

        success = MagicMock()
        success.status_code = 201
        success.json.return_value = {"url": "https://reader.example.com/doc/1"}

        mock_requests.post.side_effect = [rate_limited, success]
        mock_console.status.return_value.__enter__ = MagicMock()
        mock_console.status.return_value.__exit__ = MagicMock()

        api = ReaderAPIAdapter("test-token")
        result = api.add_url("https://example.com/article")

        assert result.is_ok() is True
        assert mock_requests.post.call_count == 2
