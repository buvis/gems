"""Document zettel frontmatter model, body builder, and writer (v1 shape).

The writer composes a Markdown zettel with YAML frontmatter and writes it
atomically to ``<vault_root>/<vault_documents_subdir>/<issuer-slug>/<basename>.md``
(per-issuer subfolder, mirroring the business-folder layout).

The basename is derived from the canonical PDF filename in
``frontmatter.file_path`` by replacing the ``.pdf`` suffix with ``.md``.

v1 frontmatter uses kebab-case keys (``doc-type``, ``ingested-at``,
``file-path``, ...) emitted via Pydantic field aliases. ``id`` is a bare int.
``ingested-at`` is a tz-aware datetime serialised as ISO 8601 with offset.
``file-path`` is an absolute filesystem path with no ``~`` segment.
"""

from __future__ import annotations

import re
import urllib.parse
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from bim.commands.doc.shared.atomic_write import atomic_write_text
from bim.commands.doc.shared.naming import DOC_TYPES, SLUG_REGEX
from bim.commands.doc.shared.validators import validate_sha256_hex64

if TYPE_CHECKING:
    from bim.commands.doc.shared.settings_models import ZettelSettings

__all__ = [
    "DocumentZettelFrontmatter",
    "ZettelWriter",
    "build_zettel_body",
]


_ID_MIN = 10**13
_ID_MAX = 10**14 - 1
# llm:<model-name> permits colons in the tail because Ollama's canonical
# model identifier uses ``name:tag`` form (e.g. qwen2.5:7b-instruct). rule and
# rule+llm forms keep the strict three-segment grammar so audit queries like
# "rules:cez-as:v3" remain unambiguous.
_EXTRACTION_METHOD_REGEX = re.compile(r"^(manual|filename|llm:.+|rule:[^:]+:v\d+|rule\+llm:[^:]+:v\d+)$")

IngestSource = Literal[
    "email",
    "scan",
    "download",
    "issuer-inbox",
    "backfill-canonical",
    "backfill-noncanonical",
]


class DocumentZettelFrontmatter(BaseModel):
    """Validated v1 frontmatter for a document zettel.

    Python attribute names stay snake_case so callers keep working;
    ``model_dump(by_alias=True)`` and YAML serialisation use the kebab-case
    aliases (``doc-type``, ``ingested-at``, ``file-path``, ...). Field order
    here matches the YAML output order (Python dicts preserve insertion
    order; we serialise with ``sort_keys=False``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: int
    title: str
    type: Literal["document"] = "document"
    doc_type: str = Field(alias="doc-type")
    issuer: str
    doc_number: str | None = Field(alias="doc-number")
    doc_date: date = Field(alias="doc-date")
    doc_amount: float | None = Field(alias="doc-amount")
    doc_currency: str | None = Field(alias="doc-currency")
    doc_language: str | None = Field(alias="doc-language")
    ingested_at: datetime = Field(alias="ingested-at")
    ingest_source: IngestSource = Field(alias="ingest-source")
    file_path: str = Field(alias="file-path")
    file_sha256: str = Field(alias="file-sha256")
    ocr_engine: str | None = Field(alias="ocr-engine")
    ocr_mean_confidence: float | None = Field(alias="ocr-mean-confidence")
    extraction_method: str = Field(alias="extraction-method")
    tags: list[str]

    @field_validator("id")
    @classmethod
    def _id_is_14_digits(cls, v: int) -> int:
        if not isinstance(v, int) or isinstance(v, bool) or v < _ID_MIN or v > _ID_MAX:
            raise ValueError(f"id must be a 14-digit integer in [{_ID_MIN}, {_ID_MAX}], got {v!r}")
        return v

    @field_validator("title")
    @classmethod
    def _title_non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("title must be non-empty")
        if v.strip() != v:
            raise ValueError(f"title must not have leading/trailing whitespace, got {v!r}")
        return v

    @field_validator("doc_type")
    @classmethod
    def _doc_type_is_known(cls, v: str) -> str:
        if v not in DOC_TYPES:
            raise ValueError(f"doc_type must be one of {DOC_TYPES}, got {v!r}")
        return v

    @field_validator("file_path")
    @classmethod
    def _file_path_is_absolute_no_tilde(cls, v: str) -> str:
        # Reject the legacy ``~/...`` shape: not absolute (so caught by the
        # is_absolute check) AND any path *component* equal to a bare ``~``
        # (defensive: catches malformed absolute paths like ``/foo/~/bar``).
        # Tildes embedded within directory names (e.g. iCloud's
        # ``com~apple~CloudDocs``) are legitimate filesystem segments and
        # not rejected.
        if not Path(v).is_absolute():
            raise ValueError(f"file_path must be absolute, got {v!r}")
        if any(part == "~" for part in Path(v).parts):
            raise ValueError(f"file_path must not contain a bare '~' segment, got {v!r}")
        return v

    @field_validator("file_sha256")
    @classmethod
    def _file_sha256_is_hex64(cls, v: str) -> str:
        return validate_sha256_hex64("file_sha256", v)

    @field_validator("ingested_at")
    @classmethod
    def _ingested_at_is_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError(f"ingested_at must be timezone-aware, got naive {v!r}")
        return v

    @field_validator("extraction_method")
    @classmethod
    def _extraction_method_is_known(cls, v: str) -> str:
        if not _EXTRACTION_METHOD_REGEX.match(v):
            raise ValueError(f"extraction_method must match {_EXTRACTION_METHOD_REGEX.pattern}, got {v!r}")
        return v


def _coerce_doc_number(value: str | None) -> int | str | None:
    """Render doc_number as bare int when the string round-trips, else as string.

    ``"7102105594"`` -> ``7102105594`` (int): ``str(7102105594) == "7102105594"``.
    ``"007"`` -> ``"007"`` (string): ``str(7) == "7"`` ≠ ``"007"``, so leading
    zeroes block the int form. PyYAML auto-quotes leading-zero strings that
    would re-parse as numbers.
    """
    if value is None:
        return None
    try:
        as_int = int(value)
    except (TypeError, ValueError):
        return value
    if str(as_int) == value:
        return as_int
    return value


def build_zettel_body(
    frontmatter: DocumentZettelFrontmatter,
    ocr_text: str,
    summary: str | None = None,
    settings: ZettelSettings | None = None,
) -> str:
    """Compose the Markdown body (everything after the YAML frontmatter).

    v1 layout: ``# {title}``, blank, ``[Open PDF](file://...)``, blank,
    optional summary paragraph + blank, ``## OCR text``, blank, the existing
    Obsidian ``> [!quote]- Full text`` callout with each OCR line prefixed
    by ``> ``. When ``settings.ocr_text_max_chars`` is positive and the OCR
    text exceeds it, the text is truncated with a Unicode ellipsis appended
    before the callout is composed.
    """
    file_url = "file://" + urllib.parse.quote(frontmatter.file_path, safe="/~")

    lines: list[str] = [
        f"# {frontmatter.title}",
        "",
        f"[Open PDF]({file_url})",
        "",
    ]

    if summary:
        lines.append(summary)
        lines.append("")

    lines.extend(
        [
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

    def write(self, frontmatter: DocumentZettelFrontmatter, body: str, issuer_slug: str) -> Path:
        """Serialise frontmatter to YAML, prepend it to ``body``, write atomically.

        The zettel is placed under ``<vault_root>/<vault_documents_subdir>/<issuer_slug>/``
        (per-issuer subfolder, created on demand). Returns the absolute path
        of the written ``.md`` file.
        """
        if not SLUG_REGEX.match(issuer_slug):
            raise ValueError(
                f"issuer_slug must be lowercase kebab-case ASCII (matching {SLUG_REGEX.pattern}), got {issuer_slug!r}"
            )

        basename = self._derive_basename(frontmatter.file_path)
        target_path = self.vault_root / self.vault_documents_subdir / issuer_slug / basename
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
        payload = fm.model_dump(by_alias=True, mode="python")
        # Re-coerce doc-number from the string-or-None we store internally to
        # ``int`` when round-trippable, leaving leading-zero strings as YAML
        # strings (which PyYAML auto-quotes when ambiguous with numbers).
        if "doc-number" in payload:
            payload["doc-number"] = _coerce_doc_number(payload["doc-number"])
        return yaml.safe_dump(
            payload,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            default_style=None,
        )
