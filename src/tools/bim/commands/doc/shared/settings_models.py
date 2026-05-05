from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

__all__ = [
    "ClassifierSettings",
    "DocPaths",
    "DocSettings",
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


class ClassifierSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    backend: str = "ollama"
    endpoint: str = "http://localhost:11434"
    primary_model: str = "qwen2.5:7b-instruct"
    fallback_model: str = "qwen2.5:14b-instruct"
    triage_threshold: float = 0.85
    max_retries: int = 2


class ZettelSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ocr_text_in_body: bool = True
    ocr_text_collapsible: bool = True
    ocr_text_max_chars: int = 0


class DocSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    paths: DocPaths
    ocr: OCRSettings = OCRSettings()
    classifier: ClassifierSettings = ClassifierSettings()
    zettel: ZettelSettings = ZettelSettings()
