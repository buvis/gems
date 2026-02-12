"""Configuration source tracking."""

from __future__ import annotations

from enum import Enum

__all__ = ["ConfigSource"]


class ConfigSource(Enum):
    """Source from which a configuration value was obtained."""

    DEFAULT = "default"
    YAML = "yaml"
    ENV = "env"
    CLI = "cli"
