from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class TriageListParams(BaseModel):
    """Parameters for the ``bim doc triage`` (list) command.

    Enumerates pending triage proposals under ``<business_root>/_triage/``.
    Carries no fields today; the frozen model keeps a stable seam for future
    filters (by issuer, by doc type) without changing the command signature.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class TriageApproveParams(BaseModel):
    """Parameters for the ``bim doc triage --approve`` command.

    Marks a triage proposal approved and promotes it via the collision-safe
    promote path.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    proposed_yml_path: Path = Field(
        ...,
        description="Path to the .proposed.yml file to approve and promote.",
    )
