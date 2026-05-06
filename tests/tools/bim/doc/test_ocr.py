from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from bim.commands.doc.shared.ocr import OCRError, OCRRunner
from bim.commands.doc.shared.settings_models import DocPaths, DocSettings, OCRSettings
from pytest_mock import MockerFixture


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    d = tmp_path / "state"
    d.mkdir()
    return d


def _make_settings(
    tmp_path: Path,
    *,
    skip_text: bool = True,
    redo_on_low_confidence: bool = True,
    low_confidence_threshold: float = 0.70,
    languages: list[str] | None = None,
    oversample: int = 400,
    deskew: bool = True,
    rotate_pages: bool = True,
) -> DocSettings:
    paths = DocPaths.model_validate(
        {
            "business_root": str(tmp_path / "Business"),
            "vault_root": str(tmp_path / "Vault"),
            "state_dir": str(tmp_path / "state"),
        }
    )
    ocr = OCRSettings(
        languages=languages if languages is not None else ["ces", "eng"],
        oversample=oversample,
        deskew=deskew,
        rotate_pages=rotate_pages,
        redo_on_low_confidence=redo_on_low_confidence,
        low_confidence_threshold=low_confidence_threshold,
        skip_text=skip_text,
    )
    return DocSettings(paths=paths, ocr=ocr)


def _ok_proc() -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")


def _sidecar_writing_run(text: str) -> Any:
    """Return a side_effect that locates --sidecar=<path> in argv and writes text there."""

    def _run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        argv = args[0] if args else kwargs.get("args")
        assert argv is not None, "subprocess.run called without argv"
        sidecar_path: Path | None = None
        for token in argv:
            token_s = str(token)
            if token_s.startswith("--sidecar="):
                sidecar_path = Path(token_s.split("=", 1)[1])
                break
        if sidecar_path is not None:
            sidecar_path.parent.mkdir(parents=True, exist_ok=True)
            sidecar_path.write_text(text, encoding="utf-8")
        return _ok_proc()

    return _run


def _argv_from_call(call_args: Any) -> list[str]:
    args, kwargs = call_args
    argv = args[0] if args else kwargs["args"]
    return [str(x) for x in argv]


class _FakePage:
    """Stand-in for pdfminer's PDFPage so len(list(...)) is meaningful."""


def _pages_iter(n: int) -> Any:
    return iter([_FakePage() for _ in range(n)])


class TestOCRRunner:
    def test_skip_branch_when_text_layer_present_and_skip_text_true(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        pdf = tmp_path / "input.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        run_mock = mocker.patch("bim.commands.doc.shared.ocr.subprocess.run")
        # Long enough that the density-based confidence stays above the
        # default 0.70 threshold (~1350 chars / 2 pages ≫ 200 chars/page target).
        existing_text = "existing text layer content " * 50
        mocker.patch(
            "bim.commands.doc.shared.ocr.extract_text",
            return_value=existing_text,
        )
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(2),
        )

        settings = _make_settings(tmp_path, skip_text=True)
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        result = runner.run(pdf)

        run_mock.assert_not_called()
        assert result.was_redone is False
        assert result.original_backup_path is None
        assert result.ocr_text == existing_text
        assert result.pdf_path == pdf
        assert result.pages == 2

    def test_redo_ocr_branch_writes_backup_and_invokes_ocrmypdf_with_redo_flag(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        pdf = tmp_path / "input.pdf"
        pdf.write_bytes(b"%PDF-1.4\nbinary-bytes-for-hashing")

        # Existing text layer present, but mean confidence is low → redo branch.
        mocker.patch(
            "bim.commands.doc.shared.ocr.extract_text",
            return_value="garbled low-confidence ocr text",
        )
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(3),
        )
        # Force the implementation's confidence estimate below the threshold so
        # the redo-branch fires deterministically regardless of how it computes.
        mocker.patch(
            "bim.commands.doc.shared.ocr._estimate_text_confidence",
            return_value=0.30,
            create=True,
        )

        run_mock = mocker.patch(
            "bim.commands.doc.shared.ocr.subprocess.run",
            side_effect=_sidecar_writing_run("redone ocr text"),
        )

        settings = _make_settings(
            tmp_path,
            skip_text=False,  # disable skip so we hit redo branch deterministically
            redo_on_low_confidence=True,
            low_confidence_threshold=0.70,
        )
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        result = runner.run(pdf)

        assert run_mock.call_count == 1
        argv = _argv_from_call(run_mock.call_args)
        assert "--redo-ocr" in argv

        assert result.was_redone is True
        assert result.original_backup_path is not None
        backup = result.original_backup_path
        assert backup.exists(), "backup file must be written to disk before OCR runs"
        assert backup.parent == state_dir / "originals"
        assert backup.suffix == ".pdf"
        # Backup must be the original bytes, not the (possibly overwritten) input.
        assert backup.read_bytes() == b"%PDF-1.4\nbinary-bytes-for-hashing"
        assert result.ocr_text == "redone ocr text"
        assert result.pages == 3

    def test_full_ocr_branch_when_no_text_layer(self, tmp_path: Path, state_dir: Path, mocker: MockerFixture) -> None:
        pdf = tmp_path / "scan.pdf"
        pdf.write_bytes(b"%PDF-1.4\nimage-only")

        # No text layer → extract_text returns empty string.
        mocker.patch("bim.commands.doc.shared.ocr.extract_text", return_value="")
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(1),
        )
        run_mock = mocker.patch(
            "bim.commands.doc.shared.ocr.subprocess.run",
            side_effect=_sidecar_writing_run("freshly ocr'd page text"),
        )

        settings = _make_settings(tmp_path, languages=["ces", "eng"])
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        result = runner.run(pdf)

        assert run_mock.call_count == 1
        argv = _argv_from_call(run_mock.call_args)
        assert "--redo-ocr" not in argv
        # Languages joined by '+'
        assert "-l" in argv
        lang_idx = argv.index("-l")
        assert argv[lang_idx + 1] == "ces+eng"

        assert result.was_redone is False
        assert result.original_backup_path is None
        assert result.ocr_text == "freshly ocr'd page text"
        assert result.pages == 1

    def test_full_ocr_argv_includes_oversample_deskew_rotate_when_enabled(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        pdf = tmp_path / "scan.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        mocker.patch("bim.commands.doc.shared.ocr.extract_text", return_value="")
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(1),
        )
        run_mock = mocker.patch(
            "bim.commands.doc.shared.ocr.subprocess.run",
            side_effect=_sidecar_writing_run("text"),
        )

        settings = _make_settings(tmp_path, oversample=600, deskew=True, rotate_pages=True)
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        runner.run(pdf)

        argv = _argv_from_call(run_mock.call_args)
        assert "--oversample" in argv
        os_idx = argv.index("--oversample")
        assert argv[os_idx + 1] == "600"
        assert "--deskew" in argv
        assert "--rotate-pages" in argv

    def test_full_ocr_argv_omits_deskew_and_rotate_when_disabled(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        pdf = tmp_path / "scan.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        mocker.patch("bim.commands.doc.shared.ocr.extract_text", return_value="")
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(1),
        )
        run_mock = mocker.patch(
            "bim.commands.doc.shared.ocr.subprocess.run",
            side_effect=_sidecar_writing_run("text"),
        )

        settings = _make_settings(tmp_path, deskew=False, rotate_pages=False)
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        runner.run(pdf)

        argv = _argv_from_call(run_mock.call_args)
        assert "--deskew" not in argv
        assert "--rotate-pages" not in argv

    def test_subprocess_failure_raises_ocr_error_with_stderr(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        pdf = tmp_path / "bad.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        mocker.patch("bim.commands.doc.shared.ocr.extract_text", return_value="")
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(1),
        )
        mocker.patch(
            "bim.commands.doc.shared.ocr.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=2,
                stdout=b"",
                stderr=b"tesseract: language not installed",
            ),
        )

        settings = _make_settings(tmp_path)
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        with pytest.raises(OCRError) as excinfo:
            runner.run(pdf)
        assert excinfo.value.stderr == "tesseract: language not installed"

    def test_subprocess_invocation_uses_capture_output_and_no_check(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        pdf = tmp_path / "scan.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        mocker.patch("bim.commands.doc.shared.ocr.extract_text", return_value="")
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(1),
        )
        run_mock = mocker.patch(
            "bim.commands.doc.shared.ocr.subprocess.run",
            side_effect=_sidecar_writing_run("text"),
        )

        settings = _make_settings(tmp_path)
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        runner.run(pdf)

        _args, kwargs = run_mock.call_args
        assert kwargs.get("capture_output") is True
        # check=False or absent (default False) — both acceptable, but if present must be False
        assert kwargs.get("check", False) is False

    def test_pages_field_uses_pdfminer_pdfpage_not_sidecar(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        pdf = tmp_path / "scan.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        mocker.patch("bim.commands.doc.shared.ocr.extract_text", return_value="")
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(3),
        )
        # Sidecar contains text consistent with only one page; pages must still be 3.
        mocker.patch(
            "bim.commands.doc.shared.ocr.subprocess.run",
            side_effect=_sidecar_writing_run("just one page worth of text"),
        )

        settings = _make_settings(tmp_path)
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        result = runner.run(pdf)

        assert result.pages == 3

    def test_skip_text_false_disables_skip_branch(self, tmp_path: Path, state_dir: Path, mocker: MockerFixture) -> None:
        pdf = tmp_path / "input.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        # Text layer present.
        mocker.patch(
            "bim.commands.doc.shared.ocr.extract_text",
            return_value="some existing text",
        )
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(1),
        )
        # High confidence so redo branch does not trigger either.
        mocker.patch(
            "bim.commands.doc.shared.ocr._estimate_text_confidence",
            return_value=0.99,
            create=True,
        )
        run_mock = mocker.patch(
            "bim.commands.doc.shared.ocr.subprocess.run",
            side_effect=_sidecar_writing_run("ocr output"),
        )

        settings = _make_settings(
            tmp_path,
            skip_text=False,
            redo_on_low_confidence=False,
        )
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        result = runner.run(pdf)

        run_mock.assert_called_once()
        argv = _argv_from_call(run_mock.call_args)
        assert "--redo-ocr" not in argv  # full OCR, not redo
        assert result.was_redone is False
        assert result.original_backup_path is None

    def test_redo_ocr_disabled_takes_full_ocr_path_when_skip_text_false(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        pdf = tmp_path / "input.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        mocker.patch(
            "bim.commands.doc.shared.ocr.extract_text",
            return_value="garbled text",
        )
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(1),
        )
        mocker.patch(
            "bim.commands.doc.shared.ocr._estimate_text_confidence",
            return_value=0.10,
            create=True,
        )
        run_mock = mocker.patch(
            "bim.commands.doc.shared.ocr.subprocess.run",
            side_effect=_sidecar_writing_run("ocr output"),
        )

        settings = _make_settings(
            tmp_path,
            skip_text=False,
            redo_on_low_confidence=False,  # explicitly off → no redo even at 0.10
        )
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        result = runner.run(pdf)

        argv = _argv_from_call(run_mock.call_args)
        assert "--redo-ocr" not in argv
        assert result.was_redone is False
        assert result.original_backup_path is None

    def test_redo_branch_fires_for_low_density_text_unmocked(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        """End-to-end: the production density heuristic fires the redo branch."""
        pdf = tmp_path / "input.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        # 30 chars over 1 page → density 30 → confidence 0.15 (well below 0.70).
        mocker.patch(
            "bim.commands.doc.shared.ocr.extract_text",
            return_value="x" * 30,
        )
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(1),
        )
        run_mock = mocker.patch(
            "bim.commands.doc.shared.ocr.subprocess.run",
            side_effect=_sidecar_writing_run("redone"),
        )

        settings = _make_settings(
            tmp_path,
            skip_text=False,
            redo_on_low_confidence=True,
            low_confidence_threshold=0.70,
        )
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        result = runner.run(pdf)

        argv = _argv_from_call(run_mock.call_args)
        assert "--redo-ocr" in argv
        assert result.was_redone is True

    def test_full_ocr_cleans_up_sidecar_on_success(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        pdf = tmp_path / "scan.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        mocker.patch("bim.commands.doc.shared.ocr.extract_text", return_value="")
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(1),
        )
        sidecar_paths: list[Path] = []

        def _capture(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            argv = args[0] if args else kwargs.get("args")
            assert argv is not None
            for token in argv:
                token_s = str(token)
                if token_s.startswith("--sidecar="):
                    p = Path(token_s.split("=", 1)[1])
                    p.write_text("done", encoding="utf-8")
                    sidecar_paths.append(p)
                    break
            return _ok_proc()

        mocker.patch("bim.commands.doc.shared.ocr.subprocess.run", side_effect=_capture)

        settings = _make_settings(tmp_path)
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        runner.run(pdf)

        assert len(sidecar_paths) == 1
        assert not sidecar_paths[0].exists()

    def test_full_ocr_cleans_up_sidecar_on_failure(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        pdf = tmp_path / "scan.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        mocker.patch("bim.commands.doc.shared.ocr.extract_text", return_value="")
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(1),
        )
        sidecar_paths: list[Path] = []

        def _capture_fail(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            argv = args[0] if args else kwargs.get("args")
            assert argv is not None
            for token in argv:
                token_s = str(token)
                if token_s.startswith("--sidecar="):
                    p = Path(token_s.split("=", 1)[1])
                    p.write_text("partial", encoding="utf-8")
                    sidecar_paths.append(p)
                    break
            return subprocess.CompletedProcess(args=[], returncode=2, stdout=b"", stderr=b"boom")

        mocker.patch("bim.commands.doc.shared.ocr.subprocess.run", side_effect=_capture_fail)

        settings = _make_settings(tmp_path)
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        with pytest.raises(OCRError):
            runner.run(pdf)

        assert len(sidecar_paths) == 1
        assert not sidecar_paths[0].exists()

    def test_full_ocr_cleans_up_output_pdf_on_failure(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        pdf = tmp_path / "scan.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        mocker.patch("bim.commands.doc.shared.ocr.extract_text", return_value="")
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(1),
        )
        # Capture the output_pdf path from argv and assert it does not exist
        # after the failed run.
        captured: dict[str, Path] = {}

        def _capture_fail(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            argv = args[0] if args else kwargs.get("args")
            assert argv is not None
            tokens = [str(t) for t in argv]
            # Last positional arg is the output PDF path.
            captured["output_pdf"] = Path(tokens[-1])
            return subprocess.CompletedProcess(args=[], returncode=3, stdout=b"", stderr=b"boom")

        mocker.patch("bim.commands.doc.shared.ocr.subprocess.run", side_effect=_capture_fail)

        settings = _make_settings(tmp_path)
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        with pytest.raises(OCRError):
            runner.run(pdf)

        assert "output_pdf" in captured
        assert not captured["output_pdf"].exists(), "output_pdf tempfile must be cleaned up on _invoke failure"

    def test_subprocess_stderr_decoded_with_replace_for_invalid_utf8(
        self, tmp_path: Path, state_dir: Path, mocker: MockerFixture
    ) -> None:
        pdf = tmp_path / "bad.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")

        mocker.patch("bim.commands.doc.shared.ocr.extract_text", return_value="")
        mocker.patch(
            "bim.commands.doc.shared.ocr.PDFPage.get_pages",
            return_value=_pages_iter(1),
        )
        # \xff is invalid UTF-8 start byte; errors='replace' must yield U+FFFD.
        mocker.patch(
            "bim.commands.doc.shared.ocr.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"err: \xff broken"),
        )

        settings = _make_settings(tmp_path)
        runner = OCRRunner(settings=settings, state_dir=state_dir)
        with pytest.raises(OCRError) as excinfo:
            runner.run(pdf)
        assert "err:" in excinfo.value.stderr
        assert "broken" in excinfo.value.stderr
        # decoded — does not raise UnicodeDecodeError on attribute access
        assert isinstance(excinfo.value.stderr, str)
