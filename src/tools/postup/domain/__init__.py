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
from postup.domain.derive import (
    AttentionItem,
    RepoSummary,
    SinceLast,
    Todo,
    ViewModel,
    load_view_model,
)
from postup.domain.discovery import discover_repos
from postup.domain.epics import (
    EPICS_SCHEMA_VERSION,
    Epic,
    EpicsPayload,
    EpicsValidationError,
    JudgmentTodo,
    RepoEpics,
    stable_todo_id,
    validate_epics,
)
from postup.domain.meta_share import META_CEILING_PCT, MetaShare, collect as collect_meta_share
from postup.domain.prompt import build_prompt
from postup.domain.repofiles import (
    read_brush_last_run,
    read_changelog_unreleased,
    read_prd_pipeline,
    read_purge_last_run,
)

__all__ = [
    "EPICS_SCHEMA_VERSION",
    "META_CEILING_PCT",
    "SCHEMA_VERSION",
    "AttentionItem",
    "Epic",
    "EpicsPayload",
    "EpicsValidationError",
    "JudgmentTodo",
    "MetaShare",
    "PortfolioData",
    "RepoData",
    "RepoEpics",
    "RepoSummary",
    "SchemaVersionError",
    "SinceLast",
    "Todo",
    "ViewModel",
    "build_prompt",
    "collect_meta_share",
    "discover_repos",
    "load_portfolio_data",
    "load_view_model",
    "read_brush_last_run",
    "read_changelog_unreleased",
    "read_prd_pipeline",
    "read_purge_last_run",
    "stable_todo_id",
    "validate_epics",
    "write_outputs",
]
