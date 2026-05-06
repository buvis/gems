"""Cross-command helpers for the doc subsystem.

Pure functions shared by ``Pipeline`` (ingest path) and ``CommandPromote``
(human-approved triage path) so the two stay byte-for-byte consistent on
zettel-frontmatter shape.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

__all__ = ["build_zettel_tags", "to_tilde_path"]


def to_tilde_path(path: Path) -> str:
    """Return ``path`` as a ``~/``-prefixed string for portability.

    For paths under ``Path.home()`` this returns ``~/<relative>`` so the
    zettel frontmatter stays portable across machines (any user can
    ``expanduser`` the resulting string and reach the right vault location).

    For paths outside home (notably test ``tmp_path`` on macOS), prepends
    ``~`` directly to the absolute path. The resulting string keeps the
    ``~/`` prefix that ``DocumentZettelFrontmatter.file_path``'s validator
    requires; callers using the path for actual filesystem access should
    use the absolute :class:`Path` instead.
    """
    home = Path.home()
    try:
        rel = path.relative_to(home)
        return f"~/{rel}"
    except ValueError:
        return f"~{path}"


def build_zettel_tags(doc_type: str, issuer_slug: str, doc_date: date | None) -> list[str]:
    """Compose the canonical Obsidian tag list for a document zettel."""
    tags = [f"document/{doc_type}"]
    if issuer_slug:
        tags.append(f"issuer/{issuer_slug}")
    if doc_date is not None:
        tags.append(f"year/{doc_date.year}")
    return tags
