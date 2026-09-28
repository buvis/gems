"""Postup domain layer: pure discovery and typed file contracts.

No UI-framework imports here — the library-agnostic seam per AGENTS.md.
"""

from __future__ import annotations

from postup.domain.contracts import (
    SCHEMA_VERSION,
    PortfolioData,
    RepoData,
    SchemaVersionError,
    load_portfolio_data,
    write_outputs,
)
from postup.domain.discovery import discover_repos
from postup.domain.repofiles import (
    read_brush_last_run,
    read_changelog_unreleased,
    read_prd_pipeline,
)

__all__ = [
    "SCHEMA_VERSION",
    "PortfolioData",
    "RepoData",
    "SchemaVersionError",
    "discover_repos",
    "load_portfolio_data",
    "read_brush_last_run",
    "read_changelog_unreleased",
    "read_prd_pipeline",
    "write_outputs",
]
