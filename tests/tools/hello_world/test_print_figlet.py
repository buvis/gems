from __future__ import annotations

from unittest.mock import patch

from hello_world.commands.print_figlet.print_figlet import CommandPrintFiglet


class TestCommandPrintFiglet:
    def test_execute_with_figlet(self):
        cmd = CommandPrintFiglet(font="banner", text="World")
        result = cmd.execute()
        assert result.success
        assert len(result.output.strip()) > 10

    def test_execute_fallback_without_pyfiglet(self):
        with patch.dict("sys.modules", {"pyfiglet": None}):
            cmd = CommandPrintFiglet(font="doom", text="Test")
            result = cmd.execute()
            assert result.success
            assert "Hello Test!" in result.output

    def test_stores_font_and_text(self):
        cmd = CommandPrintFiglet(font="doom", text="World")
        assert cmd.font == "doom"
        assert cmd.text == "World"
