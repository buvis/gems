from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field, replace

__all__ = ["BkpignoreRules", "ExcludeState", "parse_bkpignore"]

BKPIGNORE_FILENAME = ".bkpignore"


@dataclass(frozen=True)
class BkpignoreRules:
    """The add / un-ignore patterns parsed from one ``.bkpignore`` file.

    ``adds`` are bare lines (extra excludes for this subtree); ``unignores`` are
    ``!pattern`` lines (cancel an inherited global default for this subtree).
    Both are gitignore-style basename globs, matched against a single path
    component (never a slash-bearing path) in v1.
    """

    adds: tuple[str, ...] = ()
    unignores: tuple[str, ...] = ()


def parse_bkpignore(text: str) -> BkpignoreRules:
    """Parse ``.bkpignore`` file content into :class:`BkpignoreRules`.

    Gitignore-style: blank lines and ``#`` comments are ignored, surrounding
    whitespace is stripped, a leading ``!`` marks an un-ignore, and a leading
    ``\\!`` escapes a literal ``!``. Later duplicate lines are de-duplicated
    while preserving first-seen order.

    Args:
        text: Raw ``.bkpignore`` file content.

    Returns:
        The parsed add and un-ignore patterns.
    """
    adds: list[str] = []
    unignores: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            pattern = line[1:].strip()
            if pattern and pattern not in unignores:
                unignores.append(pattern)
            continue
        if line.startswith("\\!"):
            line = line[1:]
        if line not in adds:
            adds.append(line)
    return BkpignoreRules(adds=tuple(adds), unignores=tuple(unignores))


@dataclass(frozen=True)
class ExcludeState:
    """The exclude decision context in force at one point of the walk.

    ``excludes`` is the active set of basename patterns that exclude a matching
    path; ``unignores`` is the set of patterns that re-include an otherwise
    excluded path. Both are accumulated top-down: a ``.bkpignore`` found in a
    directory layers its rules onto the state inherited from ancestors, and that
    layered state applies to that directory's subtree ONLY — which is what makes
    ``!target`` path-scoped. ``applied`` records every rule that has been layered
    on during the walk, for dry-run reporting.
    """

    excludes: frozenset[str] = frozenset()
    unignores: frozenset[str] = frozenset()
    applied: tuple[str, ...] = field(default=())

    def layer(self: ExcludeState, rules: BkpignoreRules) -> ExcludeState:
        """Return a new state with ``rules`` layered on top of this one.

        Adds extend the active excludes; un-ignores extend the active
        un-ignores. The result applies to the current directory's subtree only —
        the caller passes the parent's state down and never mutates it.
        """
        if not rules.adds and not rules.unignores:
            return self
        applied = list(self.applied)
        for pattern in rules.adds:
            applied.append(f"+{pattern}")
        for pattern in rules.unignores:
            applied.append(f"!{pattern}")
        return replace(
            self,
            excludes=self.excludes | frozenset(rules.adds),
            unignores=self.unignores | frozenset(rules.unignores),
            applied=tuple(applied),
        )

    def is_excluded(self: ExcludeState, name: str, relpath: str | None = None) -> bool:
        """Decide whether a path is excluded here.

        A path is excluded when it matches an active exclude pattern AND no
        active un-ignore pattern cancels it. Un-ignore wins over exclude, so a
        subtree whose ``.bkpignore`` says ``!target`` keeps its ``target/`` even
        though ``target`` is a global default.

        ``name`` is the path's own component (basename); ``relpath`` is its path
        relative to the source root, in POSIX form. A pattern is matched against
        ``relpath`` when it contains a ``/`` (so a global ``.yarn/cache`` scopes
        to that sub-path, matching the wrapped script's ``tar --exclude``), and
        against ``name`` otherwise. ``.bkpignore`` patterns are basename-only in
        v1, so un-ignore is evaluated against ``name``.
        """
        if any(fnmatch.fnmatch(name, pattern) for pattern in self.unignores):
            return False
        for pattern in self.excludes:
            target = relpath if ("/" in pattern and relpath is not None) else name
            if target is not None and fnmatch.fnmatch(target, pattern):
                return True
        return False
