"""OCR runner for the bim doc pipeline.

Wraps ``ocrmypdf`` and pdfminer to extract page text, choosing among three
branches per the architecture spec: skip, redo, or full OCR.
"""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage

if TYPE_CHECKING:
    from bim.commands.doc.shared.settings_models import DocSettings

__all__ = ["OCRError", "OCRResult", "OCRRunner"]


class OCRError(Exception):
    """Raised when ``ocrmypdf`` exits with a non-zero status."""

    def __init__(self, *, stderr: str) -> None:
        super().__init__(stderr)
        self.stderr = stderr


@dataclass(frozen=True)
class OCRResult:
    """Outcome of an OCR run.

    Attributes:
        ocr_text: Extracted page text (sidecar contents or existing text layer).
        pdf_path: Path to the PDF whose text was extracted (input or new output).
        was_redone: True when the redo-OCR branch ran in place on the input.
        original_backup_path: Path to the pre-redo backup, if redo branch ran.
        mean_confidence: Heuristic confidence of the existing text layer, if known.
        pages: Page count from pdfminer.
    """

    ocr_text: str
    pdf_path: Path
    was_redone: bool
    original_backup_path: Path | None
    mean_confidence: float | None
    pages: int


def _estimate_text_confidence(text: str) -> float:
    """Heuristically score the confidence of an existing text layer.

    Returns 0.0 when the text is empty or whitespace-only, otherwise 1.0.
    Real text-layer quality is hard to assess without per-character signals,
    so we trust any extractable text by default; callers can patch this
    function to plug in a smarter heuristic.
    """
    return 0.0 if not text.strip() else 1.0


class OCRRunner:
    """Runs OCR on a PDF, choosing skip/redo/full branches per settings."""

    def __init__(self, settings: DocSettings, state_dir: Path) -> None:
        self._settings = settings
        self._state_dir = state_dir

    def run(self, pdf_path: Path) -> OCRResult:
        """Extract page text from ``pdf_path``, OCR'ing if needed."""
        original_bytes = pdf_path.read_bytes()
        sha256 = hashlib.sha256(original_bytes).hexdigest()

        existing_text = extract_text(str(pdf_path))
        with open(pdf_path, "rb") as handle:
            pages = len(list(PDFPage.get_pages(handle)))

        confidence = _estimate_text_confidence(existing_text)
        has_text = bool(existing_text.strip())

        ocr = self._settings.ocr
        below_threshold = ocr.redo_on_low_confidence and confidence < ocr.low_confidence_threshold

        if has_text and ocr.skip_text and not below_threshold:
            return OCRResult(
                ocr_text=existing_text,
                pdf_path=pdf_path,
                was_redone=False,
                original_backup_path=None,
                mean_confidence=confidence,
                pages=pages,
            )

        if has_text and below_threshold:
            return self._run_redo(pdf_path, original_bytes, sha256, pages)

        return self._run_full(pdf_path, pages)

    def _run_redo(
        self,
        pdf_path: Path,
        original_bytes: bytes,
        sha256: str,
        pages: int,
    ) -> OCRResult:
        backup_path = self._backup_original(original_bytes, sha256)
        sidecar_path = self._make_sidecar()

        languages = "+".join(self._settings.ocr.languages)
        argv = [
            "ocrmypdf",
            "--redo-ocr",
            "-l",
            languages,
            f"--sidecar={sidecar_path}",
            str(pdf_path),
            str(pdf_path),
        ]
        self._invoke(argv)
        ocr_text = sidecar_path.read_text(encoding="utf-8")

        return OCRResult(
            ocr_text=ocr_text,
            pdf_path=pdf_path,
            was_redone=True,
            original_backup_path=backup_path,
            mean_confidence=None,
            pages=pages,
        )

    def _run_full(self, pdf_path: Path, pages: int) -> OCRResult:
        sidecar_path = self._make_sidecar()
        output_handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        output_handle.close()
        output_pdf = Path(output_handle.name)

        ocr = self._settings.ocr
        languages = "+".join(ocr.languages)
        argv: list[str] = [
            "ocrmypdf",
            "-l",
            languages,
            "--oversample",
            str(ocr.oversample),
        ]
        if ocr.deskew:
            argv.append("--deskew")
        if ocr.rotate_pages:
            argv.append("--rotate-pages")
        argv.append(f"--sidecar={sidecar_path}")
        argv.append(str(pdf_path))
        argv.append(str(output_pdf))

        self._invoke(argv)
        ocr_text = sidecar_path.read_text(encoding="utf-8")

        return OCRResult(
            ocr_text=ocr_text,
            pdf_path=output_pdf,
            was_redone=False,
            original_backup_path=None,
            mean_confidence=None,
            pages=pages,
        )

    def _backup_original(self, original_bytes: bytes, sha256: str) -> Path:
        originals_dir = self._state_dir / "originals"
        originals_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = originals_dir / f"{timestamp}-{sha256[:8]}.pdf"
        backup_path.write_bytes(original_bytes)
        return backup_path

    def _make_sidecar(self) -> Path:
        handle = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        handle.close()
        return Path(handle.name)

    def _invoke(self, argv: list[str]) -> None:
        result = subprocess.run(argv, capture_output=True, check=False)
        if result.returncode != 0:
            raise OCRError(stderr=result.stderr.decode(errors="replace"))
