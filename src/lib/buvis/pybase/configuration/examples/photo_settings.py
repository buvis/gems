"""Example photo library settings."""

from __future__ import annotations

from pathlib import Path

from buvis.pybase.configuration.settings import GlobalSettings
from pydantic_settings import SettingsConfigDict


class PhotoSettings(GlobalSettings):
    """Settings for configuring photo management defaults.

    Attributes:
        library_path: Local path to the photo library root.
        thumbnail_size: Pixel dimension for generated thumbnails.
    """

    model_config = SettingsConfigDict(
        env_prefix="BUVIS_PHOTO_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    library_path: Path = Path.home() / "Pictures"
    thumbnail_size: int = 256
