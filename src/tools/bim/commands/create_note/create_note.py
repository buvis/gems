from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from buvis.pybase.result import CommandResult
from buvis.pybase.zettel.application.use_cases.create_zettel_use_case import CreateZettelUseCase
from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
    from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository

    from bim.params.create_note import CreateNoteParams

MAX_TRASH_ATTEMPTS = 1000


class CommandCreateNote:
    def __init__(  # noqa: PLR0913, PLR0917 — preserve the shared composition contract
        self,
        params: CreateNoteParams,
        path_zettelkasten: Path,
        repo: ZettelRepository,
        templates: dict[str, Any],
        hook_runner: Any,
        formatter: ZettelFormatter,
    ) -> None:
        if not path_zettelkasten.is_dir():
            raise FileNotFoundError(f"Zettelkasten directory not found: {path_zettelkasten}")
        self.params = params
        self.path_zettelkasten = path_zettelkasten.resolve()
        self.vault_root = self.path_zettelkasten.parent
        self.repo = repo
        self.templates = templates
        self.hook_runner = hook_runner
        self.formatter = formatter
        self.extra_answers = self.params.extra_answers or {}

    def execute(self) -> CommandResult:
        try:
            title, body, source = self._inputs()
            if self.params.zettel_type is None or title is None:
                return CommandResult(success=False, error="zettel_type and title are required")
            if self.params.zettel_type not in self.templates:
                return CommandResult(success=False, error=f"Unknown template: {self.params.zettel_type}")
            template = self.templates[self.params.zettel_type]
            answers = self._answers(template, title)
            use_case = CreateZettelUseCase(self.path_zettelkasten, self.repo, hook_runner=self.hook_runner)
            if self.params.dry_run:
                path, zettel = use_case.prepare(template, answers, body=body)
                metadata = self._metadata(path, zettel)
                metadata.update(dry_run=True, content=PrintZettelUseCase(self.formatter).execute(zettel.get_data()))
                return CommandResult(success=True, metadata=metadata)
            path = use_case.execute(template, answers, body=body)
            try:
                metadata = self._metadata(path, self.repo.find_by_location(str(path)))
            except Exception as exc:
                return CommandResult(success=False, error=f"note saved at {path}, but metadata failed: {exc}")
        except (OSError, ValueError, RuntimeError) as exc:
            return CommandResult(success=False, error=str(exc))
        if source is not None:
            try:
                metadata["trashed_source"] = str(self._trash_source(source))
            except (OSError, ValueError, RuntimeError) as exc:
                metadata["errors"] = [str(exc)]
        return CommandResult(success=True, output=f"Created {path}", metadata=metadata, warnings=use_case.warnings)

    def _inputs(self) -> tuple[str | None, str | None, Path | None]:
        if self.params.source is None:
            return self.params.title, self.params.body, None
        if self.params.body is not None:
            raise ValueError("body and source are mutually exclusive")
        inbox = self.vault_root / "inbox"
        resolved_inbox = inbox.resolve()
        source = self.params.source.expanduser().resolve()
        if (
            not resolved_inbox.is_relative_to(self.vault_root)
            or not source.is_relative_to(resolved_inbox)
            or source.suffix != ".md"
            or not source.is_file()
        ):
            raise ValueError(f"--source must be a Markdown file inside {inbox}")
        body = source.read_text(encoding="utf-8")
        body = re.sub(r"\A---\n[\s\S]*?\n---\n", "", body, count=1)
        return self.params.title if self.params.title is not None else source.stem, body, source

    def _answers(self, template: Any, title: str) -> dict[str, Any]:
        answers: dict[str, Any] = {"title": title}
        tags: list[str] = list(getattr(template, "default_tags", None) or [])
        if self.params.tags is not None or tags:
            for raw_tag in (self.params.tags or "").split(","):
                tag = raw_tag.strip().removeprefix("#").lower()
                if not tag:
                    continue
                if not re.fullmatch(r"[\w-]+(/[\w-]+)*", tag) or re.fullmatch(r"[\d/]+", tag):
                    raise ValueError(f"invalid tag '{tag}': use letters, digits, '-', '_', and '/' for nesting")
                owner = next(
                    (
                        name
                        for name, other in self.templates.items()
                        if other is not template and tag in (getattr(other, "default_tags", None) or [])
                    ),
                    None,
                )
                if owner is not None:
                    raise ValueError(f"tag '{tag}' is reserved for the {owner} template")
                if tag not in tags:
                    tags.append(tag)
            answers["tags"] = ",".join(tags)
        for q in template.questions():
            if q.key == "tags" and "tags" in answers:
                continue
            if q.key in self.extra_answers:
                answers[q.key] = self.extra_answers[q.key]
            elif q.default is not None:
                answers[q.key] = q.default
            elif q.required:
                raise ValueError(f"Missing required answer: {q.key}")
        return answers

    def _metadata(self, path: Path, zettel: Zettel) -> dict[str, Any]:
        path = path.resolve()
        relative_path = path.relative_to(self.vault_root).as_posix()
        return {
            "id": str(zettel.id),
            "type": zettel.type,
            "title": zettel.title,
            "tags": zettel.tags or [],
            "path": str(path),
            "relative_path": relative_path,
            "wikilink": f"[[{relative_path[:-3]}|{zettel.title}]]",
        }

    def _trash_source(self, source: Path) -> Path:
        trash = (self.vault_root / ".trash").resolve()
        if not trash.is_relative_to(self.vault_root):
            raise ValueError(f"Trash directory must be inside {self.vault_root}")
        trash.mkdir(exist_ok=True)
        for index in range(MAX_TRASH_ATTEMPTS):
            name = f"{source.stem} {index}{source.suffix}" if index else source.name
            destination = trash / name
            try:
                os.link(source, destination)
            except FileExistsError:
                continue
            try:
                source.unlink()
            except OSError as exc:
                raise OSError(f"Could not remove {source} after linking to {destination}: {exc}") from exc
            return destination
        raise FileExistsError(f"No available trash destination for {source} after {MAX_TRASH_ATTEMPTS} attempts")
