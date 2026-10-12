"""Reconcile host-specific links declared in the host-links manifest."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

from dot.hostlinks.manifest import HostLink, read_manifest

_EXTENDED_PREFIX = "\\\\?\\"


def _is_windows() -> bool:
    return os.name == "nt"


def _read_link(path: Path) -> str | None:
    """Read a link target minus any extended-length prefix; None if not a link."""
    try:
        value = os.readlink(path)
    except (OSError, ValueError):
        return None
    return value.removeprefix(_EXTENDED_PREFIX)


def _create_junction(source: str, target: str) -> None:
    """Create a Windows directory junction at target pointing to source."""
    importlib.import_module("_winapi").CreateJunction(source, target)


def _create_link(source: Path, target: Path) -> str | None:
    """Create the link; return a problem text on failure, None on success."""
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if _is_windows() and source.is_dir():
            _create_junction(str(source), str(target))
        elif _is_windows():
            try:
                os.symlink(source, target)
            except OSError:
                return "symlink refused; enable Developer Mode"
        else:
            os.symlink(source, target, target_is_directory=source.is_dir())
    except OSError as exc:
        return str(exc)
    return None


def _check_existing_link(entry: HostLink, target: Path, source: Path, link: str) -> str | None:
    """Judge an existing link; return a problem text, None when it is fine."""
    if os.path.normpath(os.path.join(target.parent, link)) != os.path.normpath(source):
        return f"{entry.target}: links to {link}, expected {entry.source}; skipped"
    if source.exists():
        return None
    return f"{entry.target}: dangling link, no host file at {entry.source}"


def _check_preconditions(entry: HostLink, target: Path, source: Path, apply: bool) -> str | None:
    """Check a missing link can be created; return a problem text, None if so."""
    if target.exists():
        return f"{entry.target}: exists and is not a link; skipped"
    if not source.exists():
        return f"{entry.target}: no host file at {entry.source}"
    if not apply:
        return f"{entry.target}: link missing; run 'dot materialize'"
    return None


def _check_entry(root: Path, entry: HostLink, apply: bool) -> tuple[str | None, str | None]:
    """Evaluate one entry; return (change, problem)."""
    target, source = root / entry.target, root / entry.source
    link = _read_link(target)
    if link is not None:
        return None, _check_existing_link(entry, target, source, link)
    problem = _check_preconditions(entry, target, source, apply)
    if problem is not None:
        return None, problem
    error = _create_link(source, target)
    if error is not None:
        return None, f"{entry.target}: {error}"
    return f"linked {entry.target}", None


def reconcile_links(root: Path, *, apply: bool) -> tuple[list[str], list[str]]:
    """Bring host links under root in line with the manifest.

    Never deletes, overwrites, copies or hardlinks anything. Missing links are
    created only when apply is True. Returns (changes, problems).
    """
    root = Path(os.path.abspath(root))
    entries, errors = read_manifest(root)
    changes: list[str] = []
    problems = list(errors)
    for entry in entries:
        try:
            change, problem = _check_entry(root, entry, apply)
        except (OSError, ValueError) as exc:
            change, problem = None, f"{entry.target}: {exc}"
        if change:
            changes.append(change)
        if problem:
            problems.append(problem)
    return changes, problems
