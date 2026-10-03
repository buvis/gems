from __future__ import annotations

from buvis.pybase.configuration import GlobalSettings
from pydantic_settings import SettingsConfigDict


class KlyreonSettings(GlobalSettings):
    """Settings for everything that is not the vault root.

    The vault root is deliberately NOT a setting: it lives in klyreon's own
    config file (``~/.config/klyreon/config.yaml``, key ``root``) so that any
    tool reading the vault discovers the root the same way (spec section 10).
    """

    model_config = SettingsConfigDict(
        env_prefix="BUVIS_KLYREON_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    backend: str = "claude"
    model: str | None = None
    max_sources_per_run: int = 5
    source_timeout_seconds: int = 900
    max_zettel_body_lines: int = 60
    maintenance_window_days: int = 7
    pruning_enabled: bool = False
    prune_window_days: int = 365
    git_identity_name: str = "klyreon"
    git_identity_email: str = "klyreon@localhost"
