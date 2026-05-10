"""Filesystem walker for the ``bim doc audit`` subsystem.

Yields ``(folder_slug, pdf_path)`` for every PDF under
``<business_root>/<folder_slug>/``, with deterministic ordering.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path


def _walk_issuer(folder_slug: str, directory: Path) -> Iterator[tuple[str, Path]]:
    """Recursively yield PDFs under an issuer folder, skipping hidden dirs."""
    for child in sorted(directory.iterdir(), key=lambda p: p.name):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            yield from _walk_issuer(folder_slug, child)
        elif child.is_file() and child.suffix.lower() == ".pdf":
            yield (folder_slug, child)


def walk_business_root(business_root: Path) -> Iterator[tuple[str, Path]]:
    """Yield ``(folder_slug, pdf_path)`` for every PDF under ``business_root``.

    Deterministic order (sorted issuer dirs, sorted files within).
    Recurses into nested subdirs of an issuer folder, but skips:

    - ``<business_root>/_triage/`` (handled separately by ``AuditReport.triage_pending``)
    - ``<business_root>/<folder_slug>/inbox/`` (handled separately by ``AuditReport.issuer_inboxes``)
    - any directory whose name starts with ``.`` (covers ``.git``, ``.DS_Store``)

    Top-level files (directly under ``business_root``, not in an issuer folder)
    are yielded with ``folder_slug=""`` so the per-PDF check pipeline can flag
    them as unknown_issuer.

    A non-existent ``business_root`` yields nothing (treated as empty).
    """
    if not business_root.is_dir():
        return
    for child in sorted(business_root.iterdir(), key=lambda p: p.name):
        if child.name.startswith("."):
            continue
        if child.is_file():
            if child.suffix.lower() == ".pdf":
                yield ("", child)
            continue
        if child.name == "_triage":
            continue
        folder_slug = child.name
        for sub in sorted(child.iterdir(), key=lambda p: p.name):
            if sub.name == "inbox" and sub.is_dir():
                continue
            if sub.name.startswith("."):
                continue
            if sub.is_dir():
                yield from _walk_issuer(folder_slug, sub)
            elif sub.is_file() and sub.suffix.lower() == ".pdf":
                yield (folder_slug, sub)
