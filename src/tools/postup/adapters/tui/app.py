"""The postup Textual application: a read-only standup over the derive layer.

:class:`PostupApp` renders the attention queue, todos, and repo list from a
:class:`postup.domain.derive.ViewModel` — it *consumes* the view-model and
computes nothing itself (the all-interface rule). The same derive output drives
the text brief, so both surfaces show identical facts.

Textual is an optional dependency (the ``postup`` extra); importing this module
requires it. The CLI layer catches the ``ImportError`` and renders install
guidance via ``console.require_import`` — a missing extra never reaches the user
as a traceback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import DataTable, Footer, Header, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from postup.domain.derive import ViewModel

__all__ = ["PostupApp"]


class PostupApp(App[None]):
    """Read-only Textual standup rendered from a derive view-model."""

    TITLE = "postup — portfolio standup"

    CSS = """
    #summary {
        padding: 0 1;
        color: $text-muted;
    }
    #attention-title, #todos-title, #repos-title {
        text-style: bold;
        padding: 1 1 0 1;
    }
    #cue {
        padding: 1;
        color: $warning;
    }
    DataTable {
        height: auto;
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, view_model: ViewModel) -> None:
        super().__init__()
        self._vm = view_model

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield from self._compose_body()
        yield Footer()

    def _compose_body(self) -> ComposeResult:
        vm = self._vm
        if vm.needs_collect:
            yield Static("No data yet — run 'postup collect' first.", id="cue")
            return

        yield Static(f"generated {vm.generated_at}", id="summary")
        if vm.enriched and vm.summary:
            yield Static(vm.summary, id="summary")
        elif not vm.enriched:
            yield Static(
                "not enriched — run 'postup enrich' for narrative and judgment todos",
                id="cue",
            )

        with Vertical():
            yield Static("Attention", id="attention-title")
            yield self._attention_table()
            yield Static("Todos", id="todos-title")
            yield self._todos_table()
            yield Static("Repos", id="repos-title")
            yield self._repos_table()

    def _attention_table(self) -> DataTable[str]:
        """Build the attention-queue table."""
        table: DataTable[str] = DataTable(id="attention", cursor_type="row", zebra_stripes=True)
        table.add_columns("urgency", "repo", "headline")
        for item in self._vm.attention:
            table.add_row(item.urgency, item.repo, item.headline)
        if not self._vm.attention:
            table.add_row("—", "—", "nothing needs eyes")
        return table

    def _todos_table(self) -> DataTable[str]:
        """Build the todos table (mechanical + judgment)."""
        table: DataTable[str] = DataTable(id="todos", cursor_type="row", zebra_stripes=True)
        table.add_columns("kind", "urgency", "repo", "action", "why")
        for todo in self._vm.todos:
            table.add_row(todo.kind, todo.urgency, todo.repo, todo.action, todo.why)
        if not self._vm.todos:
            table.add_row("—", "—", "—", "no todos", "—")
        return table

    def _repos_table(self) -> DataTable[str]:
        """Build the per-repo summary table."""
        table: DataTable[str] = DataTable(id="repos", cursor_type="row", zebra_stripes=True)
        table.add_columns("repo", "commits", "PRs", "issues", "CI-fail", "alerts", "unreleased", "dirty")
        for repo in self._vm.repos:
            table.add_row(
                repo.repo,
                str(repo.commits),
                str(repo.open_prs),
                str(repo.open_issues),
                str(repo.failing_ci),
                str(repo.alerts),
                str(repo.unreleased),
                str(repo.dirty),
            )
        if not self._vm.repos:
            table.add_row("no repos", "0", "0", "0", "0", "0", "0", "0")
        return table
