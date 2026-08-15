from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

__all__ = [
    "ClassifierSettings",
    "DocPaths",
    "DocSettings",
    "LLMSettings",
    "OCRSettings",
    "ZettelSettings",
]


def _default_state_dir() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "state"
    return base / "bim" / "doc"


class DocPaths(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    business_root: Path
    vault_root: Path
    vault_documents_subdir: str = "Zettelkasten/documents"
    state_dir: Path | None = None
    inbox_scans: Path | None = None
    inbox_email: Path | None = None
    inbox_downloads: Path | None = None
    issuers_file: Path | None = None
    originals_dir: Path | None = None
    originals_retention_days: int = 30

    @model_validator(mode="after")
    def _expand_user_paths(self) -> DocPaths:
        """Expand ``~`` on every user-provided path field.

        Pydantic types path fields as :class:`Path` and stores ``~/foo``
        verbatim. Filesystem consumers then either fail loudly
        (``read_bytes`` -> ``FileNotFoundError``) or, worse, silently
        succeed (``mkdir(parents=True)`` creates a literal ``~``
        directory in the cwd). Expand once at settings load so every
        downstream consumer sees an absolute path.

        Declared first so it runs before ``_business_root_under_home``
        (which compares against ``Path.home()``) and
        ``_resolve_state_paths`` (which fills lazy defaults that already
        call ``.expanduser()`` themselves).
        """
        for field in (
            "business_root",
            "vault_root",
            "state_dir",
            "inbox_scans",
            "inbox_email",
            "inbox_downloads",
            "issuers_file",
            "originals_dir",
        ):
            value: Path | None = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, value.expanduser())
        return self

    @model_validator(mode="after")
    def _business_root_under_home(self) -> DocPaths:
        # The business root must live under the user's home directory.
        # The vault/business folders are expected to be iCloud-synced under
        # ``~/Library/Mobile Documents/...``; a path outside ``$HOME`` is
        # almost always a misconfiguration. Guarding here catches it at
        # settings load (loud, early) instead of letting filed PDFs and
        # zettel ``file-path`` values land somewhere unexpected.
        resolved = self.business_root.expanduser().resolve()
        home = Path.home().expanduser().resolve()
        if not resolved.is_relative_to(home):
            raise ValueError(
                f"DocPaths.business_root must be under {home} (the user's home directory); "
                f"got {self.business_root!r} which resolves to {resolved}"
            )
        return self

    @model_validator(mode="after")
    def _resolve_state_paths(self) -> DocPaths:
        state_dir = self.state_dir if self.state_dir is not None else _default_state_dir()
        object.__setattr__(self, "state_dir", state_dir)
        if self.inbox_scans is None:
            object.__setattr__(self, "inbox_scans", state_dir / "inbox" / "scans")
        if self.inbox_email is None:
            object.__setattr__(self, "inbox_email", state_dir / "inbox" / "email")
        if self.originals_dir is None:
            object.__setattr__(self, "originals_dir", state_dir / "originals")
        if self.inbox_downloads is None:
            object.__setattr__(
                self,
                "inbox_downloads",
                Path("~/Downloads/kartoteka-inbox").expanduser(),
            )
        if self.issuers_file is None:
            object.__setattr__(
                self,
                "issuers_file",
                Path("~/.dotfiles/bim/issuers.yml").expanduser(),
            )
        return self


class OCRSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    engine: str = "ocrmypdf"
    languages: list[str] = ["ces", "eng"]
    oversample: int = 400
    deskew: bool = True
    rotate_pages: bool = True
    redo_on_low_confidence: bool = True
    low_confidence_threshold: float = 0.70
    skip_text: bool = True
    # Pass-through escape hatch for any ocrmypdf flag not modelled above
    # (e.g. ``--clean``, ``--remove-background``, ``--tesseract-pagesegmode 6``).
    # Inserted verbatim into the argv before the input/output positional args
    # in both the redo and full-OCR branches; the user owns correctness.
    extra_args: list[str] = []


class ClassifierSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    backend: str = "ollama"
    endpoint: str = "http://localhost:11434"
    primary_model: str = "qwen3:30b-a3b"
    fallback_model: str = "qwen3:14b"
    triage_threshold: float = 0.85
    max_retries: int = 2


# LLMSettings is the same shape as ClassifierSettings — both classifier and
# extractor share the endpoint, primary/fallback models, and retry budget.
# Exposed as an alias so the extractor's signature reads as
# "Extractor(settings: LLMSettings)" without duplicating fields.
LLMSettings = ClassifierSettings


class ZettelSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ocr_text_in_body: bool = True
    ocr_text_collapsible: bool = True
    ocr_text_max_chars: int = 0


class DocSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    paths: DocPaths
    # A claim older than this many minutes counts as abandoned (its worker died
    # without releasing it) and can be taken over by a fresh ingest attempt.
    claim_max_age_minutes: int = 60
    ocr: OCRSettings = OCRSettings()
    classifier: ClassifierSettings = ClassifierSettings()
    zettel: ZettelSettings = ZettelSettings()
