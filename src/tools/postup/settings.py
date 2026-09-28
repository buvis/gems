"""Settings for the ``postup`` tool."""

from __future__ import annotations

from pathlib import Path

from buvis.pybase.configuration import GlobalSettings
from pydantic_settings import SettingsConfigDict

__all__ = ["PostupSettings", "default_out_dir"]


def default_out_dir() -> Path:
    """Return the default output directory (XDG data dir).

    Returns:
        ``~/.local/share/postup`` as an absolute path.
    """
    return Path.home() / ".local" / "share" / "postup"


class PostupSettings(GlobalSettings):
    """Validated ``postup`` settings.

    Layered from CLI overrides, environment variables (``BUVIS_POSTUP_``
    prefix), YAML config, and these defaults.

    Attributes:
        roots: Directories scanned for git repositories.
        excludes: Repository paths dropped from the discovered set.
        out_dir: Directory the file contracts are written to.
        model: Optional Claude model name (consumed by the enrich command in a
            later PRD; carried here so the settings contract is stable).
    """

    model_config = SettingsConfigDict(
        env_prefix="BUVIS_POSTUP_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    roots: list[str] = []
    excludes: list[str] = []
    out_dir: str = ""
    model: str | None = None

    @property
    def resolved_out_dir(self) -> Path:
        """Return the configured ``out_dir`` or the XDG default when unset."""
        return Path(self.out_dir).expanduser() if self.out_dir else default_out_dir()
