from __future__ import annotations

import subprocess
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Input


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
    ]

    def __init__(self, rows: list[dict[str, Any]], columns: list[str]) -> None:
        super().__init__()
        self._rows = rows
        self._all_columns = columns
        self._display_columns = [c for c in columns if c != "file_path"]

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
