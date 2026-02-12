"""Example music library settings."""

from __future__ import annotations

from pathlib import Path

from buvis.pybase.configuration.settings import GlobalSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class MusicSettings(GlobalSettings):
    """Settings for configuring music library defaults.

    Attributes:
        library_path: Local path to the music library root.
        formats: Audio formats to include when scanning the library.
    """

    model_config = SettingsConfigDict(
        env_prefix="BUVIS_MUSIC_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    library_path: Path = Path.home() / "Music"
    formats: list[str] = Field(default=["mp3", "flac", "wav"])
