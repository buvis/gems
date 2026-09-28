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
from postup.domain.prompt import build_prompt
from postup.domain.repofiles import (
    read_brush_last_run,
    read_changelog_unreleased,
    read_prd_pipeline,
)

__all__ = [
    "EPICS_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "AttentionItem",
    "Epic",
    "EpicsPayload",
    "EpicsValidationError",
    "JudgmentTodo",
    "PortfolioData",
    "RepoData",
    "RepoEpics",
    "RepoSummary",
    "SchemaVersionError",
    "SinceLast",
    "Todo",
    "ViewModel",
    "build_prompt",
    "discover_repos",
    "load_portfolio_data",
    "load_view_model",
    "read_brush_last_run",
    "read_changelog_unreleased",
    "read_prd_pipeline",
    "stable_todo_id",
    "validate_epics",
    "write_outputs",
]
