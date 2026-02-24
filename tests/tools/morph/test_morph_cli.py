from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from buvis.pybase.result import FatalError
from morph.cli import cli


class TestMorphHtml2MdImportError:
    def test_html2md_import_error(self, runner, tmp_path) -> None:
        # Remove cached module so the lazy import inside html2md handler re-fires
        mod_key = "morph.commands.html2md.html2md"
        saved = sys.modules.pop(mod_key, None)
        try:
            with patch.dict(sys.modules, {mod_key: None}):
                result = runner.invoke(cli, ["html2md", str(tmp_path)])
                assert "requires the 'morph' extra" in result.output
        finally:
            if saved is not None:
                sys.modules[mod_key] = saved


class TestMorphDeblanFatalErrorPropagation:
    @patch("morph.commands.deblank.deblank.CommandDeblank")
    def test_deblank_execute_raises_fatal_error(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        mock_cmd_cls.return_value.execute.side_effect = FatalError("Broken pipe")
        result = runner.invoke(cli, ["deblank", str(pdf)])
        assert "Broken pipe" in result.output
