"""Archive an article's original text outside the vault, dated like the vault's ``articles`` tree."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


def archive_file_name(title: str) -> str:
    """The original title, not slugified; only characters a path cannot hold are replaced."""
    name = re.sub(r"[/\\:\x00-\x1f]", "-", title).strip().rstrip(".")
    if not name:
        raise ValueError(f"title '{title}' cannot be used as a file name")
    return name


def archive_path(path_articles: Path, title: str, now: datetime) -> Path:
    """``<path_articles>/<YYYY>/<YYYYMM>00/<title>.md``: the month folder of the vault's archive."""
    return path_articles.expanduser() / f"{now:%Y}" / f"{now:%Y%m}00" / f"{archive_file_name(title)}.md"


def archive_text(title: str, original: str, web: str) -> str:
    return f"# {title}\n\n{original}\n" + (f"\n---\n\nSource: {web}\n" if web else "")


def archive_original(path_articles: Path, title: str, original: str, web: str, now: datetime) -> Path:
    """Write the original text to the archive with an exclusive open; return the path.

    Raises:
        ValueError: When the parent of ``path_articles`` does not exist or the title
            cannot name a file.
        FileExistsError: When the target already exists; nothing is overwritten.
    """
    root = path_articles.expanduser()
    if not root.parent.is_dir():
        raise ValueError(f"{root.parent} does not exist; set path_articles")
    target = archive_path(root, title, now)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(archive_text(title, original, web).encode("utf-8"))
    return target


__all__ = ["archive_file_name", "archive_original", "archive_path", "archive_text"]
