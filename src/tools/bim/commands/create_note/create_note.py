from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from buvis.pybase.result import CommandResult
from buvis.pybase.zettel.application.use_cases.create_zettel_use_case import CreateZettelUseCase

from bim.params.create_note import CreateNoteParams

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository


class CommandCreateNote:
    def __init__(
        self,
        params: CreateNoteParams,
        path_zettelkasten: Path,
        repo: ZettelRepository,
        templates: dict[str, Any],
        hook_runner: Any,
    ) -> None:
        if not path_zettelkasten.is_dir():
            raise FileNotFoundError(f"Zettelkasten directory not found: {path_zettelkasten}")
        self.params = params
        self.path_zettelkasten = path_zettelkasten
        self.repo = repo
        self.templates = templates
        self.hook_runner = hook_runner
        self.extra_answers = self.params.extra_answers or {}

    def execute(self) -> CommandResult:
        if self.params.zettel_type is None or self.params.title is None:
            return CommandResult(success=False, error="zettel_type and title are required")
        if self.params.zettel_type not in self.templates:
            return CommandResult(success=False, error=f"Unknown template: {self.params.zettel_type}")

        template = self.templates[self.params.zettel_type]
        answers: dict[str, Any] = {"title": self.params.title}
        if self.params.tags:
            answers["tags"] = self.params.tags
        for q in template.questions():
            if q.key in self.extra_answers:
                answers[q.key] = self.extra_answers[q.key]
            elif q.default is not None:
                answers[q.key] = q.default
            elif q.required:
                return CommandResult(success=False, error=f"Missing required answer: {q.key}")
        use_case = CreateZettelUseCase(
            self.path_zettelkasten,
            self.repo,
            hook_runner=self.hook_runner,
        )
        try:
            path = use_case.execute(template, answers)
        except FileExistsError as e:
            return CommandResult(success=False, error=str(e))
        return CommandResult(
            success=True,
            output=f"Created {path}",
            metadata={"path": path},
        )
