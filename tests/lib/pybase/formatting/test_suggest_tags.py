from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

from buvis.pybase.formatting.string_operator.suggest_tags import suggest_tags

URLOPEN = "buvis.pybase.formatting.string_operator.suggest_tags.urllib.request.urlopen"
CONSOLE = "buvis.pybase.formatting.string_operator.suggest_tags.console"


def _mock_response(body_dict):
    resp = MagicMock()
    resp.read.return_value = json.dumps(body_dict).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestSuggestTags:
    def test_returns_tags_from_ollama(self):
        mock_resp = _mock_response({"response": '["python", "cli-tool"]'})

        with patch(URLOPEN, return_value=mock_resp) as mock_urlopen:
            result = suggest_tags("some text", "llama3.2:3b", "http://localhost:11434")

        assert result == ["python", "cli-tool"]
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data)
        assert body["model"] == "llama3.2:3b"
        assert "some text" in body["prompt"]

    def test_connection_error_returns_empty(self):
        with (
            patch(URLOPEN, side_effect=urllib.error.URLError("offline")),
            patch(CONSOLE) as mock_console,
        ):
            result = suggest_tags("text", "model", "http://localhost:11434")

        assert result == []
        mock_console.warning.assert_called_once()

    def test_extracts_json_array_from_surrounding_text(self):
        mock_resp = _mock_response({"response": 'Here are tags: ["a", "b"] hope that helps'})

        with patch(URLOPEN, return_value=mock_resp):
            result = suggest_tags("text", "model", "http://localhost:11434")

        assert result == ["a", "b"]

    def test_invalid_json_returns_empty(self):
        mock_resp = _mock_response({"response": "no json here"})

        with patch(URLOPEN, return_value=mock_resp):
            result = suggest_tags("text", "model", "http://localhost:11434")

        assert result == []

    def test_filters_non_string_items(self):
        mock_resp = _mock_response({"response": '["valid", 123, "also-valid"]'})

        with patch(URLOPEN, return_value=mock_resp):
            result = suggest_tags("text", "model", "http://localhost:11434")

        assert result == ["valid", "also-valid"]
