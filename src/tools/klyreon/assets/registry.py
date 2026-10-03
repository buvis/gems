"""The operator table and the package-data payload lookup.

One row per operator maps a name to its install root and the payload files that
land under it. ``claude`` is the only entry in v1; adding kiro or copilot later
is a new :class:`Operator` row plus a payload directory, with no installer change.

Payload files are package data under ``klyreon/assets/payload/<operator>/`` and
are resolved through :mod:`importlib.resources`, so they are found from an
installed wheel, not only from the source tree.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

__all__ = [
    "KNOWN_OPERATORS",
    "Operator",
    "PayloadFile",
    "UnknownOperatorError",
    "known_operator_names",
    "payload_files",
    "resolve_target",
]

_PAYLOAD_ANCHOR = "klyreon.assets.payload"


class UnknownOperatorError(ValueError):
    """Raised when an operator name is not in :data:`KNOWN_OPERATORS`."""


@dataclass(frozen=True, slots=True)
class PayloadFile:
    """One packaged file and where it lands, relative to the operator's install root."""

    # POSIX-style relative path inside the payload package (e.g. "skills/klyreon/SKILL.md").
    package_relpath: str
    # POSIX-style relative path under the install root (same shape in v1).
    install_relpath: str


@dataclass(frozen=True, slots=True)
class Operator:
    """One operator: its name, how to find its install root, and its files."""

    name: str
    # Environment variable that overrides the install root base when set.
    config_env: str | None
    # Install root relative to $HOME when ``config_env`` is unset or empty.
    home_relpath: str
    files: tuple[PayloadFile, ...]


KNOWN_OPERATORS: dict[str, Operator] = {
    "claude": Operator(
        name="claude",
        config_env="CLAUDE_CONFIG_DIR",
        home_relpath=".claude",
        files=(
            PayloadFile(
                package_relpath="skills/klyreon/SKILL.md",
                install_relpath="skills/klyreon/SKILL.md",
            ),
        ),
    ),
}


def known_operator_names() -> list[str]:
    """Return the sorted list of known operator names."""
    return sorted(KNOWN_OPERATORS)


def _require_operator(operator: str) -> Operator:
    try:
        return KNOWN_OPERATORS[operator]
    except KeyError as exc:
        known = ", ".join(known_operator_names())
        msg = f"unknown operator {operator!r}; known operators: {known}"
        raise UnknownOperatorError(msg) from exc


def resolve_target(operator: str) -> Path:
    """Return the absolute install root for ``operator``.

    For ``claude`` this honours ``$CLAUDE_CONFIG_DIR`` when set and non-empty,
    falling back to ``~/.claude``. An unknown operator raises
    :class:`UnknownOperatorError` listing the known ones.
    """
    spec = _require_operator(operator)
    if spec.config_env:
        override = os.environ.get(spec.config_env)
        if override:
            return Path(override).expanduser().resolve()
    return (Path.home() / spec.home_relpath).resolve()


def _payload_root(operator: str) -> Traversable:
    """Return the Traversable anchored at this operator's payload directory."""
    return resources.files(_PAYLOAD_ANCHOR).joinpath(operator)


def payload_files(operator: str) -> list[tuple[PayloadFile, Traversable]]:
    """Return each payload file for ``operator`` paired with its resource handle.

    The resource handle is an :class:`importlib.abc.Traversable` so the content
    resolves from an installed wheel as well as from the source tree. Raises
    :class:`UnknownOperatorError` for an unknown operator, and
    :class:`FileNotFoundError` if a declared payload file is missing from the
    package (a packaging error, surfaced loudly rather than silently skipped).
    """
    spec = _require_operator(operator)
    root = _payload_root(operator)
    resolved: list[tuple[PayloadFile, Traversable]] = []
    for payload in spec.files:
        handle = root
        for part in payload.package_relpath.split("/"):
            handle = handle.joinpath(part)
        if not handle.is_file():
            msg = f"packaged payload file is missing for operator {operator!r}: {payload.package_relpath}"
            raise FileNotFoundError(msg)
        resolved.append((payload, handle))
    return resolved
