"""Settings for the ``bim tx`` command group (``tx:`` in the bim config)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TxSettings(BaseModel):
    """Tiromex run limits, maintenance windows and git identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    backend: str = "claude"
    max_sources_per_run: int = 5
    source_timeout_seconds: int = 900
    max_zettel_body_lines: int = 60
    maintenance_window_days: int = 7
    pruning_enabled: bool = False
    prune_window_days: int = 365
    git_identity_name: str = "bim-tx"
    git_identity_email: str = "bim-tx@localhost"
