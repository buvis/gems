from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from bim.commands.shared.os_open import open_in_os


class TestOpenInOs:
    @patch("bim.commands.shared.os_open.subprocess.Popen")
    @patch("bim.commands.shared.os_open.platform.system", return_value="Darwin")
    def test_darwin_uses_open(self, _sys: object, mock_popen: object) -> None:
        open_in_os(Path("/tmp/test.md"))
        mock_popen.assert_called_once_with(["open", "/tmp/test.md"])  # type: ignore[union-attr]

    @patch("bim.commands.shared.os_open.subprocess.Popen")
    @patch("bim.commands.shared.os_open.platform.system", return_value="Linux")
    def test_linux_uses_xdg_open(self, _sys: object, mock_popen: object) -> None:
        open_in_os("/tmp/test.md")
        mock_popen.assert_called_once_with(["xdg-open", "/tmp/test.md"])  # type: ignore[union-attr]

    @patch("os.startfile", create=True)
    @patch("bim.commands.shared.os_open.platform.system", return_value="Windows")
    def test_windows_uses_startfile(self, _sys: object, mock_start: object) -> None:
        open_in_os(Path("/tmp/test.md"))
        mock_start.assert_called_once_with("/tmp/test.md")  # type: ignore[union-attr]
