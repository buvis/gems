from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from buvis.pybase.result import CommandResult, FatalError


class CommandDeblank:
    def __init__(self, files: tuple[str, ...]) -> None:
        self.files = files

        missing: list[str] = []
        if shutil.which("pdftotext") is None:
            missing.append("pdftotext")
        if shutil.which("pdftk") is None:
            missing.append("pdftk")
        if missing:
            install_hint = self._get_install_hint()
            raise FatalError(f"Missing required tools: {', '.join(missing)}. Install with: {install_hint}")

    def execute(self) -> CommandResult:
        warnings: list[str] = []
        processed = 0

        for file_name in self.files:
            path = Path(file_name)

            text_result = subprocess.run(
                ["pdftotext", str(path), "-"],
                capture_output=True,
                text=True,
                check=False,
            )
            if text_result.returncode != 0:
                warnings.append(f"Failed to extract text from {path}")
                continue

            non_blank_pages = self._collect_non_blank_pages(text_result.stdout)
            if not non_blank_pages:
                warnings.append(f"No non-blank pages found in {path}")
                continue

            page_ranges = self._to_pdftk_ranges(non_blank_pages)
            old_path = path.with_suffix(f"{path.suffix}.old")

            if old_path.exists():
                warnings.append(f"Backup already exists, skipped: {old_path}")
                continue

            path.rename(old_path)

            cat_result = subprocess.run(
                ["pdftk", str(old_path), "cat", *page_ranges.split(), "output", str(path)],
                capture_output=True,
                check=False,
            )
            if cat_result.returncode != 0:
                warnings.append(f"Failed to deblank {path}")
                self._restore_original(path, old_path, warnings)
                continue

            processed += 1

        return CommandResult(
            success=True,
            output=f"Processed {processed} file(s)",
            warnings=warnings,
        )

    @staticmethod
    def _get_install_hint() -> str:
        if sys.platform == "darwin":
            return "brew install poppler pdftk-java"
        if sys.platform.startswith("linux"):
            return "apt install poppler-utils pdftk-java"
        return "Install pdftotext and pdftk"

    @staticmethod
    def _collect_non_blank_pages(text: str) -> list[int]:
        pages: list[int] = []
        page_number = 1
        blank = True

        for char in text:
            if char == "\x0c":
                if not blank:
                    pages.append(page_number)
                page_number += 1
                blank = True
                continue
            if not char.isspace():
                blank = False

        if not blank:
            pages.append(page_number)

        return pages

    @staticmethod
    def _to_pdftk_ranges(page_numbers: list[int]) -> str:
        ranges: list[str] = []
        start = page_numbers[0]
        end = page_numbers[0]

        for page in page_numbers[1:]:
            if page == end + 1:
                end = page
                continue
            ranges.append(f"{start}-{end}")
            start = page
            end = page
        ranges.append(f"{start}-{end}")

        return " ".join(ranges)

    @staticmethod
    def _restore_original(path: Path, old_path: Path, warnings: list[str]) -> None:
        try:
            if path.exists():
                path.unlink()
            if old_path.exists():
                old_path.rename(path)
        except OSError as exc:
            warnings.append(f"Failed to restore original for {path}: {exc}")
