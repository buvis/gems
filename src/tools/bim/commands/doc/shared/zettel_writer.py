"""Document zettel frontmatter model, body builder, and writer.

The writer composes a Markdown zettel with YAML frontmatter and writes it
atomically to ``<vault_root>/<vault_documents_subdir>/<basename>.md``.

The basename is derived from the canonical PDF filename in
``frontmatter.file_path`` by replacing the ``.pdf`` suffix with ``.md``.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from bim.commands.doc.shared.atomic_write import atomic_write_text
from bim.commands.doc.shared.naming import DOC_TYPES, SLUG_REGEX

if TYPE_CHECKING:
    from bim.commands.doc.shared.settings_models import ZettelSettings

__all__ = [
    "DocumentZettelFrontmatter",
    "ZettelWriter",
    "build_zettel_body",
]


_ID_REGEX = re.compile(r"^\d{14}$")
_SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")
_EXTRACTION_METHOD_REGEX = re.compile(r"^(manual|filename|llm:[^:]+|rule:[^:]+:v\d+|rule\+llm:[^:]+:v\d+)$")

IngestSource = Literal[
    "email",
    "scan",
    "download",
    "issuer-inbox",
    "backfill-canonical",
    "backfill-noncanonical",
]


class _DoubleQuotedStr(str):
    """Marker subclass so YAML emits the value with double quotes."""


def _double_quoted_representer(dumper: yaml.SafeDumper, data: _DoubleQuotedStr) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style='"')


yaml.SafeDumper.add_representer(_DoubleQuotedStr, _double_quoted_representer)


class DocumentZettelFrontmatter(BaseModel):
    """Validated frontmatter for a document zettel.

    Field order here matches the YAML output order (Python dicts preserve
    insertion order; we serialize with ``sort_keys=False``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    type: Literal["document"] = "document"
    doc_type: str
    issuer_slug: str
    issuer_display: str
    doc_number: str | None
    doc_date: date
    doc_amount: float | None
    doc_currency: str | None
    doc_language: str | None
    ingest_date: date
    ingest_source: IngestSource
    file_path: str
    file_sha256: str
    ocr_engine: str | None
    ocr_mean_confidence: float | None
    extraction_method: str
    tags: list[str]

    @field_validator("id")
    @classmethod
    def _id_is_14_digits(cls, v: str) -> str:
        if not _ID_REGEX.match(v):
            raise ValueError(f"id must be 14 digits, got {v!r}")
        return v

    @field_validator("doc_type")
    @classmethod
    def _doc_type_is_known(cls, v: str) -> str:
        if v not in DOC_TYPES:
            raise ValueError(f"doc_type must be one of {DOC_TYPES}, got {v!r}")
        return v

    @field_validator("issuer_slug")
    @classmethod
    def _issuer_slug_is_canonical(cls, v: str) -> str:
        if not SLUG_REGEX.match(v):
            raise ValueError(
                f"issuer_slug must be lowercase kebab-case ASCII (matching {SLUG_REGEX.pattern}), got {v!r}"
            )
        return v

    @field_validator("file_path")
    @classmethod
    def _file_path_uses_tilde(cls, v: str) -> str:
        if not v.startswith("~/"):
            raise ValueError(f"file_path must start with '~/', got {v!r}")
        return v

    @field_validator("file_sha256")
    @classmethod
    def _file_sha256_is_hex64(cls, v: str) -> str:
        if not _SHA256_REGEX.match(v):
            raise ValueError(f"file_sha256 must be 64 lowercase hex chars, got {v!r}")
        return v

    @field_validator("extraction_method")
    @classmethod
    def _extraction_method_is_known(cls, v: str) -> str:
        if not _EXTRACTION_METHOD_REGEX.match(v):
            raise ValueError(f"extraction_method must match {_EXTRACTION_METHOD_REGEX.pattern}, got {v!r}")
        return v


def _doc_type_title(doc_type: str) -> str:
    """Title-case a doc_type without lowercasing the rest (matches project convention)."""
    if not doc_type:
        return doc_type
    return doc_type[0].upper() + doc_type[1:]


def build_zettel_body(
    frontmatter: DocumentZettelFrontmatter,
    ocr_text: str,
    settings: ZettelSettings | None = None,
) -> str:
    """Compose the Markdown body (everything after the YAML frontmatter).

    The body contains a header, a link to the canonical PDF, key metadata
    lines, and an Obsidian-style collapsible callout containing the OCR text
    with each line prefixed by ``> ``. When ``settings.ocr_text_max_chars`` is
    positive and the OCR text exceeds it, the text is truncated and a Unicode
    ellipsis is appended before the callout is composed.
    """
    title = _doc_type_title(frontmatter.doc_type)
    if frontmatter.doc_number is None:
        header = f"# {title} — {frontmatter.issuer_display}"
    else:
        header = f"# {title} {frontmatter.doc_number} — {frontmatter.issuer_display}"

    lines: list[str] = [
        header,
        "",
        f"[Open PDF]({frontmatter.file_path})",
        "",
        f"**Date:** {frontmatter.doc_date.isoformat()}",
    ]

    if frontmatter.doc_amount is not None:
        currency = frontmatter.doc_currency or ""
        lines.append(f"**Amount:** {frontmatter.doc_amount} {currency}".rstrip())

    lines.extend(
        [
            "",
            "## OCR text",
            "",
            "> [!quote]- Full text",
        ]
    )

    text = ocr_text
    if settings is not None and settings.ocr_text_max_chars > 0 and len(text) > settings.ocr_text_max_chars:
        text = text[: settings.ocr_text_max_chars] + "…"

    for ocr_line in text.split("\n"):
        lines.append(f"> {ocr_line}")

    return "\n".join(lines) + "\n"


class ZettelWriter:
    """Atomic writer for document zettel Markdown files.

    The ``repo`` parameter is reserved for future integration with the zettel
    repository abstraction; v1 writes directly via ``atomic_write_text``.
    """

    def __init__(self, repo: object, vault_root: Path, vault_documents_subdir: str) -> None:
        self.repo = repo
        self.vault_root = vault_root
        self.vault_documents_subdir = vault_documents_subdir

    def write(self, frontmatter: DocumentZettelFrontmatter, body: str) -> Path:
        """Serialize frontmatter to YAML, prepend it to ``body``, write atomically.

        Returns the absolute path of the written ``.md`` file.
        """
        basename = self._derive_basename(frontmatter.file_path)
        target_path = self.vault_root / self.vault_documents_subdir / basename
        target_path.parent.mkdir(parents=True, exist_ok=True)

        yaml_text = self._serialize_frontmatter(frontmatter)
        content = f"---\n{yaml_text}---\n\n{body}"
        atomic_write_text(target_path, content)
        return target_path

    @staticmethod
    def _derive_basename(file_path: str) -> str:
        leaf = Path(file_path).name
        if leaf.lower().endswith(".pdf"):
            leaf = leaf[: -len(".pdf")]
        return f"{leaf}.md"

    @staticmethod
    def _serialize_frontmatter(fm: DocumentZettelFrontmatter) -> str:
        payload: dict[str, object] = {
            "id": _DoubleQuotedStr(fm.id),
            "type": fm.type,
            "doc_type": fm.doc_type,
            "issuer_slug": fm.issuer_slug,
            "issuer_display": fm.issuer_display,
            "doc_number": _DoubleQuotedStr(fm.doc_number) if fm.doc_number is not None else None,
            "doc_date": fm.doc_date,
            "doc_amount": fm.doc_amount,
            "doc_currency": fm.doc_currency,
            "doc_language": fm.doc_language,
            "ingest_date": fm.ingest_date,
            "ingest_source": fm.ingest_source,
            "file_path": fm.file_path,
            "file_sha256": fm.file_sha256,
            "ocr_engine": fm.ocr_engine,
            "ocr_mean_confidence": fm.ocr_mean_confidence,
            "extraction_method": fm.extraction_method,
            "tags": list(fm.tags),
        }
        return yaml.safe_dump(
            payload,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            default_style=None,
        )
