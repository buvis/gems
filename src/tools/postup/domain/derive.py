"""The Python derive layer: the deterministic view-model shared by CLI and TUI.

:func:`load_view_model` reads the file contracts under an output directory and
folds them into a typed, UI-free :class:`ViewModel` that both the text brief and
the Textual TUI render without recomputing anything (the all-interface rule).

This module is **pure and UI-free**: it imports neither ``textual`` nor ``click``
(asserted by an import-isolation test), reads the contracts only through
:func:`postup.domain.contracts.load_portfolio_data` and JSON, and never raises on
missing inputs — a missing ``data.json`` yields a ``needs_collect`` state, a
missing ``epics.json`` yields the deterministic (not-enriched) subset.

Fixture-parity seam (PRD 00068 / 00065)
---------------------------------------
The PRD's "Blocked by" names 00065 (shared JS/Python derive fixture payloads),
which is **not built yet**. So this derive layer and its tests own their fixture
payloads directly for now. These are the canonical derive inputs 00065 will later
adopt for the shared JS/Python parity suite; the JS/Python parity test is
**deferred until the JS derive exists** and is deliberately not added here. When
00065 lands, its fixtures should be reconciled against these and the parity test
added on the JS side.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from postup.domain.contracts import SchemaVersionError, load_portfolio_data

if TYPE_CHECKING:
    from pathlib import Path

    from postup.domain.contracts import PortfolioData, RepoData

__all__ = [
    "AttentionItem",
    "RepoSummary",
    "SinceLast",
    "Todo",
    "ViewModel",
    "load_view_model",
]

_CI_FAIL_STATES = frozenset({"failure", "timed_out", "startup_failure"})
_DIRTY_ATTENTION_DAYS = 7
_IDLE_WIP_ATTENTION_DAYS = 14
_BRUSH_CADENCE_DAYS = 30

# Attention urgency ranks — lower sorts first.
_URGENCY_RANK = {"now": 0, "soon": 1, "later": 2}


@dataclass(frozen=True, slots=True)
class AttentionItem:
    """One thing in the portfolio that wants the user's eyes, ranked.

    Attributes:
        repo: The ``owner/name`` the item concerns.
        urgency: ``now`` | ``soon`` | ``later`` — drives ordering.
        headline: One-line description of what needs attention.
        kind: A short machine tag for the source signal (``ci``, ``security``,
            ``review``, ``dirty``, ``wip-idle``, ``external-review``).
    """

    repo: str
    urgency: str
    headline: str
    kind: str


@dataclass(frozen=True, slots=True)
class Todo:
    """A mechanical or judgment follow-up.

    Mechanical todos are derived deterministically from the collected signals;
    judgment todos are lifted verbatim from ``epics.json`` (present only when the
    portfolio has been enriched).

    Attributes:
        repo: The ``owner/name`` the todo concerns.
        action: The imperative follow-up text.
        why: One line grounding the todo in the data.
        kind: ``mechanical`` or ``judgment``.
        urgency: ``now`` | ``soon`` | ``later``.
    """

    repo: str
    action: str
    why: str
    kind: str
    urgency: str


@dataclass(frozen=True, slots=True)
class RepoSummary:
    """A one-row summary of a repository's collected state.

    Attributes:
        repo: The ``owner/name`` slug.
        commits: Commit count in the window.
        open_prs: Open pull-request count.
        open_issues: Open issue count.
        failing_ci: Number of failing CI workflows on the default branch.
        alerts: Open security-alert count.
        unreleased: Unreleased-commit count (``0`` when unknown).
        dirty: Uncommitted-file count in the local checkout.
        errors: Per-repo degradation messages from the collector.
    """

    repo: str
    commits: int
    open_prs: int
    open_issues: int
    failing_ci: int
    alerts: int
    unreleased: int
    dirty: int
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SinceLast:
    """The diff of headline counts against the previous run.

    ``None`` deltas mean there was no previous snapshot to diff against.

    Attributes:
        has_prev: Whether a ``data-prev.json`` was found to diff against.
        commits: Delta of total commits since the previous run.
        open_prs: Delta of total open PRs.
        open_issues: Delta of total open issues.
        alerts: Delta of total security alerts.
        failing_ci: Delta of total failing CI workflows.
        new_repos: Repo slugs present now but not in the previous run.
        gone_repos: Repo slugs present in the previous run but not now.
    """

    has_prev: bool
    commits: int = 0
    open_prs: int = 0
    open_issues: int = 0
    alerts: int = 0
    failing_ci: int = 0
    new_repos: tuple[str, ...] = ()
    gone_repos: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ViewModel:
    """The full standup view-model both surfaces render.

    Attributes:
        needs_collect: ``True`` when no ``data.json`` was found — the surfaces
            show a "run postup collect first" cue and nothing else.
        enriched: ``True`` when ``epics.json`` was present and judgment content
            is available; ``False`` shows the deterministic subset with a
            not-enriched cue.
        generated_at: The collection timestamp (empty in the needs-collect state).
        summary: The enrichment narrative, or an empty string when not enriched.
        attention: Ranked attention queue.
        todos: Mechanical todos, followed by judgment todos when enriched.
        repos: Per-repo summaries, sorted by slug.
        since_last: The since-last diff.
        errors: Portfolio-level degradation messages (e.g. external-PR fetch).
    """

    needs_collect: bool
    enriched: bool
    generated_at: str = ""
    summary: str = ""
    attention: tuple[AttentionItem, ...] = ()
    todos: tuple[Todo, ...] = ()
    repos: tuple[RepoSummary, ...] = ()
    since_last: SinceLast = field(default_factory=lambda: SinceLast(has_prev=False))
    errors: tuple[str, ...] = ()


def load_view_model(out_dir: Path) -> ViewModel:
    """Read the contracts under ``out_dir`` and fold them into a view-model.

    Args:
        out_dir: Directory holding the postup file contracts.

    Returns:
        A :class:`ViewModel`. A missing or unreadable ``data.json`` yields the
        ``needs_collect`` state (never an exception); a missing ``epics.json``
        yields the deterministic, not-enriched subset.
    """
    data_file = out_dir / "data.json"
    if not data_file.is_file():
        return ViewModel(needs_collect=True, enriched=False)
    try:
        data = load_portfolio_data(data_file)
    except (OSError, ValueError, SchemaVersionError):
        return ViewModel(needs_collect=True, enriched=False)

    epics = _read_epics(out_dir)
    prev = _read_prev(out_dir)

    repos = _repo_summaries(data)
    attention = _attention_queue(data)
    todos = _mechanical_todos(data)
    if epics is not None:
        todos = todos + _judgment_todos(epics)

    return ViewModel(
        needs_collect=False,
        enriched=epics is not None,
        generated_at=data.generated_at,
        summary=str(epics.get("summary", "")) if epics else "",
        attention=attention,
        todos=todos,
        repos=repos,
        since_last=_since_last(data, prev),
        errors=_portfolio_errors(data),
    )


def _read_epics(out_dir: Path) -> dict[str, object] | None:
    """Return the parsed ``epics.json`` mapping, or ``None`` when absent/invalid.

    A malformed or non-object ``epics.json`` degrades to the not-enriched subset
    rather than raising — enrichment must never break the deterministic brief.
    """
    path = out_dir / "epics.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def _read_prev(out_dir: Path) -> PortfolioData | None:
    """Return the previous snapshot, or ``None`` when absent/unreadable."""
    path = out_dir / "data-prev.json"
    if not path.is_file():
        return None
    try:
        return load_portfolio_data(path)
    except (OSError, ValueError, SchemaVersionError):
        return None


def _failing_ci(repo: RepoData) -> int:
    """Count CI workflows whose latest run failed on the default branch."""
    return sum(1 for run in repo.ci if (run.conclusion or "") in _CI_FAIL_STATES)


def _repo_summaries(data: PortfolioData) -> tuple[RepoSummary, ...]:
    """Build the per-repo summary rows, sorted by ``owner/name``."""
    rows = [
        RepoSummary(
            repo=f"{repo.owner}/{repo.name}",
            commits=repo.commit_count,
            open_prs=len(repo.prs),
            open_issues=len(repo.issues),
            failing_ci=_failing_ci(repo),
            alerts=len(repo.security),
            unreleased=repo.unreleased_commits or 0,
            dirty=repo.local.dirty if repo.local else 0,
            errors=tuple(repo.errors),
        )
        for repo in data.repos
    ]
    return tuple(sorted(rows, key=lambda r: r.repo))


def _attention_queue(data: PortfolioData) -> tuple[AttentionItem, ...]:
    """Rank the portfolio's attention-worthy signals deterministically.

    Ordering is by urgency rank, then repo slug, then headline — a total order so
    the same payload always produces the same queue.
    """
    items: list[AttentionItem] = []
    for repo in data.repos:
        slug = f"{repo.owner}/{repo.name}"
        items.extend(_repo_attention(repo, slug))
    items.extend(_external_attention(data))
    return tuple(
        sorted(items, key=lambda i: (_URGENCY_RANK.get(i.urgency, 9), i.repo, i.headline)),
    )


def _repo_attention(repo: RepoData, slug: str) -> list[AttentionItem]:
    """Attention items sourced from one repository's signals."""
    items: list[AttentionItem] = []

    failing = _failing_ci(repo)
    if failing:
        items.append(
            AttentionItem(repo=slug, urgency="now", headline=f"{failing} failing CI workflow(s)", kind="ci"),
        )
    if repo.security:
        items.append(
            AttentionItem(
                repo=slug,
                urgency="now",
                headline=f"{len(repo.security)} open security alert(s)",
                kind="security",
            ),
        )
    review_prs = [pr for pr in repo.prs if not pr.draft]
    if review_prs:
        items.append(
            AttentionItem(
                repo=slug,
                urgency="soon",
                headline=f"{len(review_prs)} open PR(s) awaiting attention",
                kind="review",
            ),
        )
    local = repo.local
    if local and local.dirty and (local.dirty_since_days or 0) >= _DIRTY_ATTENTION_DAYS:
        items.append(
            AttentionItem(
                repo=slug,
                urgency="soon",
                headline=f"{local.dirty} file(s) dirty for {local.dirty_since_days}d",
                kind="dirty",
            ),
        )
    if repo.prds:
        for wip in repo.prds.wip:
            if wip.idle_days >= _IDLE_WIP_ATTENTION_DAYS:
                items.append(
                    AttentionItem(
                        repo=slug,
                        urgency="later",
                        headline=f"WIP PRD idle {wip.idle_days}d: {wip.title}",
                        kind="wip-idle",
                    ),
                )
    return items


def _external_attention(data: PortfolioData) -> list[AttentionItem]:
    """Attention items sourced from portfolio-external PRs."""
    items: list[AttentionItem] = []
    for pr in data.external.review_requested:
        items.append(
            AttentionItem(
                repo=pr.repo,
                urgency="soon",
                headline=f"review requested: #{pr.number} {pr.title}",
                kind="external-review",
            ),
        )
    return items


def _mechanical_todos(data: PortfolioData) -> tuple[Todo, ...]:
    """Build deterministic todos from the collected signals (no LLM).

    Sorted by urgency, then repo, then action for a stable order.
    """
    todos: list[Todo] = []
    for repo in data.repos:
        slug = f"{repo.owner}/{repo.name}"
        if repo.changelog_unreleased and repo.unreleased_commits:
            todos.append(
                Todo(
                    repo=slug,
                    action="cut a release",
                    why=f"{repo.unreleased_commits} unreleased commit(s) with a CHANGELOG entry",
                    kind="mechanical",
                    urgency="soon",
                ),
            )
        if _failing_ci(repo):
            todos.append(
                Todo(
                    repo=slug,
                    action="fix failing CI",
                    why="the default branch has a failing workflow",
                    kind="mechanical",
                    urgency="now",
                ),
            )
        if repo.branches and repo.branches.stray:
            merged = sum(1 for b in repo.branches.stray if b.merged)
            if merged:
                todos.append(
                    Todo(
                        repo=slug,
                        action="prune merged branches",
                        why=f"{merged} merged stray branch(es)",
                        kind="mechanical",
                        urgency="later",
                    ),
                )
    return tuple(
        sorted(todos, key=lambda t: (_URGENCY_RANK.get(t.urgency, 9), t.repo, t.action)),
    )


def _judgment_todos(epics: dict[str, object]) -> tuple[Todo, ...]:
    """Lift judgment todos from a parsed ``epics.json`` mapping.

    Malformed entries are skipped rather than raising, keeping the brief robust
    against a hand-edited or partially-valid ``epics.json``.
    """
    raw = epics.get("todos")
    if not isinstance(raw, list):
        return ()
    todos: list[Todo] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        repo = entry.get("repo")
        action = entry.get("action")
        if not isinstance(repo, str) or not isinstance(action, str):
            continue
        why = entry.get("why")
        urgency = entry.get("urgency")
        todos.append(
            Todo(
                repo=repo,
                action=action,
                why=why if isinstance(why, str) else "",
                kind="judgment",
                urgency=urgency if isinstance(urgency, str) else "later",
            ),
        )
    return tuple(
        sorted(todos, key=lambda t: (_URGENCY_RANK.get(t.urgency, 9), t.repo, t.action)),
    )


def _totals(data: PortfolioData) -> dict[str, int]:
    """Fold a snapshot into the scalar totals the since-last diff compares."""
    return {
        "commits": sum(r.commit_count for r in data.repos),
        "open_prs": sum(len(r.prs) for r in data.repos),
        "open_issues": sum(len(r.issues) for r in data.repos),
        "alerts": sum(len(r.security) for r in data.repos),
        "failing_ci": sum(_failing_ci(r) for r in data.repos),
    }


def _since_last(data: PortfolioData, prev: PortfolioData | None) -> SinceLast:
    """Diff the current snapshot's totals against the previous run."""
    if prev is None:
        return SinceLast(has_prev=False)
    now = _totals(data)
    before = _totals(prev)
    now_repos = {f"{r.owner}/{r.name}" for r in data.repos}
    prev_repos = {f"{r.owner}/{r.name}" for r in prev.repos}
    return SinceLast(
        has_prev=True,
        commits=now["commits"] - before["commits"],
        open_prs=now["open_prs"] - before["open_prs"],
        open_issues=now["open_issues"] - before["open_issues"],
        alerts=now["alerts"] - before["alerts"],
        failing_ci=now["failing_ci"] - before["failing_ci"],
        new_repos=tuple(sorted(now_repos - prev_repos)),
        gone_repos=tuple(sorted(prev_repos - now_repos)),
    )


def _portfolio_errors(data: PortfolioData) -> tuple[str, ...]:
    """Collect portfolio-level (non per-repo) degradation messages."""
    errors: list[str] = []
    if data.external.error:
        errors.append(f"external PRs: {data.external.error}")
    return tuple(errors)
