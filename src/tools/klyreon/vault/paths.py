"""Root-relative path resolution and confinement (spec 10.4).

``resolve_path`` turns a root-relative path from a file (``sources``,
``links.to``, ``mocs``, ``doubts[].target.to``) into an absolute path, and
rejects anything that could escape the vault root:

- any path containing a ``..`` segment is an error (spec 10.4);
- any absolute path, or a path that resolves outside the root, is an error.

It does NOT require the target to exist -- existence is a separate validation
rule. The caller decides whether the resolved path must be present.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

__all__ = ["PathConfinementError", "is_confined", "resolve_path"]


class PathConfinementError(ValueError):
    """Raised when a root-relative path escapes the vault root."""


def resolve_path(root: Path, rel: str) -> Path:
    """Resolve ``rel`` under ``root`` or raise :class:`PathConfinementError`.

    Args:
        root: The absolute, resolved vault root.
        rel: A root-relative path as written in a file.

    Returns:
        The absolute path ``root / rel``, normalised.

    Raises:
        PathConfinementError: if ``rel`` is absolute, contains a ``..``
            segment, or resolves outside ``root``.
    """
    pure = PurePosixPath(rel)
    if pure.is_absolute():
        msg = f"path must be root-relative, not absolute: {rel!r}"
        raise PathConfinementError(msg)
    if ".." in pure.parts:
        msg = f"path must not contain a '..' segment: {rel!r}"
        raise PathConfinementError(msg)

    root_resolved = root.resolve()
    candidate = (root_resolved / rel).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        msg = f"path escapes the vault root: {rel!r}"
        raise PathConfinementError(msg)
    return candidate


def is_confined(root: Path, rel: str) -> bool:
    """Return ``True`` when :func:`resolve_path` would accept ``rel``."""
    try:
        resolve_path(root, rel)
    except PathConfinementError:
        return False
    return True
