from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from buvis.pybase.configuration import GlobalSettings
from pydantic import field_validator
from pydantic_settings import SettingsConfigDict


class BraidSettings(GlobalSettings):
    # A repository's config must not enroll skills or redirect host roots.
    config_include_cwd: ClassVar[bool] = False

    model_config = SettingsConfigDict(
        env_prefix="BUVIS_BRAID_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    agents_root: Path = Path("~/.agents")
    claude_root: Path = Path("~/.claude")
    sources: tuple[Path, ...] = ()
    policies: tuple[Path, ...] = ()
    kiro_root: Path | None = None

    @field_validator("kiro_root", mode="before")
    @classmethod
    def _empty_kiro_root_is_unset(cls, value: object) -> object:
        return None if value == "" else value
