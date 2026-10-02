"""Vault root discovery (spec section 10).

Resolution order:

1. ``$KLYREON_ROOT`` (spec 10.1 reason 2: test isolation) -- wins outright.
2. else the ``root`` key in ``$XDG_CONFIG_HOME/klyreon/config.yaml``,
   falling back to ``~/.config/klyreon/config.yaml``.

Every failure is loud and names the rule that broke; nothing is ever created
here. The returned root is absolute and exists.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

__all__ = ["RootError", "config_path", "resolve_root"]


class RootError(ValueError):
    """Raised when the vault root cannot be resolved per spec 10.4."""


def config_path() -> Path:
    """Return the klyreon config path, honouring ``$XDG_CONFIG_HOME``."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "klyreon" / "config.yaml"


def _validate_root(raw: str, *, origin: str) -> Path:
    """Expand, validate and return ``raw`` as an absolute existing directory."""
    expanded = Path(raw).expanduser()
    if not expanded.is_absolute():
        msg = f"root from {origin} must be an absolute path, got {raw!r}"
        raise RootError(msg)
    if not expanded.exists():
        msg = f"root from {origin} does not exist: {expanded}"
        raise RootError(msg)
    if not expanded.is_dir():
        msg = f"root from {origin} is not a directory: {expanded}"
        raise RootError(msg)
    return expanded.resolve()


def resolve_root() -> Path:
    """Resolve the vault root, or raise :class:`RootError` naming the rule.

    ``$KLYREON_ROOT`` wins when set; otherwise the config file is read.
    """
    env_root = os.environ.get("KLYREON_ROOT")
    if env_root:
        return _validate_root(env_root, origin="$KLYREON_ROOT")

    cfg = config_path()
    if not cfg.is_file():
        msg = (
            f"no vault root: $KLYREON_ROOT is unset and the config file is missing: {cfg}. "
            "Run 'klyreon init' or set $KLYREON_ROOT."
        )
        raise RootError(msg)

    try:
        loaded = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        msg = f"config file is not valid YAML: {cfg}: {exc}"
        raise RootError(msg) from exc

    if not isinstance(loaded, dict) or "root" not in loaded:
        msg = f"config file {cfg} has no 'root' key"
        raise RootError(msg)

    root_value = loaded["root"]
    if not isinstance(root_value, str) or not root_value.strip():
        msg = f"config file {cfg} 'root' must be a non-empty string"
        raise RootError(msg)

    return _validate_root(root_value, origin=str(cfg))
