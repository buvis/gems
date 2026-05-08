"""Cross-command helpers for the doc subsystem.

Pure functions shared by ``Pipeline`` (ingest path) and ``CommandPromote``
(human-approved triage path) so the two stay byte-for-byte consistent on
zettel-frontmatter shape.
"""

from __future__ import annotations

import re
from datetime import date

__all__ = ["build_zettel_tags", "compose_zettel_title"]


_WHITESPACE_RUN = re.compile(r"\s+")


def _normalize_whitespace(value: str) -> str:
    """Collapse any whitespace run (spaces, tabs, newlines) to a single space and strip ends."""
    return _WHITESPACE_RUN.sub(" ", value).strip()


def compose_zettel_title(
    issuer: str,
    doc_type: str,
    doc_number: str | None,
    doc_title: str | None,
) -> str:
    """Compose the v1 zettel ``title`` string from frontmatter components.

    Format: ``"{issuer} {doc_type} {doc_number}"`` when ``doc_number`` is
    truthy, otherwise ``"{issuer} {doc_type} {doc_title}"`` when ``doc_title``
    is truthy. ``doc_type`` casing is preserved (the spec example uses
    lowercase ``invoice``). All inputs have embedded whitespace runs
    collapsed to single spaces and leading/trailing whitespace stripped.

    Raises:
        ValueError: when both ``doc_number`` and ``doc_title`` are empty
            or ``None`` (no third token would be available).
    """
    issuer_clean = _normalize_whitespace(issuer)
    doc_type_clean = _normalize_whitespace(doc_type)
    number_clean = _normalize_whitespace(doc_number) if doc_number else ""
    title_clean = _normalize_whitespace(doc_title) if doc_title else ""

    if number_clean:
        return f"{issuer_clean} {doc_type_clean} {number_clean}"
    if title_clean:
        return f"{issuer_clean} {doc_type_clean} {title_clean}"
    raise ValueError("title needs doc_number or doc_title")


def build_zettel_tags(doc_type: str, issuer_slug: str, doc_date: date | None) -> list[str]:
    """Compose the canonical Obsidian tag list for a document zettel."""
    tags = [f"document/{doc_type}"]
    if issuer_slug:
        tags.append(f"issuer/{issuer_slug}")
    if doc_date is not None:
        tags.append(f"year/{doc_date.year}")
    return tags
