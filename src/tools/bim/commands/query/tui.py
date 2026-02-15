from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from bim.dependencies import get_repo
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static


class ConfirmScreen(ModalScreen[bool]):
    CSS = """
    ConfirmScreen { align: center middle; }
    #confirm-dialog { width: 50; height: auto; padding: 1 2; border: thick $accent; background: $surface; }
    #confirm-buttons { width: 100%; height: auto; margin-top: 1; }
    #confirm-buttons Button { margin: 0 1; }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Center(id="confirm-dialog"):
            yield Label(self._message)
            with Center(id="confirm-buttons"):
                yield Button("Yes", variant="error", id="yes")
                yield Button("No", variant="primary", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class QueryTuiApp(App[None]):
    TITLE = "bim query"
    CSS = """
    Input { dock: top; margin: 0 1; }
    DataTable { height: 1fr; }
    """
    BINDINGS = [
        Binding("/", "focus_search", "Search", show=True),
        Binding("escape", "clear_search", "Clear", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("enter", "open_editor", "Open in nvim", show=True),
        Binding("a", "archive", "Archive", show=True),
        Binding("e", "edit", "Edit", show=True),
        Binding("s", "show", "Show", show=True),
        Binding("d", "delete", "Delete", show=True),
        Binding("f", "format", "Format", show=True),
    ]

    def __init__(
        self, rows: list[dict[str, Any]], columns: list[str], archive_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self._rows = rows
        self._all_columns = columns
        self._display_columns = [c for c in columns if c != "file_path"]
        self._archive_dir = archive_dir

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Type to filter...")
        yield DataTable()
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        for col in self._display_columns:
            table.add_column(col, key=col)
        self._populate(self._rows)

    def _populate(self, rows: list[dict[str, Any]]) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for row in rows:
            cells = [str(row.get(col, "")) for col in self._display_columns]
            table.add_row(*cells, key=str(id(row)))
        self._visible_rows = rows

    def on_input_changed(self, event: Input.Changed) -> None:
        term = event.value.lower()
        if not term:
            self._populate(self._rows)
            return
        filtered = [
            row
            for row in self._rows
            if any(term in str(row.get(col, "")).lower() for col in self._all_columns)
        ]
        self._populate(filtered)

    def action_focus_search(self) -> None:
        self.query_one(Input).focus()

    def action_clear_search(self) -> None:
        inp = self.query_one(Input)
        inp.value = ""
        self.query_one(DataTable).focus()

    def action_open_editor(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._visible_rows):
            return
        fp = self._visible_rows[row_idx].get("file_path")
        if not fp:
            return
        with self.suspend():
            subprocess.run(["nvim", str(fp)])

    def action_archive(self) -> None:
        if self._archive_dir is None:
            return
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._visible_rows):
            return
        fp = self._visible_rows[row_idx].get("file_path")
        if not fp:
            return
        self._pending_archive_path = fp
        self.push_screen(
            ConfirmScreen("Archive this note?"),
            callback=self._on_archive_confirmed,
        )

    def _on_archive_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._archive_dir is None:
            return
        fp = self._pending_archive_path
        from bim.commands.archive_note.archive_note import archive_single

        msg = archive_single(Path(fp), self._archive_dir, quiet=True)
        self.notify(msg)
        self._rows = [r for r in self._rows if r.get("file_path") != fp]
        self._populate(self._rows)

    def action_show(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._visible_rows):
            return
        fp = self._visible_rows[row_idx].get("file_path")
        if not fp:
            return
        from bim.commands.show_note.tui import ShowScreen

        self.push_screen(ShowScreen(Path(fp)))

    def action_delete(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._visible_rows):
            return
        fp = self._visible_rows[row_idx].get("file_path")
        if not fp:
            return
        self._pending_delete_path = fp
        self.push_screen(
            ConfirmScreen("Permanently delete this note?"),
            callback=self._on_delete_confirmed,
        )

    def _on_delete_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        fp = self._pending_delete_path
        from bim.commands.delete_note.delete_note import delete_single

        msg = delete_single(Path(fp), quiet=True)
        self.notify(msg)
        self._rows = [r for r in self._rows if r.get("file_path") != fp]
        self._populate(self._rows)

    def action_format(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._visible_rows):
            return
        fp = self._visible_rows[row_idx].get("file_path")
        if not fp:
            return
        from bim.commands.format_note.format_note import format_single

        format_single(Path(fp), in_place=True, quiet=True)
        self.notify(f"Formatted {Path(fp).name}")

    def action_edit(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._visible_rows):
            return
        fp = self._visible_rows[row_idx].get("file_path")
        if not fp:
            return
        from bim.commands.edit_note.tui import EditScreen

        self.push_screen(
            EditScreen(Path(fp)),
            callback=self._on_edit_done,
        )

    def _on_edit_done(self, result: dict[str, Any] | None) -> None:
        if result is None:
            return
        fp = result.get("file_path")
        if not fp:
            return
        # Re-read zettel from disk and update row columns that exist
        repo = get_repo()
        meta = repo.find_by_location(fp).get_data().metadata
        for row in self._rows:
            if str(row.get("file_path")) == fp:
                for key in row:
                    if key != "file_path" and key in meta:
                        row[key] = meta[key]
                break
        self._populate(self._rows)


# ---------------------------------------------------------------------------
# Kanban TUI
# ---------------------------------------------------------------------------


class KanbanCard(Static, can_focus=True):
    """Focusable card representing a single row."""

    def __init__(self, row: dict[str, Any], display_cols: list[str]) -> None:
        title = str(row.get("title", ""))
        extras = [
            str(row.get(c, ""))
            for c in display_cols
            if c != "title" and row.get(c)
        ]
        label = title or " | ".join(extras) or "(untitled)"
        if extras and title:
            label += f"\n[dim]{' | '.join(extras)}[/dim]"
        super().__init__(label, markup=True)
        self.row = row


class KanbanLane(VerticalScroll):
    """Scrollable column for one group value."""

    def __init__(self, title: str, rows: list[dict[str, Any]], display_cols: list[str]) -> None:
        super().__init__()
        self._title = title
        self._lane_rows = rows
        self._display_cols = display_cols
        self.border_title = f"{title} ({len(rows)})"

    def compose(self) -> ComposeResult:
        for row in self._lane_rows:
            yield KanbanCard(row, self._display_cols)


class KanbanTuiApp(App[None]):
    TITLE = "bim kanban"
    CSS = """
    Input { dock: top; margin: 0 1; }
    #kanban-board { height: 1fr; }
    KanbanLane {
        width: 1fr;
        border: solid $accent;
        margin: 0 1;
        padding: 0 1;
    }
    KanbanCard {
        margin: 1 0;
        padding: 1 2;
        background: $surface;
        border: tall $panel;
    }
    KanbanCard:focus {
        border: tall $accent;
        background: $boost;
    }
    """
    BINDINGS = [
        Binding("/", "focus_search", "Search", show=True),
        Binding("escape", "clear_search", "Clear", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("enter", "open_editor", "Open in nvim", show=True),
        Binding("a", "archive", "Archive", show=True),
        Binding("e", "edit", "Edit", show=True),
        Binding("s", "show", "Show", show=True),
        Binding("d", "delete", "Delete", show=True),
        Binding("f", "format", "Format", show=True),
    ]

    def __init__(
        self,
        rows: list[dict[str, Any]],
        columns: list[str],
        group_by: str,
        archive_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self._rows = rows
        self._all_columns = columns
        self._group_by = group_by
        self._display_cols = [c for c in columns if c not in ("file_path", group_by)]
        self._archive_dir = archive_dir
        self._filter = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Type to filter...")
        yield Horizontal(id="kanban-board")
        yield Footer()

    def on_mount(self) -> None:
        self._rebuild_lanes(self._rows)

    def _group_rows(self, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            key = str(row.get(self._group_by) or "Ungrouped") or "Ungrouped"
            groups.setdefault(key, []).append(row)
        return groups

    def _rebuild_lanes(self, rows: list[dict[str, Any]]) -> None:
        board = self.query_one("#kanban-board", Horizontal)
        board.remove_children()
        for group_name, group_rows in self._group_rows(rows).items():
            board.mount(KanbanLane(group_name, group_rows, self._display_cols))

    def on_input_changed(self, event: Input.Changed) -> None:
        self._filter = event.value.lower()
        if not self._filter:
            self._rebuild_lanes(self._rows)
            return
        filtered = [
            row
            for row in self._rows
            if any(self._filter in str(row.get(c, "")).lower() for c in self._all_columns)
        ]
        self._rebuild_lanes(filtered)

    def action_focus_search(self) -> None:
        self.query_one(Input).focus()

    def action_clear_search(self) -> None:
        inp = self.query_one(Input)
        inp.value = ""
        self.query_one("#kanban-board").focus()

    def _focused_row(self) -> dict[str, Any] | None:
        focused = self.focused
        if isinstance(focused, KanbanCard):
            return focused.row
        return None

    def action_open_editor(self) -> None:
        row = self._focused_row()
        if not row:
            return
        fp = row.get("file_path")
        if not fp:
            return
        with self.suspend():
            subprocess.run(["nvim", str(fp)])

    def action_archive(self) -> None:
        if self._archive_dir is None:
            return
        row = self._focused_row()
        if not row:
            return
        fp = row.get("file_path")
        if not fp:
            return
        self._pending_archive_path = fp
        self.push_screen(
            ConfirmScreen("Archive this note?"),
            callback=self._on_archive_confirmed,
        )

    def _on_archive_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._archive_dir is None:
            return
        fp = self._pending_archive_path
        from bim.commands.archive_note.archive_note import archive_single

        msg = archive_single(Path(fp), self._archive_dir, quiet=True)
        self.notify(msg)
        self._rows = [r for r in self._rows if r.get("file_path") != fp]
        self._rebuild_lanes(self._rows)

    def action_show(self) -> None:
        row = self._focused_row()
        if not row:
            return
        fp = row.get("file_path")
        if not fp:
            return
        from bim.commands.show_note.tui import ShowScreen

        self.push_screen(ShowScreen(Path(fp)))

    def action_delete(self) -> None:
        row = self._focused_row()
        if not row:
            return
        fp = row.get("file_path")
        if not fp:
            return
        self._pending_delete_path = fp
        self.push_screen(
            ConfirmScreen("Permanently delete this note?"),
            callback=self._on_delete_confirmed,
        )

    def _on_delete_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        fp = self._pending_delete_path
        from bim.commands.delete_note.delete_note import delete_single

        msg = delete_single(Path(fp), quiet=True)
        self.notify(msg)
        self._rows = [r for r in self._rows if r.get("file_path") != fp]
        self._rebuild_lanes(self._rows)

    def action_format(self) -> None:
        row = self._focused_row()
        if not row:
            return
        fp = row.get("file_path")
        if not fp:
            return
        from bim.commands.format_note.format_note import format_single

        format_single(Path(fp), in_place=True, quiet=True)
        self.notify(f"Formatted {Path(fp).name}")

    def action_edit(self) -> None:
        row = self._focused_row()
        if not row:
            return
        fp = row.get("file_path")
        if not fp:
            return
        from bim.commands.edit_note.tui import EditScreen

        self.push_screen(
            EditScreen(Path(fp)),
            callback=self._on_edit_done,
        )

    def _on_edit_done(self, result: dict[str, Any] | None) -> None:
        if result is None:
            return
        fp = result.get("file_path")
        if not fp:
            return
        repo = get_repo()
        meta = repo.find_by_location(fp).get_data().metadata
        for row in self._rows:
            if str(row.get("file_path")) == fp:
                for key in row:
                    if key != "file_path" and key in meta:
                        row[key] = meta[key]
                break
        self._rebuild_lanes(self._rows)
