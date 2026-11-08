from __future__ import annotations

from pathlib import Path

from buvis.pybase.configuration import GlobalSettings
from pydantic import field_validator
from pydantic_settings import SettingsConfigDict


class BraidSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_BRAID_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    agents_root: Path = Path("~/.agents")
    claude_root: Path = Path("~/.claude")
    config_root: Path = Path("~/.config/braid")
    kiro_root: Path | None = None

    @field_validator("kiro_root", mode="before")
    @classmethod
    def _empty_kiro_root_is_unset(cls, value: object) -> object:
        return None if value == "" else value
