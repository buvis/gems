from __future__ import annotations

from pathlib import Path
from typing import Any

from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase
from bim.dependencies import get_formatter, get_repo
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Center, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select, Static


def _load_zettel(path: Path) -> Any:
    """Return the full ZettelData object."""
    repo = get_repo()
    zettel = repo.find_by_location(str(path))
    return zettel.get_data()


def _build_form_fields(metadata: dict[str, Any]) -> ComposeResult:
    yield Label("Title", classes="field-label")
    yield Input(value=str(metadata.get("title", "")), id="edit-title")

    yield Label("Type", classes="field-label")
    known_types = ["note", "project", "meeting", "person", "literature"]
    current_type = metadata.get("type", "note")
    if current_type and current_type not in known_types:
        known_types.insert(0, current_type)
    type_options = [(t, t) for t in known_types]
    yield Select(type_options, value=current_type, id="edit-type")

    yield Label("Tags (comma-separated)", classes="field-label")
    tags = metadata.get("tags", [])
    tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags or "")
    yield Input(value=tags_str, id="edit-tags")

    yield Label("Processed", classes="field-label")
    yield Checkbox("", value=bool(metadata.get("processed", False)), id="edit-processed")

    yield Label("Publish", classes="field-label")
    yield Checkbox("", value=bool(metadata.get("publish", False)), id="edit-publish")


def _gather_changes(query_one: Any, original: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}

    title = query_one("#edit-title", Input).value
    if title != str(original.get("title", "")):
        changes["title"] = title

    type_sel = query_one("#edit-type", Select)
    if type_sel.value is not Select.BLANK:
        new_type = str(type_sel.value)
        if new_type != original.get("type", "note"):
            changes["type"] = new_type

    tags_str = query_one("#edit-tags", Input).value
    new_tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str.strip() else []
    old_tags = original.get("tags", [])
    if not isinstance(old_tags, list):
        old_tags = []
    if new_tags != old_tags:
        changes["tags"] = new_tags

    processed = query_one("#edit-processed", Checkbox).value
    if processed != bool(original.get("processed", False)):
        changes["processed"] = processed

    publish = query_one("#edit-publish", Checkbox).value
    if publish != bool(original.get("publish", False)):
        changes["publish"] = publish

    return changes


class EditNoteApp(App[None]):
    """Standalone TUI for editing a zettel's metadata."""

    CSS = """
    VerticalScroll { padding: 1 2; }
    .field-label { margin-top: 1; color: $text-muted; }
    #preview { margin-top: 1; padding: 1; border: solid $accent; }
    Horizontal { margin-top: 1; }
    Button { margin-right: 1; }
    """
    BINDINGS = [("escape", "quit", "Cancel")]

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._zettel_data = _load_zettel(path)
        self._original = dict(self._zettel_data.metadata)

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield from _build_form_fields(self._original)
            yield Static(id="preview", markup=False)
            with Horizontal():
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")
        yield Footer()

    def on_mount(self) -> None:
        self._update_preview()

    @on(Input.Changed)
    @on(Select.Changed)
    @on(Checkbox.Changed)
    def _field_changed(self) -> None:
        self._update_preview()

    def _update_preview(self) -> None:
        import copy

        preview = self.query_one("#preview", Static)
        data = copy.deepcopy(self._zettel_data)
        changes = _gather_changes(self.query_one, self._original)
        data.metadata.update(changes)
        preview.update(PrintZettelUseCase(get_formatter()).execute(data))

    @on(Button.Pressed, "#save-btn")
    def _save(self) -> None:
        changes = _gather_changes(self.query_one, self._original)
        if changes:
            from bim.commands.edit_note.edit_note import edit_single

            msg = edit_single(self._path, changes, quiet=True)
            self.notify(msg)
        self.exit()

    @on(Button.Pressed, "#cancel-btn")
    def _cancel(self) -> None:
        self.exit()


class EditScreen(ModalScreen[dict[str, Any] | None]):
    """Modal edit screen pushable from query TUI."""

    CSS = """
    EditScreen { align: center middle; }
    #edit-dialog { width: 70; max-height: 80%; padding: 1 2; border: thick $accent; background: $surface; overflow-y: auto; }
    .field-label { margin-top: 1; color: $text-muted; }
    #preview { margin-top: 1; padding: 1; border: solid $accent; }
    #edit-buttons { width: 100%; height: auto; margin-top: 1; }
    #edit-buttons Button { margin: 0 1; }
    """

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._zettel_data = _load_zettel(path)
        self._original = dict(self._zettel_data.metadata)

    def compose(self) -> ComposeResult:
        with Center(id="edit-dialog"):
            yield from _build_form_fields(self._original)
            yield Static(id="preview", markup=False)
            with Center(id="edit-buttons"):
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        self._update_preview()

    @on(Input.Changed)
    @on(Select.Changed)
    @on(Checkbox.Changed)
    def _field_changed(self) -> None:
        self._update_preview()

    def _update_preview(self) -> None:
        import copy

        preview = self.query_one("#preview", Static)
        data = copy.deepcopy(self._zettel_data)
        changes = _gather_changes(self.query_one, self._original)
        data.metadata.update(changes)
        preview.update(PrintZettelUseCase(get_formatter()).execute(data))

    @on(Button.Pressed, "#save-btn")
    def _save(self) -> None:
        changes = _gather_changes(self.query_one, self._original)
        if changes:
            from bim.commands.edit_note.edit_note import edit_single

            edit_single(self._path, changes, quiet=True)
        self.dismiss({"file_path": str(self._path)})

    @on(Button.Pressed, "#cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(None)
