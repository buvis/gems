from unittest.mock import patch

from hello_world.commands.print_figlet.print_figlet import CommandPrintFiglet


class TestCommandPrintFiglet:
    def test_execute_with_figlet(self, capsys):
        cmd = CommandPrintFiglet(font="banner", text="World")
        cmd.execute()
        output = capsys.readouterr().out
        # banner font renders as ASCII art, just check output is non-trivial
        assert len(output.strip()) > 10

    def test_execute_fallback_without_pyfiglet(self, capsys):
        with patch.dict("sys.modules", {"pyfiglet": None}):
            cmd = CommandPrintFiglet(font="doom", text="Test")
            cmd.execute()
            output = capsys.readouterr().out
            assert "Hello Test!" in output

    def test_stores_font_and_text(self):
        cmd = CommandPrintFiglet(font="doom", text="World")
        assert cmd.font == "doom"
        assert cmd.text == "World"
