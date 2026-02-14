from __future__ import annotations

from pathlib import Path
from typing import Any

from buvis.pybase.zettel.application.use_cases.create_zettel_use_case import CreateZettelUseCase
from buvis.pybase.zettel.domain.templates import Question, ZettelTemplate
from buvis.pybase.zettel.infrastructure.persistence.template_loader import discover_templates
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import (
    MarkdownZettelFormatter,
)
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval
from bim.dependencies import get_repo
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static


class CreateNoteApp(App[None]):
    CSS = """
    VerticalScroll { padding: 1 2; }
    .field-label { margin-top: 1; color: $text-muted; }
    #preview { margin-top: 1; padding: 1; border: solid $accent; }
    Horizontal { margin-top: 1; }
    Button { margin-right: 1; }
    """
    BINDINGS = [("escape", "quit", "Cancel")]

    def __init__(
        self,
        path_zettelkasten: Path,
        preselected_type: str | None = None,
        preselected_title: str | None = None,
        preselected_tags: str | None = None,
        extra_answers: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.path_zettelkasten = path_zettelkasten
        self.preselected_type = preselected_type
        self.preselected_title = preselected_title
        self.preselected_tags = preselected_tags
        self.extra_answers = extra_answers or {}
        self.templates = discover_templates(python_eval)
        self._current_template: ZettelTemplate | None = None
        self._question_widgets: list[tuple[Question, Input | Select[str]]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Label("Template", classes="field-label")
            template_options = [(name, name) for name in sorted(self.templates)]
            if self.preselected_type and self.preselected_type in self.templates:
                yield Select(template_options, value=self.preselected_type, id="template-select")
            else:
                yield Select(template_options, prompt="Select template...", id="template-select")

            yield Label("Title", classes="field-label")
            yield Input(
                placeholder="Zettel title",
                value=self.preselected_title or "",
                id="title-input",
            )

            yield Label("Tags (comma-separated)", classes="field-label")
            yield Input(
                placeholder="tag1, tag2",
                value=self.preselected_tags or "",
                id="tags-input",
            )

            yield Static(id="questions-container")
            yield Static(id="preview", markup=False)

            with Horizontal():
                yield Button("Create", variant="primary", id="create-btn", disabled=True)
                yield Button("Cancel", variant="default", id="cancel-btn")
        yield Footer()

    def on_mount(self) -> None:
        if self.preselected_type and self.preselected_type in self.templates:
            self._on_template_selected(self.preselected_type)
            self._update_preview()

    @on(Select.Changed, "#template-select")
    def _template_changed(self, event: Select.Changed) -> None:
        if event.value is not Select.BLANK:
            self._on_template_selected(str(event.value))
            self._update_preview()

    def _on_template_selected(self, name: str) -> None:
        self._current_template = self.templates[name]
        container = self.query_one("#questions-container", Static)
        # Clear old question widgets
        for _, widget in self._question_widgets:
            widget.remove()
        # Also remove any labels we added
        for label in self.query(".question-label"):
            label.remove()
        self._question_widgets = []

        for q in self._current_template.questions():
            lbl = Label(q.prompt, classes="field-label question-label")
            container.mount(lbl)
            if q.choices:
                options = [(c, c) for c in q.choices]
                pre = self.extra_answers.get(q.key)
                if pre and pre in q.choices:
                    w: Input | Select[str] = Select(options, value=pre, id=f"q-{q.key}")
                elif q.default and q.default in q.choices:
                    w = Select(options, value=q.default, id=f"q-{q.key}")
                else:
                    w = Select(options, prompt=f"Select {q.prompt}...", id=f"q-{q.key}")
            else:
                w = Input(
                    placeholder=q.prompt,
                    value=self.extra_answers.get(q.key, q.default or ""),
                    id=f"q-{q.key}",
                )
            container.mount(w)
            self._question_widgets.append((q, w))

    @on(Input.Changed)
    @on(Select.Changed)
    def _field_changed(self) -> None:
        self._update_preview()

    def _gather_answers(self) -> dict[str, Any]:
        answers: dict[str, Any] = {}
        answers["title"] = self.query_one("#title-input", Input).value
        answers["tags"] = self.query_one("#tags-input", Input).value
        for q, widget in self._question_widgets:
            if isinstance(widget, Select):
                val = widget.value
                answers[q.key] = str(val) if val is not Select.BLANK else ""
            else:
                answers[q.key] = widget.value
        return answers

    def _update_preview(self) -> None:
        preview = self.query_one("#preview", Static)
        create_btn = self.query_one("#create-btn", Button)

        if not self._current_template:
            preview.update("")
            create_btn.disabled = True
            return

        answers = self._gather_answers()
        if not answers.get("title"):
            preview.update("[waiting for title]")
            create_btn.disabled = True
            return

        from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
        from buvis.pybase.zettel.domain.services.zettel_factory import ZettelFactory
        from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import (
            MarkdownZettelFormatter,
        )

        data = self._current_template.build_data(answers)
        zettel = Zettel(data)
        zettel = ZettelFactory.create(zettel)
        content = MarkdownZettelFormatter.format(zettel.get_data())
        preview.update(content)
        create_btn.disabled = False

    @on(Button.Pressed, "#create-btn")
    @work
    async def _create(self) -> None:
        if not self._current_template:
            return
        answers = self._gather_answers()

        use_case = CreateZettelUseCase(self.path_zettelkasten, get_repo())
        try:
            path = use_case.execute(self._current_template, answers)
        except FileExistsError as e:
            self.notify(str(e), severity="error")
        else:
            self.notify(f"Created {path}", severity="information")
            self.exit()

    @on(Button.Pressed, "#cancel-btn")
    def _cancel(self) -> None:
        self.exit()
