"""The ``epics.json`` contract: the enrichment schema the LLM must satisfy.

:class:`EpicsPayload` is the validated shape of the narrative summary, per-repo
epics referencing exact commit SHAs, and judgment todos with stable ids that a
:mod:`postup.commands.enrich` run writes to ``epics.json``. It is pure and
UI-free — no console, no subprocess, no Click.

Two guards make LLM output trustworthy:

* **SHA cross-check** — :func:`validate_epics` rejects any epic SHA that is not
  in the collected ``data.json`` commit set, so a hallucinated reference never
  reaches the brief.
* **Stable ids** — a judgment todo's id is derived deterministically from its
  content (:func:`stable_todo_id`) so the same finding keeps the same id across
  re-enrichment runs, and browser/server done-state survives.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    from pydantic_core import ErrorDetails

    from postup.domain.contracts import PortfolioData

__all__ = [
    "EPICS_SCHEMA_VERSION",
    "Epic",
    "EpicsPayload",
    "EpicsValidationError",
    "JudgmentTodo",
    "RepoEpics",
    "stable_todo_id",
    "validate_epics",
]

EPICS_SCHEMA_VERSION = 1

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SLUG_MAX = 40
_ID_HASH_LEN = 8

Urgency = Literal["now", "soon", "later"]
Importance = Literal["high", "low"]
Effort = Literal["quick", "medium", "deep"]


class EpicsValidationError(ValueError):
    """Raised when parsed LLM output fails the epics contract.

    Carries the human-readable reasons so the enrich command can append them to
    the retry prompt.
    """

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


class _Model(BaseModel):
    """Base model: reject unknown fields so LLM drift is caught loudly."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Epic(_Model):
    """One themed grouping of commits within a repository."""

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    shas: list[str] = Field(min_length=1)


class RepoEpics(_Model):
    """The epics collected for one ``owner/name`` repository."""

    epics: list[Epic] = Field(default_factory=list)


class JudgmentTodo(_Model):
    """A model-composed follow-up grounded in the collected data.

    Attributes:
        id: Stable, content-derived id (see :func:`stable_todo_id`). Done-state
            tracking keys off this, so it must not drift between runs.
        repo: The ``owner/name`` the todo concerns.
        urgency: ``now`` | ``soon`` | ``later``.
        action: Imperative follow-up the user can execute.
        why: One line grounding the todo in the data.
        importance: Eisenhower-matrix importance (default ``high``).
        effort: Rough effort estimate (default ``medium``).
    """

    id: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    kind: Literal["judgment"] = "judgment"
    urgency: Urgency
    action: str = Field(min_length=1)
    why: str = Field(min_length=1)
    importance: Importance = "high"
    effort: Effort = "medium"


class EpicsPayload(_Model):
    """The ``epics.json`` contract.

    Attributes:
        schema_version: Bumped loudly on any breaking change.
        summary: 2-4 short paragraphs in a manager voice — what moved across the
            portfolio, which themes dominate, what looks stuck or risky.
        repos: Per-repo epics keyed by ``owner/name``.
        todos: Judgment todos with stable ids.
    """

    schema_version: int = EPICS_SCHEMA_VERSION
    summary: str = Field(min_length=1)
    repos: dict[str, RepoEpics] = Field(default_factory=dict)
    todos: list[JudgmentTodo] = Field(default_factory=list)


def _slug(text: str) -> str:
    """Return a lowercase hyphen slug of ``text``, bounded in length."""
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug[:_SLUG_MAX].strip("-")


def stable_todo_id(repo: str, action: str) -> str:
    """Derive a deterministic id for a judgment todo from its content.

    The id is ``<repo>:judgment:<action-slug>-<hash>`` where the hash is a short
    BLAKE2b digest of ``repo`` and ``action``. Identical input always yields the
    identical id, so done-state keyed on the id survives re-enrichment; a changed
    action produces a new id (a materially different todo).

    Args:
        repo: The ``owner/name`` the todo concerns.
        action: The imperative follow-up text.

    Returns:
        A stable id string.
    """
    digest = hashlib.blake2b(f"{repo}\x1f{action}".encode(), digest_size=_ID_HASH_LEN // 2).hexdigest()
    slug = _slug(action) or "todo"
    return f"{repo}:judgment:{slug}-{digest}"


def _known_shas(data: PortfolioData) -> set[str]:
    """Return every commit SHA present in the collected portfolio data."""
    return {commit.sha for repo in data.repos for commit in repo.commits}


def validate_epics(raw: object, data: PortfolioData) -> EpicsPayload:
    """Validate parsed LLM output against the epics contract and the data.

    Beyond pydantic shape validation this cross-checks every epic SHA against the
    collected commit set — a SHA the collector never saw is a hallucination and
    fails validation rather than being silently dropped.

    Args:
        raw: The parsed JSON object from the model response.
        data: The collected portfolio data the enrichment is grounded in.

    Returns:
        The validated payload.

    Raises:
        EpicsValidationError: If the shape is invalid or an epic references a SHA
            absent from ``data``.
    """
    try:
        payload = EpicsPayload.model_validate(raw)
    except ValidationError as exc:
        raise EpicsValidationError([_format_pydantic_error(err) for err in exc.errors()]) from exc

    known = _known_shas(data)
    unknown: list[str] = []
    for repo_slug, repo_epics in payload.repos.items():
        for epic in repo_epics.epics:
            unknown.extend(
                f"{repo_slug}: unknown SHA {sha!r} (not in collected commits)" for sha in epic.shas if sha not in known
            )
    if unknown:
        raise EpicsValidationError(unknown)

    return payload


def _format_pydantic_error(err: ErrorDetails) -> str:
    """Render one pydantic error entry as a compact ``loc: message`` line."""
    loc = ".".join(str(part) for part in err.get("loc", ()))
    msg = err.get("msg", "invalid")
    return f"{loc or '<root>'}: {msg}"
