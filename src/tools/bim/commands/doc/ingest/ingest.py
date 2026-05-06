"""CommandIngest — thin wrapper that delegates to the Pipeline.

The pipeline does all the orchestration; this command class exists so the
CLI handler has a uniform ``CommandResult``-returning entry point and so
``MissingDependency`` (raised by ``health.check_health`` and bubbling up
from the boundary services) maps to a structured failure rather than a
stack trace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from bim.commands.doc.shared.health import MissingDependency

if TYPE_CHECKING:
    from bim.commands.doc.shared.pipeline import Pipeline
    from bim.params.doc_ingest import IngestParams

__all__ = ["CommandIngest"]


class CommandIngest:
    """Run the doc ingest pipeline for one staged document."""

    def __init__(self, *, params: IngestParams, pipeline: Pipeline) -> None:
        self._params = params
        self._pipeline = pipeline

    def execute(self) -> CommandResult:
        try:
            return self._pipeline.run(self._params)
        except MissingDependency as exc:
            return CommandResult(
                success=False,
                error=str(exc),
                metadata={
                    "missing_dependency": True,
                    "tool": str(exc),
                    "install_hint": "Install with: uv tool install buvis-gems[doc]",
                },
            )
