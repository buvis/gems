"""Filesystem walker for the ``bim doc audit`` subsystem.

Yields ``(folder_slug, pdf_path)`` for every PDF under
``<business_root>/<folder_slug>/``, with deterministic ordering.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path


def _is_contained(path: Path, root_resolved: Path) -> bool:
    """Return True iff ``path`` (after symlink resolution) lies under ``root_resolved``.

    ``business_root`` is read-only by spec; following a symlink whose target
    escapes the root would let the audit traverse and report PDFs from
    anywhere on disk. We resolve and check containment before recursing or
    yielding any path.
    """
    try:
        return path.resolve().is_relative_to(root_resolved)
    except OSError:
        # Broken symlink or unresolvable path; treat as out-of-bounds.
        return False


def _walk_issuer(folder_slug: str, directory: Path, root_resolved: Path) -> Iterator[tuple[str, Path]]:
    """Recursively yield PDFs under an issuer folder, skipping hidden dirs.

    Symlinked entries whose target escapes ``root_resolved`` are skipped.
    """
    for child in sorted(directory.iterdir(), key=lambda p: p.name):
        if child.name.startswith("."):
            continue
        if not _is_contained(child, root_resolved):
            continue
        if child.is_dir():
            yield from _walk_issuer(folder_slug, child, root_resolved)
        elif child.is_file() and child.suffix.lower() == ".pdf":
            yield (folder_slug, child)


def _walk_issuer_top_level(folder_slug: str, issuer_dir: Path, root_resolved: Path) -> Iterator[tuple[str, Path]]:
    """Walk the immediate children of an issuer folder.

    Skips ``inbox/``, hidden entries, and symlinks escaping ``root_resolved``.
    Recurses into other subdirs via ``_walk_issuer``.
    """
    for sub in sorted(issuer_dir.iterdir(), key=lambda p: p.name):
        if sub.name == "inbox" and sub.is_dir():
            continue
        if sub.name.startswith("."):
            continue
        if not _is_contained(sub, root_resolved):
            continue
        if sub.is_dir():
            yield from _walk_issuer(folder_slug, sub, root_resolved)
        elif sub.is_file() and sub.suffix.lower() == ".pdf":
            yield (folder_slug, sub)


def walk_business_root(business_root: Path) -> Iterator[tuple[str, Path]]:
    """Yield ``(folder_slug, pdf_path)`` for every PDF under ``business_root``.

    Deterministic order (sorted issuer dirs, sorted files within).
    Recurses into nested subdirs of an issuer folder, but skips:

    - ``<business_root>/_triage/`` (handled separately by ``AuditReport.triage_pending``)
    - ``<business_root>/<folder_slug>/inbox/`` (handled separately by ``AuditReport.issuer_inboxes``)
    - any directory whose name starts with ``.`` (covers ``.git``, ``.DS_Store``)
    - any path whose symlink target escapes ``business_root`` (read-escape guard)

    Top-level files (directly under ``business_root``, not in an issuer folder)
    are yielded with ``folder_slug=""`` so the per-PDF check pipeline can flag
    them as unknown_issuer.

    A non-existent ``business_root`` yields nothing (treated as empty).
    """
    if not business_root.is_dir():
        return
    root_resolved = business_root.resolve()
    for child in sorted(business_root.iterdir(), key=lambda p: p.name):
        if child.name.startswith("."):
            continue
        if not _is_contained(child, root_resolved):
            continue
        if child.is_file():
            if child.suffix.lower() == ".pdf":
                yield ("", child)
            continue
        if child.name == "_triage":
            continue
        yield from _walk_issuer_top_level(child.name, child, root_resolved)
