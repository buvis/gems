from __future__ import annotations

from pathlib import Path
from typing import Any

from buvis.pybase.adapters import console
from buvis.pybase.zettel.application.use_cases.create_zettel_use_case import CreateZettelUseCase
from buvis.pybase.zettel.domain.templates import discover_templates
from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
    MarkdownZettelRepository,
)
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval


class CommandCreateNote:
    def __init__(
        self,
        path_zettelkasten: Path,
        zettel_type: str | None = None,
        title: str | None = None,
        tags: str | None = None,
        extra_answers: dict[str, str] | None = None,
    ) -> None:
        if not path_zettelkasten.is_dir():
            raise FileNotFoundError(f"Zettelkasten directory not found: {path_zettelkasten}")
        self.path_zettelkasten = path_zettelkasten
        self.zettel_type = zettel_type
        self.title = title
        self.tags = tags
        self.extra_answers = extra_answers or {}

    def _scripted(self) -> None:
        templates = discover_templates(python_eval)
        assert self.zettel_type is not None
        assert self.title is not None
        if self.zettel_type not in templates:
            console.failure(f"Unknown template: {self.zettel_type}")
            return
        template = templates[self.zettel_type]
        answers: dict[str, Any] = {"title": self.title}
        if self.tags:
            answers["tags"] = self.tags
        for q in template.questions():
            if q.key in self.extra_answers:
                answers[q.key] = self.extra_answers[q.key]
            elif q.default is not None:
                answers[q.key] = q.default
            elif q.required:
                console.failure(f"Missing required answer: {q.key}")
                return
        use_case = CreateZettelUseCase(self.path_zettelkasten, MarkdownZettelRepository())
        try:
            path = use_case.execute(template, answers)
        except FileExistsError as e:
            console.failure(str(e))
        else:
            console.success(f"Created {path}")

    def execute(self) -> None:
        if self.zettel_type and self.title:
            self._scripted()
        else:
            from bim.commands.create_note.tui import CreateNoteApp

            app = CreateNoteApp(
                path_zettelkasten=self.path_zettelkasten,
                preselected_type=self.zettel_type,
                preselected_title=self.title,
                preselected_tags=self.tags,
                extra_answers=self.extra_answers,
            )
            app.run()
