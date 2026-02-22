from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from morph.commands.deblank.deblank import CommandDeblank


class TestGetInstallHint:
    def test_darwin(self) -> None:
        with patch.object(sys, "platform", "darwin"):
            hint = CommandDeblank._get_install_hint()
        assert "brew" in hint

    def test_linux(self) -> None:
        with patch.object(sys, "platform", "linux"):
            hint = CommandDeblank._get_install_hint()
        assert "apt" in hint

    def test_other(self) -> None:
        with patch.object(sys, "platform", "win32"):
            hint = CommandDeblank._get_install_hint()
        assert "pdftotext" in hint
        assert "pdftk" in hint


class TestRestoreOriginal:
    def test_restore_success(self, tmp_path: Path) -> None:
        original = tmp_path / "test.pdf"
        backup = tmp_path / "test.pdf.old"
        backup.write_bytes(b"backup data")
        warnings: list[str] = []

        CommandDeblank._restore_original(original, backup, warnings)

        assert original.exists()
        assert not backup.exists()
        assert warnings == []

    def test_restore_no_backup(self, tmp_path: Path) -> None:
        original = tmp_path / "test.pdf"
        backup = tmp_path / "test.pdf.old"
        warnings: list[str] = []

        CommandDeblank._restore_original(original, backup, warnings)

        assert not original.exists()
        assert warnings == []

    def test_restore_os_error(self, tmp_path: Path) -> None:
        original = tmp_path / "test.pdf"
        backup = tmp_path / "test.pdf.old"
        backup.write_bytes(b"backup data")
        warnings: list[str] = []

        with patch.object(Path, "rename", side_effect=OSError("Permission denied")):
            CommandDeblank._restore_original(original, backup, warnings)

        assert len(warnings) == 1
        assert "Permission denied" in warnings[0]


class TestDeblankMultipleFiles:
    def test_multiple_pdfs(self, tmp_path: Path) -> None:
        pdf1 = tmp_path / "a.pdf"
        pdf2 = tmp_path / "b.pdf"
        pdf1.write_bytes(b"%PDF-1.4")
        pdf2.write_bytes(b"%PDF-1.4")

        with (
            patch(
                "morph.commands.deblank.deblank.shutil.which",
                return_value="/usr/bin/tool",
            ),
            patch("morph.commands.deblank.deblank.subprocess.run") as mock_run,
            patch("morph.commands.deblank.deblank.Path.rename"),
        ):
            mock_run.side_effect = [
                subprocess.CompletedProcess(args=["pdftotext"], returncode=0, stdout="A\x0cB"),
                subprocess.CompletedProcess(args=["pdftk"], returncode=0, stdout=b""),
                subprocess.CompletedProcess(args=["pdftotext"], returncode=0, stdout="C"),
                subprocess.CompletedProcess(args=["pdftk"], returncode=0, stdout=b""),
            ]

            result = CommandDeblank(files=(str(pdf1), str(pdf2))).execute()

        assert result.success
        assert result.output == "Processed 2 file(s)"
