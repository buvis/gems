from __future__ import annotations

from pathlib import Path

from buvis.pybase.adapters import console

from bim.commands.create_note.batch import create_single, parse_batch_file
from bim.dependencies import get_templates


class CommandCreateNote:
    def __init__(
        self,
        path_zettelkasten: Path,
        zettel_type: str | None = None,
        title: str | None = None,
        tags: str | None = None,
        extra_answers: dict[str, str] | None = None,
        batch_file: Path | None = None,
    ) -> None:
        if not path_zettelkasten.is_dir():
            raise FileNotFoundError(f"Zettelkasten directory not found: {path_zettelkasten}")
        self.path_zettelkasten = path_zettelkasten
        self.zettel_type = zettel_type
        self.title = title
        self.tags = tags
        self.extra_answers = extra_answers or {}
        self.batch_file = batch_file

    def _scripted(self) -> None:
        templates = get_templates()
        if self.zettel_type is None or self.title is None:
            console.panic("zettel_type and title are required for scripted mode")
            return
        if self.zettel_type not in templates:
            console.failure(f"Unknown template: {self.zettel_type}")
            return
        template = templates[self.zettel_type]
        create_single(
            self.path_zettelkasten,
            template,
            self.title,
            tags=self.tags,
            extra_answers=self.extra_answers,
        )

    def _batch(self) -> None:
        assert self.batch_file is not None
        default_type, default_tags, items = parse_batch_file(self.batch_file)
        templates = get_templates()
        created = 0
        failed = 0
        for item in items:
            zettel_type = item["type"] or self.zettel_type or default_type
            tags = item["tags"] or self.tags or default_tags
            if not zettel_type:
                console.failure(f"No type for '{item['title']}', skipping")
                failed += 1
                continue
            if zettel_type not in templates:
                console.failure(f"Unknown template '{zettel_type}' for '{item['title']}', skipping")
                failed += 1
                continue
            path = create_single(
                self.path_zettelkasten,
                templates[zettel_type],
                item["title"],
                tags=tags,
                extra_answers=item.get("answers", {}),
                quiet=True,
            )
            if path:
                created += 1
            else:
                failed += 1
        console.info(f"Batch: {created} created, {failed} failed")

    def execute(self) -> None:
        if self.batch_file:
            self._batch()
        elif self.zettel_type and self.title:
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
