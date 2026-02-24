from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from puc.cli import cli


class TestPucCommands:
    @patch("puc.commands.strip.strip.CommandStrip")
    def test_strip_success(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.write_bytes(b"\xff\xd8\xff")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Stripped 1 file")
        result = runner.invoke(cli, ["strip", str(photo)])
        assert result.exit_code == 0
