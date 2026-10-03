"""MOC authoring: a zettel that anchors to a MOC finds one there.

A missing MOC is created with ``id`` (the kebab filename stem), ``title``,
``created``, ``kind: moc``, an H1, and an empty member block delimited by
``<!-- klyreon:members -->`` and ``<!-- /klyreon:members -->``. New members are
appended inside that block as Markdown links; klyreon rewrites ONLY the block,
so anything the human wrote around it survives (the human-edits-win rule).

This module is pure document transformation: it reads an existing MOC (or
synthesises a new one) and returns a :class:`Document` for the caller to stage.
It writes nothing itself.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path, PurePosixPath

from klyreon.spec.enums import AuxKind
from klyreon.spec.model import Document, FileKind
from klyreon.spec.parser import FrontmatterError, parse_file

__all__ = ["MEMBERS_CLOSE", "MEMBERS_OPEN", "ensure_moc"]

MEMBERS_OPEN = "<!-- klyreon:members -->"
MEMBERS_CLOSE = "<!-- /klyreon:members -->"

_BLOCK_RE = re.compile(
    re.escape(MEMBERS_OPEN) + r"(?P<members>.*?)" + re.escape(MEMBERS_CLOSE),
    re.DOTALL,
)


def _slug(moc_rel_path: str) -> str:
    return PurePosixPath(moc_rel_path).stem


def _title_from_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def _new_moc_document(moc_rel_path: str, members: list[str], now: dt.datetime) -> Document:
    slug = _slug(moc_rel_path)
    title = _title_from_slug(slug)
    front: dict[str, object] = {
        "id": slug,
        "title": title,
        "created": now.isoformat(),
        "kind": AuxKind.MOC.value,
    }
    block = _render_block(members)
    body = f"\n# {title}\n\n{block}\n"
    return Document(path=moc_rel_path, kind=FileKind.AUX, frontmatter=front, body=body, h1=title)


def _render_block(member_links: list[str]) -> str:
    inner = "\n".join(member_links)
    middle = f"\n{inner}\n" if inner else "\n"
    return f"{MEMBERS_OPEN}{middle}{MEMBERS_CLOSE}"


def _member_link(member_rel_path: str) -> str:
    stem = PurePosixPath(member_rel_path).stem
    return f"- [{stem}]({member_rel_path})"


def _existing_member_links(block_body: str) -> list[str]:
    return [ln.strip() for ln in block_body.splitlines() if ln.strip()]


def ensure_moc(
    root: Path,
    moc_rel_path: str,
    members: list[str],
    *,
    now: dt.datetime,
) -> Document:
    """Return the MOC document with ``members`` appended inside the marker block.

    Creates the MOC when it does not exist. When it exists, only the member
    block is rewritten; prose above and below it is preserved verbatim. A
    member already listed is not duplicated.

    Args:
        root: Vault root.
        moc_rel_path: Vault-relative MOC path, e.g. ``wiki/mocs/architecture.md``.
        members: Vault-relative paths of member zettels to ensure are listed.
        now: Timestamp for a freshly created MOC's ``created``.
    """
    new_links = [_member_link(m) for m in members]
    abs_path = root / moc_rel_path

    if not abs_path.is_file():
        return _new_moc_document(moc_rel_path, new_links, now)

    try:
        doc = parse_file(abs_path, FileKind.AUX)
    except FrontmatterError:
        # An existing but malformed MOC is replaced with a well-formed one that
        # still carries the members; the caller's validation would reject the
        # malformed one anyway.
        return _new_moc_document(moc_rel_path, new_links, now)

    match = _BLOCK_RE.search(doc.body)
    if match is None:
        # No marker block: append a fresh one at the end, leaving prose intact.
        block = _render_block(new_links)
        doc.body = doc.body.rstrip("\n") + f"\n\n{block}\n"
        return doc

    current = _existing_member_links(match.group("members"))
    merged = list(current)
    for link in new_links:
        if link not in merged:
            merged.append(link)
    doc.body = doc.body[: match.start()] + _render_block(merged) + doc.body[match.end() :]
    return doc
