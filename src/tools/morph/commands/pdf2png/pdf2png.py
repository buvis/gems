from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from buvis.pybase.result import CommandResult, FatalError
from PIL import Image


class CommandPdf2Png:
    def __init__(self, files: tuple[str, ...], dpi: int = 200) -> None:
        self.files = files
        self.dpi = dpi

        if shutil.which("pdftoppm") is None:
            install_hint = self._get_install_hint()
            raise FatalError(f"Missing required tool: pdftoppm. Install with: {install_hint}")

    def execute(self) -> CommandResult:
        warnings: list[str] = []
        processed = 0

        for file_name in self.files:
            path = Path(file_name)
            out_path = path.with_suffix(".png")

            if out_path.exists():
                warnings.append(f"Output already exists, skipped: {out_path}")
                continue

            with tempfile.TemporaryDirectory() as tmp_name:
                tmp = Path(tmp_name)

                render_result = subprocess.run(
                    ["pdftoppm", "-png", "-r", str(self.dpi), str(path), str(tmp / "page")],
                    capture_output=True,
                    check=False,
                )
                if render_result.returncode != 0:
                    warnings.append(f"Failed to render {path}")
                    continue

                pages = sorted(tmp.glob("page-*.png"))
                if not pages:
                    warnings.append(f"No pages rendered from {path}")
                    continue

                self._stack(pages, out_path)

            processed += 1

        return CommandResult(
            success=True,
            output=f"Processed {processed} file(s)",
            warnings=warnings,
        )

    @staticmethod
    def _stack(pages: list[Path], out_path: Path) -> None:
        images = [Image.open(page) for page in pages]
        width = max(image.width for image in images)
        height = sum(image.height for image in images)
        canvas = Image.new("RGB", (width, height), "white")

        y = 0
        for image in images:
            canvas.paste(image, (0, y))
            y += image.height

        canvas.save(out_path)

    @staticmethod
    def _get_install_hint() -> str:
        if sys.platform == "darwin":
            return "brew install poppler"
        if sys.platform.startswith("linux"):
            return "apt install poppler-utils"
        return "Install pdftoppm"
