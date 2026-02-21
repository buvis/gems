from __future__ import annotations

from unittest.mock import patch

from hello_world.commands.diagnostics.diagnostics import CommandDiagnostics


class TestCommandDiagnostics:
    @patch("hello_world.commands.diagnostics.diagnostics.requires", return_value=["pyfiglet>=0.8"])
    @patch("hello_world.commands.diagnostics.diagnostics.distributions", return_value=[])
    def test_execute_returns_success(self, _mock_dist, _mock_req) -> None:
        result = CommandDiagnostics().execute()
        assert result.success
        assert "Python:" in result.output
        assert "Script:" in result.output
        assert "Direct dependencies:" in result.output
