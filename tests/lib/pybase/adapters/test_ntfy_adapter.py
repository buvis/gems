from __future__ import annotations

import base64
import urllib.error
from email.header import decode_header

import pytest
from buvis.pybase.adapters.ntfy import build_ntfy_request, send_ntfy


class TestNtfyAdapter:
    def test_request_url_body_and_basic_auth(self) -> None:
        request = build_ntfy_request(
            "https://ntfy.example///", "sysup", "sysup on host", "failed brew: bööm", "user:päss"
        )
        assert request.full_url == "https://ntfy.example/sysup"
        assert request.get_method() == "POST"
        assert request.data == "failed brew: bööm".encode()
        assert request.get_header("Authorization") == "Basic " + base64.b64encode("user:päss".encode()).decode()
        assert request.get_header("User-agent") == "buvis-gems/ntfy"
        assert request.get_header("Tags") == "computer"
        assert request.get_header("Title") == "sysup on host"

    @pytest.mark.parametrize("title", ["sysup on 東京", "sysup\rhost", "sysup\nhost", "sysup\r\nhost"])
    def test_non_latin1_title_is_rfc2047_encoded(self, title: str) -> None:
        request = build_ntfy_request("https://ntfy.example", "sysup", title, "message")
        header = request.get_header("Title")
        assert header.startswith("=?UTF-8?B?")
        assert "\r" not in header
        assert "\n" not in header
        value, charset = decode_header(header)[0]
        assert value.decode(charset) == title

    def test_latin1_title_needs_no_encoding_or_auth(self) -> None:
        request = build_ntfy_request("https://ntfy.example", "sysup", "sysup on hôte", "message")
        assert request.get_header("Title") == "sysup on hôte"
        assert request.get_header("Authorization") is None

    def test_http_error_returns_reason(self, mocker) -> None:
        opener = mocker.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError("https://ntfy.example/sysup", 403, "Forbidden", {}, None),
        )
        assert send_ntfy("https://ntfy.example", "sysup", "title", "message") == "HTTP 403"
        opener.assert_called_once()

    def test_success_returns_none(self, mocker) -> None:
        opener = mocker.patch("urllib.request.urlopen")
        assert send_ntfy("https://ntfy.example", "sysup", "title", "message") is None
        opener.assert_called_once()
        assert opener.call_args.kwargs == {"timeout": 5.0}
        opener.return_value.__exit__.assert_called_once()

    @pytest.mark.parametrize(
        "error",
        [urllib.error.URLError("offline"), TimeoutError("late"), OSError("broken"), ValueError("invalid")],
    )
    def test_send_errors_return_reason(self, mocker, error: Exception) -> None:
        mocker.patch("urllib.request.urlopen", side_effect=error)
        reason = send_ntfy("https://ntfy.example", "sysup", "title", "message", timeout=1.5)
        assert reason == f"{type(error).__name__}: {error}"

    @pytest.mark.parametrize("error", [None, urllib.error.URLError("offline")])
    def test_adapter_prints_nothing(self, mocker, capsys, error) -> None:
        mocker.patch("urllib.request.urlopen", side_effect=error)
        send_ntfy("https://ntfy.example", "sysup", "title", "message")
        assert capsys.readouterr() == ("", "")

    def test_malformed_url_returns_reason(self, mocker, capsys) -> None:
        opener = mocker.patch("urllib.request.urlopen")
        reason = send_ntfy("not-a-url", "sysup", "title", "message")
        assert reason.startswith("ValueError: ")
        opener.assert_not_called()
        assert capsys.readouterr() == ("", "")
