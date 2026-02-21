from __future__ import annotations

from hello_world.commands.list_fonts.list_fonts import CommandListFonts


class TestCommandListFonts:
    def test_execute_returns_font_list(self) -> None:
        result = CommandListFonts().execute()
        assert result.success
        assert len(result.output) > 0
        # pyfiglet always includes "banner" font
        assert "banner" in result.output
