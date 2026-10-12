"""Manifest parsing for host links.

The manifest lives at ``.config/buvis/host-links`` in the dotfiles root and
maps installed target paths to host-specific source paths, one
``target => source`` pair per line.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

MANIFEST_PATH = ".config/buvis/host-links"

_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_PATH_SEPARATORS = re.compile(r"[\\/]")


@dataclasses.dataclass(frozen=True)
class HostLink:
    """A single host link from an installed target to its host source."""

    target: str
    source: str


def _is_absolute(path: str) -> bool:
    return path.startswith(("/", "~", "\\")) or _DRIVE_PREFIX.match(path) is not None


def _has_dotdot(path: str) -> bool:
    return ".." in _PATH_SEPARATORS.split(path)


def _validate_path(path: str) -> str | None:
    """Return the first problem with a manifest path, or None if valid."""
    if not path:
        return "empty path"
    if _is_absolute(path):
        return "absolute path"
    if _has_dotdot(path):
        return "'..' not allowed"
    return None


def parse_manifest(text: str) -> tuple[list[HostLink], list[str]]:
    """Parse manifest text into host links.

    Returns the valid links in file order plus one error string per bad
    line, formatted ``host-links:<line>: <reason>``. Invalid lines do not
    reserve their target for duplicate detection.
    """
    links: list[HostLink] = []
    errors: list[str] = []
    seen_targets: set[str] = set()
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=>" not in stripped:
            errors.append(f"host-links:{number}: missing '=>'")
            continue
        target, source = (part.strip() for part in stripped.split("=>", 1))
        problem = _validate_path(target) or _validate_path(source)
        if problem is not None:
            errors.append(f"host-links:{number}: {problem}")
            continue
        if target == source:
            errors.append(f"host-links:{number}: target equals source")
            continue
        if target in seen_targets:
            errors.append(f"host-links:{number}: duplicate target {target}")
            continue
        seen_targets.add(target)
        links.append(HostLink(target=target, source=source))
    return links, errors


def read_manifest(root: Path) -> tuple[list[HostLink], list[str]]:
    """Read and parse the manifest at ``root / MANIFEST_PATH``.

    A missing manifest yields no links and no errors; an unreadable or
    undecodable one yields a single ``host-links: ...`` error.
    """
    path = root / MANIFEST_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [], []
    except (OSError, UnicodeDecodeError) as exc:
        return [], [f"host-links: {exc}"]
    return parse_manifest(text)
