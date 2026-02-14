from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from buvis.pybase.zettel import MarkdownZettelRepository
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label


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

    def _on_archive_confirmed(self, confirmed: bool) -> None:
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

    def _on_delete_confirmed(self, confirmed: bool) -> None:
        if not confirmed:
            return
        fp = self._pending_delete_path
        from bim.commands.delete_note.delete_note import delete_single

        msg = delete_single(Path(fp), quiet=True)
        self.notify(msg)
        self._rows = [r for r in self._rows if r.get("file_path") != fp]
        self._populate(self._rows)

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
        repo = MarkdownZettelRepository()
        meta = repo.find_by_location(fp).get_data().metadata
        for row in self._rows:
            if str(row.get("file_path")) == fp:
                for key in row:
                    if key != "file_path" and key in meta:
                        row[key] = meta[key]
                break
        self._populate(self._rows)
