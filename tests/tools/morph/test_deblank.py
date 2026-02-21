from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest
from buvis.pybase.result import FatalError
from morph.commands.deblank.deblank import CommandDeblank


class TestDeblanknkPages:
    def test_collect_non_blank_pages_basic(self) -> None:
        text = "page one\x0c   \x0cpage three"

        pages = CommandDeblank._collect_non_blank_pages(text)

        assert pages == [1, 3]

    def test_collect_non_blank_pages_all_blank(self) -> None:
        text = "   \x0c\t \x0c\n"

        pages = CommandDeblank._collect_non_blank_pages(text)

        assert pages == []

    def test_collect_non_blank_pages_single_page(self) -> None:
        pages = CommandDeblank._collect_non_blank_pages("single page content")

        assert pages == [1]


class TestDeblankRanges:
    def test_to_pdftk_ranges_consecutive(self) -> None:
        assert CommandDeblank._to_pdftk_ranges([1, 2, 3]) == "1-3"

    def test_to_pdftk_ranges_gaps(self) -> None:
        assert CommandDeblank._to_pdftk_ranges([1, 2, 5, 6, 8]) == "1-2 5-6 8-8"

    def test_to_pdftk_ranges_single(self) -> None:
        assert CommandDeblank._to_pdftk_ranges([3]) == "3-3"


class TestDeblankExecute:
    def test_process_pdf(self, tmp_path) -> None:
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        with (
            patch("morph.commands.deblank.deblank.shutil.which", return_value="/usr/bin/tool"),
            patch("morph.commands.deblank.deblank.subprocess.run") as mock_run,
            patch("morph.commands.deblank.deblank.Path.rename") as mock_rename,
        ):
            mock_run.side_effect = [
                subprocess.CompletedProcess(args=["pdftotext"], returncode=0, stdout="A\x0c \x0cB"),
                subprocess.CompletedProcess(args=["pdftk"], returncode=0, stdout=b""),
            ]

            result = CommandDeblank(files=(str(pdf),)).execute()

        assert result.success
        assert result.output == "Processed 1 file(s)"
        assert result.warnings == []
        assert result.error is None
        assert mock_run.call_count == 2
        assert mock_rename.called

    def test_no_non_blank_pages(self, tmp_path) -> None:
        pdf = tmp_path / "blank.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        with (
            patch("morph.commands.deblank.deblank.shutil.which", return_value="/usr/bin/tool"),
            patch("morph.commands.deblank.deblank.subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=["pdftotext"],
                returncode=0,
                stdout=" \x0c \x0c\n",
            )
            result = CommandDeblank(files=(str(pdf),)).execute()

        assert result.success
        assert result.output == "Processed 0 file(s)"
        assert result.error is None
        assert any("No non-blank pages found" in warning for warning in result.warnings)

    def test_backup_exists(self, tmp_path) -> None:
        pdf = tmp_path / "book.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        (tmp_path / "book.pdf.old").write_bytes(b"old")

        with (
            patch("morph.commands.deblank.deblank.shutil.which", return_value="/usr/bin/tool"),
            patch("morph.commands.deblank.deblank.subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=["pdftotext"],
                returncode=0,
                stdout="content",
            )
            result = CommandDeblank(files=(str(pdf),)).execute()

        assert result.success
        assert result.output == "Processed 0 file(s)"
        assert result.error is None
        assert any("Backup already exists" in warning for warning in result.warnings)
        assert mock_run.call_count == 1

    def test_pdftotext_fails(self, tmp_path) -> None:
        pdf = tmp_path / "bad.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        with (
            patch("morph.commands.deblank.deblank.shutil.which", return_value="/usr/bin/tool"),
            patch("morph.commands.deblank.deblank.subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=["pdftotext"],
                returncode=1,
                stdout="",
            )
            result = CommandDeblank(files=(str(pdf),)).execute()

        assert result.success
        assert result.output == "Processed 0 file(s)"
        assert result.error is None
        assert any("Failed to extract text" in warning for warning in result.warnings)

    def test_pdftk_fails(self, tmp_path) -> None:
        pdf = tmp_path / "fail.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        with (
            patch("morph.commands.deblank.deblank.shutil.which", return_value="/usr/bin/tool"),
            patch("morph.commands.deblank.deblank.subprocess.run") as mock_run,
            patch("morph.commands.deblank.deblank.Path.rename"),
            patch("morph.commands.deblank.deblank.CommandDeblank._restore_original") as mock_restore,
        ):
            mock_run.side_effect = [
                subprocess.CompletedProcess(args=["pdftotext"], returncode=0, stdout="A"),
                subprocess.CompletedProcess(args=["pdftk"], returncode=1, stdout=b""),
            ]
            result = CommandDeblank(files=(str(pdf),)).execute()

        assert result.success
        assert result.output == "Processed 0 file(s)"
        assert result.error is None
        assert any("Failed to deblank" in warning for warning in result.warnings)
        mock_restore.assert_called_once()


class TestDeblankMissingTools:
    def test_missing_pdftotext(self) -> None:
        with patch(
            "morph.commands.deblank.deblank.shutil.which",
            side_effect=lambda name: None if name == "pdftotext" else "/usr/bin/tool",
        ):
            with pytest.raises(FatalError, match="pdftotext"):
                CommandDeblank(files=("a.pdf",))

    def test_missing_pdftk(self) -> None:
        with patch(
            "morph.commands.deblank.deblank.shutil.which",
            side_effect=lambda name: None if name == "pdftk" else "/usr/bin/tool",
        ):
            with pytest.raises(FatalError, match="pdftk"):
                CommandDeblank(files=("a.pdf",))

    def test_both_missing(self) -> None:
        with patch("morph.commands.deblank.deblank.shutil.which", return_value=None):
            with pytest.raises(FatalError) as exc:
                CommandDeblank(files=("a.pdf",))

        assert "pdftotext" in str(exc.value)
        assert "pdftk" in str(exc.value)
