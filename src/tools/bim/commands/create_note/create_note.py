from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from buvis.pybase.result import CommandResult
from buvis.pybase.zettel.application.use_cases.create_zettel_use_case import CreateZettelUseCase
from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase

from bim.shared.article_archive import archive_original, archive_path, archive_text
from bim.shared.vault_links import append_daily_log, contact_names, daily_log_entry, link_contacts

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
    from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository

    from bim.params.create_note import CreateNoteParams

MAX_TRASH_ATTEMPTS = 1000


@dataclass
class _Plan:
    """Everything the create needs once the inputs are validated."""

    template: Any
    title: str
    answers: dict[str, Any]
    body: str | None
    source: Path | None
    now: datetime
    linked: list[str] = field(default_factory=list)
    archive: Path | None = None
    original: str = ""

    @property
    def web(self) -> str:
        return str(self.answers.get("web") or "").strip()


class CommandCreateNote:
    def __init__(  # noqa: PLR0913, PLR0917 — preserve the shared composition contract
        self,
        params: CreateNoteParams,
        path_zettelkasten: Path,
        repo: ZettelRepository,
        templates: dict[str, Any],
        hook_runner: Any,
        formatter: ZettelFormatter,
        *,
        path_daily: Path | None = None,
        path_articles: Path | None = None,
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
        self.path_daily = path_daily
        self.path_articles = path_articles
        self.extra_answers = self.params.extra_answers or {}

    def execute(self) -> CommandResult:
        try:
            return self._execute()
        except (OSError, ValueError, RuntimeError) as exc:
            return CommandResult(success=False, error=str(exc))

    def _execute(self) -> CommandResult:
        title, body, source = self._inputs()
        if self.params.zettel_type is None or title is None:
            return CommandResult(success=False, error="zettel_type and title are required")
        if self.params.zettel_type not in self.templates:
            return CommandResult(success=False, error=f"Unknown template: {self.params.zettel_type}")
        template = self.templates[self.params.zettel_type]
        now = datetime.now().astimezone().replace(microsecond=0)
        plan = _Plan(template, title, self._answers(template, title), body, source, now)
        if template.name == "article":
            plan.original, plan.body = self._article_inputs(body)
            plan.archive = archive_path(self._articles_root(), title, now)
            plan.answers["archive_link"] = f"[{title}](file://{quote(str(plan.archive), safe='/')})"
        plan.body, plan.linked = self._link_contacts(template, plan.body)
        use_case = CreateZettelUseCase(self.path_zettelkasten, self.repo, hook_runner=self.hook_runner)
        if self.params.dry_run:
            return self._dry_run(use_case, plan)
        return self._create(use_case, plan)

    def _dry_run(self, use_case: CreateZettelUseCase, plan: _Plan) -> CommandResult:
        path, zettel = use_case.prepare(plan.template, plan.answers, body=plan.body)
        metadata = self._metadata(path, zettel)
        metadata.update(dry_run=True, content=PrintZettelUseCase(self.formatter).execute(zettel.get_data()))
        if plan.archive is not None:
            metadata["archive"] = {
                "path": str(plan.archive),
                "content": archive_text(plan.title, plan.original, plan.web),
            }
        if plan.linked:
            metadata["linked_contacts"] = plan.linked
        if self.params.daily_log and self.path_daily is not None:
            entry = daily_log_entry((zettel.date or plan.now).astimezone(), metadata["wikilink"])
            metadata["daily_log"] = {"status": "not written (dry run)", "entry": entry}
        return CommandResult(success=True, metadata=metadata)

    def _create(self, use_case: CreateZettelUseCase, plan: _Plan) -> CommandResult:
        if plan.archive is not None:
            archive_original(self._articles_root(), plan.title, plan.original, plan.web, plan.now)
        try:
            path = use_case.execute(plan.template, plan.answers, body=plan.body)
        except (OSError, ValueError, RuntimeError):
            if plan.archive is not None:
                plan.archive.unlink(missing_ok=True)
            raise
        try:
            saved = self.repo.find_by_location(str(path))
            metadata = self._metadata(path, saved)
        except Exception as exc:
            return CommandResult(success=False, error=f"note saved at {path}, but metadata failed: {exc}")
        if plan.archive is not None:
            metadata["archive"] = {"path": str(plan.archive)}
        if plan.linked:
            metadata["linked_contacts"] = plan.linked
        # The parsed date comes back in UTC; the daily note and its log line live in local time.
        self._after_save(metadata, (saved.date or plan.now).astimezone(), plan.source)
        return CommandResult(success=True, output=f"Created {path}", metadata=metadata, warnings=use_case.warnings)

    def _after_save(self, metadata: dict[str, Any], now: datetime, source: Path | None) -> None:
        """Daily log and source cleanup: the note exists, so problems become ``errors``, not failures."""
        errors: list[str] = []
        if self.params.daily_log and self.path_daily is not None:
            try:
                metadata["daily_log"] = append_daily_log(self.path_daily, now, metadata["wikilink"])
            except OSError as exc:
                errors.append(f"cannot add the daily note log entry: {exc}")
        if source is not None:
            try:
                metadata["trashed_source"] = str(self._trash_source(source))
            except (OSError, ValueError, RuntimeError) as exc:
                errors.append(str(exc))
        if errors:
            metadata["errors"] = errors

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

    def _article_inputs(self, body: str | None) -> tuple[str, str]:
        """Return ``(original, summary)``: the original is archived, the summary becomes the note body."""
        summary = _clean(self.params.summary or "")
        if not summary:
            raise ValueError("article needs --summary-file with the core facts")
        original = _clean(body or "")
        if not original:
            raise ValueError("article needs the original text: pass --body-file or --source")
        return original, summary

    def _articles_root(self) -> Path:
        if self.path_articles is None:
            raise ValueError("path_articles is not configured")
        return self.path_articles

    def _link_contacts(self, template: Any, body: str | None) -> tuple[str | None, list[str]]:
        if not body or not self.params.link_contacts or getattr(template, "folder", "") == "contact":
            return body, []
        names = contact_names(self.path_zettelkasten / "contact")
        return link_contacts(body, names, f"{self.path_zettelkasten.name}/contact")

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
                if tag in tags:
                    continue
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


def _clean(text: str) -> str:
    """Normalise line endings, drop leading blank lines and trailing whitespace."""
    return re.sub(r"\A(?:[ \t]*\n)+", "", text.replace("\r\n", "\n")).rstrip()
