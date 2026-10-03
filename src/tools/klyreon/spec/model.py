"""Typed documents for the three file species.

The model is intentionally thin: it carries the parsed frontmatter as an
ordered mapping, plus the body text and the extracted H1. The parser and
writer own the YAML and Markdown mechanics; validation lives in
``validator.py``. Keeping the model free of console/Click/git honours the
"spec engine is pure" rule in the PRD.

Round-trip fidelity rule (spec 14): known keys are written in spec order,
unknown keys are written AFTER them in their original relative order. The
model preserves the full original mapping (``frontmatter``) so the writer can
re-split it; ``FileKind`` records which species a path was parsed as.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

#: Known frontmatter keys in spec order (sections 5.1-5.5). The writer emits
#: present keys in this order; any key not listed here is "unknown" and is
#: written after these, preserving its original relative order.
KNOWN_KEY_ORDER: tuple[str, ...] = (
    # 5.1 required (both species)
    "id",
    "title",
    "created",
    "type",
    # auxiliary files use `kind` in place of `type`
    "kind",
    # 5.2 common optional
    "updated",
    "tags",
    "publish",
    "processed",
    "reviewed",
    # 5.3 concept-zettel dimensions
    "concept-type",
    "assent",
    "lifecycle",
    "claims",
    "doubts",
    # 5.4 cross-reference
    "sources",
    "links",
    "mocs",
    "delivered-as",
    # 5.5 type-specific (common ones kept in a stable place after the graph fields)
    "language",
    "article-author",
    "article-publication",
    "article-url",
    "book-author",
    "book-isbn",
    "book-chapter",
    "quote-author",
    "quote-source",
    "transcript-event",
    "transcript-participants",
    "transcript-recorded",
)

_KNOWN_KEYS = frozenset(KNOWN_KEY_ORDER)


class FileKind(str, Enum):
    """Which species a file was parsed as, decided by its directory."""

    SOURCE = "source"
    ZETTEL = "zettel"
    AUX = "aux"


@dataclass(slots=True)
class Document:
    """A parsed Markdown file with YAML frontmatter.

    Attributes:
        path: The vault-relative or absolute path the document was read from.
        kind: The species (decided by directory at parse time).
        frontmatter: The frontmatter as an insertion-ordered mapping. ``id``
            is always a string (the sexagesimal/int traps are handled in the
            parser). This is the authoritative store; known/unknown split is
            derived from :data:`KNOWN_KEY_ORDER`.
        body: The Markdown body AFTER the closing frontmatter fence, verbatim.
        h1: The first H1 heading text, or ``None`` when the body has no H1.
    """

    path: str
    kind: FileKind
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    h1: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        """Return a frontmatter value, or ``default`` when absent."""
        return self.frontmatter.get(key, default)

    def known_keys(self) -> list[str]:
        """Present known keys, in spec order."""
        return [k for k in KNOWN_KEY_ORDER if k in self.frontmatter]

    def unknown_keys(self) -> list[str]:
        """Present unknown keys, in their original insertion order."""
        return [k for k in self.frontmatter if k not in _KNOWN_KEYS]


# Thin species aliases. They share the Document shape today; distinct names
# keep call sites readable and leave room for species-specific helpers later
# without changing the parser contract.
SourceDocument = Document
Zettel = Document
AuxFile = Document
