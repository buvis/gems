"""The ``postup brief`` command — and the bare-``postup`` default surface.

Renders the deterministic text standup (attention queue, mechanical todos, repo
summary, since-last diff) from the latest ``data.json`` via the console adapter,
and returns a :class:`CommandResult`. Judgment todos and the narrative summary
appear only when ``epics.json`` exists; otherwise a one-line "not enriched" cue
is shown.

This path is the default command surface, so it must stay light: it imports the
pure :mod:`postup.domain.derive` layer and **never** Textual or any web
dependency (asserted by an import-isolation test). Following the ``CommandResult``
discipline, the command computes the standup text and returns it in the result's
metadata — the CLI adapter renders it. No console/Click/Textual import here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from postup.domain.derive import load_view_model
from postup.domain.meta_share import collect as collect_meta_share

if TYPE_CHECKING:
    from postup.domain.derive import ViewModel
    from postup.domain.meta_share import MetaShare
    from postup.settings import PostupSettings

__all__ = ["CommandBrief", "render_brief"]


class CommandBrief:
    """Render the deterministic text standup from the collected contracts.

    The command produces the standup *text* and returns it in the result
    metadata; the CLI adapter is responsible for printing it (``CommandResult``
    discipline — commands never touch the console).

    Args:
        settings: Resolved postup settings (``out_dir``).
    """

    def __init__(self, settings: PostupSettings) -> None:
        self.settings = settings

    def execute(self) -> CommandResult:
        """Load the view-model, render the standup text, and return it.

        Returns:
            A failure result with the "run postup collect first" guidance when no
            ``data.json`` exists; a success result whose ``metadata['text']``
            holds the rendered standup for the CLI to print.
        """
        out_dir = self.settings.resolved_out_dir
        vm = load_view_model(out_dir)
        if vm.needs_collect:
            return CommandResult(
                success=False,
                error=f"no data.json in {out_dir} — run 'postup collect' first",
            )

        # The meta-budget share is a LIVE read of the cost ledger, not a
        # collected snapshot, so the text brief computes it fresh at render time.
        # An absent/empty ledger yields the n/a state (never raises).
        meta = collect_meta_share()
        text = render_brief(vm, meta)
        return CommandResult(
            success=True,
            output=f"rendered brief for {len(vm.repos)} repo(s)" + ("" if vm.enriched else " (not enriched)"),
            metadata={
                "text": text,
                "repos": len(vm.repos),
                "attention": len(vm.attention),
                "todos": len(vm.todos),
                "enriched": vm.enriched,
            },
        )


def render_brief(vm: ViewModel, meta: MetaShare | None = None) -> str:
    """Render a view-model into the deterministic plain-text standup.

    Pure and UI-free: takes the view-model (and the optional meta-budget share)
    and returns a string, so the exact output can be asserted in a unit test
    without a console.

    Args:
        vm: The derived view-model.
        meta: The trailing-window meta-budget share, or ``None`` to omit the
            tile. When present but unavailable, the tile renders ``meta n/a``.

    Returns:
        The standup as a newline-joined string.
    """
    lines: list[str] = ["Portfolio standup", f"generated {vm.generated_at}", ""]

    if vm.enriched and vm.summary:
        lines += ["Summary", *_indent(vm.summary.splitlines()), ""]
    elif not vm.enriched:
        lines += ["(not enriched — run 'postup enrich' for narrative and judgment todos)", ""]

    lines += _meta_budget_section(meta)
    lines += _attention_section(vm)
    lines += _todos_section(vm)
    lines += _repos_section(vm)
    lines += _since_last_section(vm)
    lines += _errors_section(vm)

    return "\n".join(lines).rstrip() + "\n"


def _meta_budget_section(meta: MetaShare | None) -> list[str]:
    """Render the meta-budget tile: share of spend with an inclusive-ceiling state.

    Omitted entirely when ``meta`` is ``None`` (the caller chose not to compute
    it). Renders ``Meta budget: n/a`` when the ledger held no priced session for
    the window, ``over ceiling``/``ok`` otherwise. The state word is the text
    surface's equivalent of the web tile's red/green.
    """
    if meta is None:
        return []
    if not meta.available:
        return ["Meta budget: n/a (no cost data for the window)", ""]
    state = "over ceiling" if meta.over_ceiling else "ok"
    return [
        (
            f"Meta budget: {meta.meta_pct:.0f}% of ${meta.total_usd:.2f} "
            f"({meta.window_days}d) — {state} [ceiling {meta.ceiling_pct:.0f}%]"
        ),
        "",
    ]


def _indent(rows: list[str]) -> list[str]:
    """Indent each row by two spaces."""
    return [f"  {row}" for row in rows]


def _attention_section(vm: ViewModel) -> list[str]:
    """Render the ranked attention queue."""
    if not vm.attention:
        return ["Attention: nothing needs eyes", ""]
    rows = [f"[{item.urgency}] {item.repo}: {item.headline}" for item in vm.attention]
    return ["Attention", *_indent(rows), ""]


def _todos_section(vm: ViewModel) -> list[str]:
    """Render mechanical (and, when enriched, judgment) todos."""
    mechanical = [t for t in vm.todos if t.kind == "mechanical"]
    judgment = [t for t in vm.todos if t.kind == "judgment"]

    lines: list[str] = ["Todos"]
    if mechanical:
        lines.append("  mechanical:")
        lines += [f"    - {t.repo}: {t.action} ({t.why})" for t in mechanical]
    else:
        lines.append("  mechanical: none")
    if judgment:
        lines.append("  judgment:")
        lines += [f"    - [{t.urgency}] {t.repo}: {t.action} ({t.why})" for t in judgment]
    return [*lines, ""]


def _repos_section(vm: ViewModel) -> list[str]:
    """Render the per-repo summary rows."""
    if not vm.repos:
        return ["Repos: none", ""]
    lines = ["Repos"]
    for repo in vm.repos:
        row = (
            f"  {repo.repo}: {repo.commits} commits, {repo.open_prs} PRs, "
            f"{repo.open_issues} issues, {repo.failing_ci} CI-fail, "
            f"{repo.alerts} alerts, {repo.unreleased} unreleased, {repo.dirty} dirty"
        )
        lines.append(row)
        if repo.errors:
            lines += [f"    ! {err}" for err in repo.errors]
    return [*lines, ""]


def _since_last_section(vm: ViewModel) -> list[str]:
    """Render the since-last diff, or a first-run note when there is no prev."""
    diff = vm.since_last
    if not diff.has_prev:
        return ["Since last: no previous run to compare", ""]
    lines = [
        "Since last",
        f"  commits {_signed(diff.commits)}, PRs {_signed(diff.open_prs)}, "
        f"issues {_signed(diff.open_issues)}, alerts {_signed(diff.alerts)}, "
        f"CI-fail {_signed(diff.failing_ci)}",
    ]
    if diff.new_repos:
        lines.append(f"  new: {', '.join(diff.new_repos)}")
    if diff.gone_repos:
        lines.append(f"  gone: {', '.join(diff.gone_repos)}")
    return [*lines, ""]


def _errors_section(vm: ViewModel) -> list[str]:
    """Render portfolio-level degradation messages when present."""
    if not vm.errors:
        return []
    return ["Warnings", *_indent(list(vm.errors)), ""]


def _signed(value: int) -> str:
    """Format an integer delta with an explicit sign (``+3``/``-1``/``0``)."""
    return f"+{value}" if value > 0 else str(value)
