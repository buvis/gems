"""Typed, versioned on-disk contracts for portfolio data.

The :class:`PortfolioData` model is the ``data.json`` contract every other
postup interface consumes. It carries an explicit ``schema_version`` so later
PRDs can evolve the shape additively and reject an unknown version loudly.

All writes go through :func:`buvis.pybase.filesystem.atomic_write_text` per the
monorepo atomic-persistence invariant — never a bare ``write_text``/``open(w)``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal

from buvis.pybase.filesystem import atomic_write_text
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "SCHEMA_VERSION",
    "BranchInfo",
    "Branches",
    "CIRun",
    "Commit",
    "ExternalPRs",
    "ExternalPr",
    "Issue",
    "LocalState",
    "PortfolioData",
    "PrdPipeline",
    "PullRequest",
    "RepoData",
    "SchemaVersionError",
    "SecurityAlert",
    "WipPrd",
    "load_portfolio_data",
    "write_outputs",
]

SCHEMA_VERSION = 1

DIGEST_COMMITS = 50


class SchemaVersionError(ValueError):
    """Raised when reading a ``data.json`` whose ``schema_version`` is unknown."""


class _Model(BaseModel):
    """Base model: forbid unknown fields so contract drift is caught loudly."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Commit(_Model):
    """One commit in the collection window."""

    sha: str
    date: str
    author: str
    subject: str


class Release(_Model):
    """A published GitHub release."""

    tag: str
    name: str
    date: str | None = None
    prerelease: bool = False


class Issue(_Model):
    """An open issue."""

    number: int
    title: str
    created: str | None = None
    labels: list[str] = Field(default_factory=list)


class PullRequest(_Model):
    """An open pull request on the repo."""

    number: int
    title: str
    author: str
    created: str | None = None
    draft: bool = False
    review: str = ""
    checks: str = ""
    labels: list[str] = Field(default_factory=list)


class CIRun(_Model):
    """Latest run of one workflow on the default branch."""

    workflow: str
    status: str
    conclusion: str | None = None
    url: str
    date: str | None = None


class SecurityAlert(_Model):
    """An open security alert (dependabot or secret-scanning)."""

    kind: Literal["dependabot", "secret"]
    severity: str
    title: str
    url: str


class BranchInfo(_Model):
    """A stray remote/local branch (not the default branch)."""

    name: str
    date: str
    merged: bool


class Branches(_Model):
    """Stray branches and extra worktrees for a repo."""

    stray: list[BranchInfo] = Field(default_factory=list)
    worktrees: list[str] = Field(default_factory=list)


class WipPrd(_Model):
    """A work-in-progress PRD with its idle age."""

    title: str
    idle_days: int


class PrdPipeline(_Model):
    """PRD pipeline counts under ``dev/local/prds``."""

    backlog: list[str] = Field(default_factory=list)
    wip: list[WipPrd] = Field(default_factory=list)
    done_count: int = 0


class LocalState(_Model):
    """Local working-tree state relative to the tracked default branch."""

    branch: str
    dirty: int = 0
    dirty_since_days: int | None = None
    ahead: int = 0
    behind: int = 0
    stashes: int = 0


class ExternalPr(_Model):
    """A PR involving the user outside the scanned portfolio."""

    repo: str
    number: int
    title: str
    created: str | None = None
    url: str
    draft: bool = False


class ExternalPRs(_Model):
    """Open PRs involving the user across GitHub, outside the portfolio."""

    review_requested: list[ExternalPr] = Field(default_factory=list)
    authored: list[ExternalPr] = Field(default_factory=list)
    error: str | None = None


class RepoData(_Model):
    """The full collected signal set for one repository.

    Every signal is optional: a per-repo failure degrades into ``errors`` and
    WARNs rather than aborting the run, so a partially-collected repo still
    serializes cleanly.
    """

    path: str
    owner: str
    name: str
    default_branch: str | None = None
    description: str = ""
    language: str = ""
    stars: int = 0
    commit_count: int = 0
    commits: list[Commit] = Field(default_factory=list)
    releases: list[Release] = Field(default_factory=list)
    last_tag: str | None = None
    unreleased_commits: int | None = None
    issues: list[Issue] = Field(default_factory=list)
    prs: list[PullRequest] = Field(default_factory=list)
    ci: list[CIRun] = Field(default_factory=list)
    security: list[SecurityAlert] = Field(default_factory=list)
    branches: Branches | None = None
    prds: PrdPipeline | None = None
    changelog_unreleased: bool | None = None
    brush_last_run: str | None = None
    purge_last_run: str | None = None
    local: LocalState | None = None
    skipped: str | None = None
    errors: list[str] = Field(default_factory=list)


class PortfolioData(_Model):
    """The ``data.json`` contract.

    Attributes:
        schema_version: Bumped loudly on any breaking change; unknown values are
            rejected on read.
        generated_at: ISO-8601 UTC timestamp of the collection run.
        since_days: The commit window in days.
        repos: Fully or partially collected repositories.
        skipped: Repositories dropped before collection (non-github remote,
            unreadable) with a reason.
        external: PRs involving the user outside the portfolio.
    """

    schema_version: int = SCHEMA_VERSION
    generated_at: str
    since_days: int
    repos: list[RepoData] = Field(default_factory=list)
    skipped: list[RepoData] = Field(default_factory=list)
    external: ExternalPRs = Field(default_factory=ExternalPRs)


def _digest_markdown(repos: list[RepoData]) -> str:
    """Build the per-repo commit digest markdown."""
    lines: list[str] = []
    for repo in sorted(repos, key=lambda r: f"{r.owner}/{r.name}"):
        if not repo.commits:
            continue
        lines.append(f"## {repo.owner}/{repo.name}")
        lines += [f"{c.sha} {c.date} {c.subject}" for c in repo.commits[:DIGEST_COMMITS]]
        if len(repo.commits) > DIGEST_COMMITS:
            lines.append(f"... and {len(repo.commits) - DIGEST_COMMITS} more commits")
        lines.append("")
    return "\n".join(lines)


def _history_row(data: PortfolioData) -> dict[str, object]:
    """Fold one run into a compact history summary line."""
    fail_states = {"failure", "timed_out", "startup_failure"}
    repos: dict[str, dict[str, int]] = {}
    for repo in data.repos:
        local = repo.local
        prds = repo.prds
        failing = sum(1 for run in repo.ci if (run.conclusion or "") in fail_states)
        repos[f"{repo.owner}/{repo.name}"] = {
            "c": repo.commit_count,
            "i": len(repo.issues),
            "p": len(repo.prs),
            "a": len(repo.security),
            "f": failing,
            "d": local.dirty if local else 0,
            "ah": local.ahead if local else 0,
            "b": len(prds.backlog) if prds else 0,
            "w": len(prds.wip) if prds else 0,
            "s": repo.stars,
            "u": repo.unreleased_commits or 0,
        }
    return {"at": data.generated_at, "skipped": len(data.skipped), "repos": repos}


def load_portfolio_data(path: Path) -> PortfolioData:
    """Read and validate a ``data.json`` file.

    Args:
        path: Path to the ``data.json`` contract.

    Returns:
        The validated portfolio data.

    Raises:
        SchemaVersionError: If ``schema_version`` is missing or unknown.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    version = raw.get("schema_version") if isinstance(raw, dict) else None
    if version != SCHEMA_VERSION:
        raise SchemaVersionError(
            f"unknown schema_version {version!r} in {path} (this postup expects {SCHEMA_VERSION})",
        )
    return PortfolioData.model_validate(raw)


def write_outputs(data: PortfolioData, out_dir: Path) -> None:
    """Write the four file contracts atomically under ``out_dir``.

    Rotation order guarantees ``data-prev.json`` holds the prior ``data.json``
    even if the run dies mid-write: the previous snapshot is rotated **before**
    the new ``data.json`` is published.

    Args:
        data: The collected portfolio data.
        out_dir: Directory the contracts are written to (created if absent).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    data_file = out_dir / "data.json"

    # Rotate the previous snapshot BEFORE overwriting data.json so data-prev.json
    # is always the prior run even if we crash before the new data.json lands.
    if data_file.is_file():
        atomic_write_text(out_dir / "data-prev.json", data_file.read_text(encoding="utf-8"))

    payload = data.model_dump(mode="json")
    atomic_write_text(data_file, json.dumps(payload, indent=1))
    atomic_write_text(out_dir / "commits-digest.md", _digest_markdown(data.repos))

    history_file = out_dir / "history.jsonl"
    existing = history_file.read_text(encoding="utf-8") if history_file.is_file() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    atomic_write_text(history_file, existing + json.dumps(_history_row(data)) + "\n")
