from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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

    @patch("hello_world.commands.diagnostics.diagnostics.requires", return_value=["pyfiglet>=0.8"])
    @patch("hello_world.commands.diagnostics.diagnostics.distributions")
    def test_lists_matching_dependency(self, mock_dist, _mock_req) -> None:
        dist = MagicMock()
        dist.metadata = {"Name": "pyfiglet"}
        dist.version = "1.0.0"
        dist._path = Path("/site-packages/pyfiglet-1.0.0.dist-info/METADATA")
        mock_dist.return_value = [dist]

        result = CommandDiagnostics().execute()

        assert result.success
        assert "pyfiglet==1.0.0" in result.output

    @patch("hello_world.commands.diagnostics.diagnostics.requires", return_value=["pyfiglet>=0.8"])
    @patch("hello_world.commands.diagnostics.diagnostics.distributions")
    def test_lists_dep_without_path(self, mock_dist, _mock_req) -> None:
        dist = MagicMock()
        dist.metadata = {"Name": "pyfiglet"}
        dist.version = "1.0.0"
        del dist._path
        mock_dist.return_value = [dist]

        result = CommandDiagnostics().execute()

        assert result.success
        assert "pyfiglet==1.0.0 (unknown)" in result.output

    @patch("hello_world.commands.diagnostics.diagnostics.requires", return_value=["pyfiglet>=0.8"])
    @patch("hello_world.commands.diagnostics.diagnostics.distributions")
    def test_skips_non_matching_dep(self, mock_dist, _mock_req) -> None:
        dist = MagicMock()
        dist.metadata = {"Name": "unrelated-pkg"}
        dist.version = "2.0.0"
        mock_dist.return_value = [dist]

        result = CommandDiagnostics().execute()

        assert result.success
        assert "unrelated-pkg" not in result.output
