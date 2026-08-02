from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, call, patch

import pytest
from buvis.pybase.result import FatalError
from morph.commands.pdf2png.pdf2png import CommandPdf2Png


class TestPdf2PngExecute:
    def test_process_pdf(self, tmp_path) -> None:
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        with (
            patch("morph.commands.pdf2png.pdf2png.shutil.which", return_value="/usr/bin/pdftoppm"),
            patch("morph.commands.pdf2png.pdf2png.subprocess.run") as mock_run,
            patch("morph.commands.pdf2png.pdf2png.tempfile.TemporaryDirectory") as mock_tmpdir,
            patch("morph.commands.pdf2png.pdf2png.CommandPdf2Png._stack") as mock_stack,
        ):
            mock_tmpdir.return_value.__enter__.return_value = str(tmp_path)
            mock_run.return_value = subprocess.CompletedProcess(args=["pdftoppm"], returncode=0)
            (tmp_path / "page-1.png").write_bytes(b"fake")
            (tmp_path / "page-2.png").write_bytes(b"fake")

            result = CommandPdf2Png(files=(str(pdf),)).execute()

        assert result.success
        assert result.output == "Processed 1 file(s)"
        assert result.warnings == []
        assert mock_run.call_count == 1
        assert mock_stack.call_count == 1
        stacked_pages = mock_stack.call_args.args[0]
        assert [p.name for p in stacked_pages] == ["page-1.png", "page-2.png"]

    def test_output_already_exists(self, tmp_path) -> None:
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        (tmp_path / "sample.png").write_bytes(b"existing")

        with patch("morph.commands.pdf2png.pdf2png.shutil.which", return_value="/usr/bin/pdftoppm"):
            result = CommandPdf2Png(files=(str(pdf),)).execute()

        assert result.success
        assert result.output == "Processed 0 file(s)"
        assert any("Output already exists" in warning for warning in result.warnings)

    def test_render_fails(self, tmp_path) -> None:
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        with (
            patch("morph.commands.pdf2png.pdf2png.shutil.which", return_value="/usr/bin/pdftoppm"),
            patch("morph.commands.pdf2png.pdf2png.subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(args=["pdftoppm"], returncode=1)
            result = CommandPdf2Png(files=(str(pdf),)).execute()

        assert result.success
        assert result.output == "Processed 0 file(s)"
        assert any("Failed to render" in warning for warning in result.warnings)

    def test_no_pages_rendered(self, tmp_path) -> None:
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        with (
            patch("morph.commands.pdf2png.pdf2png.shutil.which", return_value="/usr/bin/pdftoppm"),
            patch("morph.commands.pdf2png.pdf2png.subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(args=["pdftoppm"], returncode=0)
            result = CommandPdf2Png(files=(str(pdf),)).execute()

        assert result.success
        assert result.output == "Processed 0 file(s)"
        assert any("No pages rendered" in warning for warning in result.warnings)


class TestPdf2PngMissingTool:
    def test_missing_pdftoppm(self) -> None:
        with patch("morph.commands.pdf2png.pdf2png.shutil.which", return_value=None):
            with pytest.raises(FatalError, match="pdftoppm"):
                CommandPdf2Png(files=("a.pdf",))


class TestPdf2PngInstallHint:
    def test_darwin(self) -> None:
        with patch.object(sys, "platform", "darwin"):
            hint = CommandPdf2Png._get_install_hint()
        assert "brew" in hint

    def test_linux(self) -> None:
        with patch.object(sys, "platform", "linux"):
            hint = CommandPdf2Png._get_install_hint()
        assert "apt" in hint

    def test_other(self) -> None:
        with patch.object(sys, "platform", "win32"):
            hint = CommandPdf2Png._get_install_hint()
        assert "pdftoppm" in hint


class TestPdf2PngStack:
    def test_stack_stitches_vertically(self, tmp_path) -> None:
        page1 = MagicMock(width=100, height=50)
        page2 = MagicMock(width=100, height=30)
        out_path = tmp_path / "out.png"

        with patch("morph.commands.pdf2png.pdf2png.Image") as mock_image:
            mock_image.open.side_effect = [page1, page2]
            canvas = MagicMock()
            mock_image.new.return_value = canvas

            CommandPdf2Png._stack([tmp_path / "page-1.png", tmp_path / "page-2.png"], out_path)

        mock_image.new.assert_called_once_with("RGB", (100, 80), "white")
        assert canvas.paste.call_args_list == [call(page1, (0, 0)), call(page2, (0, 50))]
        canvas.save.assert_called_once_with(out_path)
