from __future__ import annotations

import subprocess
from unittest.mock import Mock, patch

from buvis.pybase.adapters.uv.uv import UvAdapter


class TestEnsureUv:
    """Tests for UvAdapter.ensure_uv()."""

    @patch("buvis.pybase.adapters.uv.uv.shutil.which")
    def test_does_nothing_when_uv_available(self, mock_which: Mock) -> None:
        """Test that ensure_uv returns early when uv is already installed."""
        mock_which.return_value = "/usr/bin/uv"
        UvAdapter.ensure_uv()
        mock_which.assert_called_once_with("uv")

    @patch("buvis.pybase.adapters.uv.uv.subprocess.check_call")
    @patch("buvis.pybase.adapters.uv.uv.platform.system")
    @patch("buvis.pybase.adapters.uv.uv.shutil.which")
    def test_installs_uv_on_unix(
        self,
        mock_which: Mock,
        mock_system: Mock,
        mock_check_call: Mock,
    ) -> None:
        """Test uv installation on Unix systems (Darwin/Linux)."""
        mock_which.return_value = None
        mock_system.return_value = "Darwin"

        UvAdapter.ensure_uv()

        mock_check_call.assert_called_once()
        call_args = mock_check_call.call_args
        assert "curl" in call_args[0][0]
        assert call_args[1]["shell"] is True

    @patch("buvis.pybase.adapters.uv.uv.subprocess.check_call")
    @patch("buvis.pybase.adapters.uv.uv.platform.system")
    @patch("buvis.pybase.adapters.uv.uv.shutil.which")
    def test_installs_uv_on_windows(
        self,
        mock_which: Mock,
        mock_system: Mock,
        mock_check_call: Mock,
    ) -> None:
        """Test uv installation on Windows."""
        mock_which.return_value = None
        mock_system.return_value = "Windows"

        UvAdapter.ensure_uv()

        mock_check_call.assert_called_once()
        call_args = mock_check_call.call_args
        assert call_args[0][0][0] == "powershell"

    @patch("buvis.pybase.adapters.uv.uv.sys.exit")
    @patch("buvis.pybase.adapters.uv.uv.subprocess.check_call")
    @patch("buvis.pybase.adapters.uv.uv.platform.system")
    @patch("buvis.pybase.adapters.uv.uv.shutil.which")
    def test_exits_on_install_failure(
        self,
        mock_which: Mock,
        mock_system: Mock,
        mock_check_call: Mock,
        mock_exit: Mock,
    ) -> None:
        """Test that sys.exit(1) is called when installation fails."""
        mock_which.return_value = None
        mock_system.return_value = "Darwin"
        mock_check_call.side_effect = subprocess.CalledProcessError(1, "curl")

        UvAdapter.ensure_uv()

        mock_exit.assert_called_once_with(1)
