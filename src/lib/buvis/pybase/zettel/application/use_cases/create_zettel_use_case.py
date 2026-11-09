from __future__ import annotations

import os
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from buvis.pybase.formatting import StringOperator
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelWriter
from buvis.pybase.zettel.domain.services.zettel_factory import ZettelFactory
from buvis.pybase.zettel.domain.templates import HookRunner, ZettelTemplate
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

MAX_ID_ATTEMPTS = 5


class CreateZettelUseCase:
    def __init__(
        self,
        zettelkasten_path: Path,
        writer: ZettelWriter,
        hook_runner: HookRunner | None = None,
    ) -> None:
        self.zettelkasten_path = zettelkasten_path
        self.writer = writer
        self.hook_runner = hook_runner
        self.warnings: list[str] = []
        """Warnings the hooks reported during the last ``execute``."""

    def prepare(
        self, template: ZettelTemplate, answers: dict[str, Any], *, body: str | None = None
    ) -> tuple[Path, Zettel]:
        """Build a note and choose its path without saving or running hooks."""
        path, zettel, _ = self._prepare(template, answers, body, MAX_ID_ATTEMPTS)
        return path, zettel

    def _prepare(
        self, template: ZettelTemplate, answers: dict[str, Any], body: str | None, remaining_attempts: int
    ) -> tuple[Path, Zettel, int]:
        while True:
            remaining_attempts -= 1
            data = template.build_data(answers)
            _append_body(data, template, answers, body)
            zettel = ZettelFactory.create(Zettel(data))
            path = self._path_for(template, zettel)
            if not path.exists():
                zettel.get_data().file_path = str(path)
                return path, zettel, remaining_attempts
            if not _retries_on_collision(template) or not remaining_attempts:
                raise FileExistsError(f"Zettel already exists: {path}")
            time.sleep(1)

    def _path_for(self, template: ZettelTemplate, zettel: Zettel) -> Path:
        if getattr(template, "file_stem", "id") == "slug":
            stem = StringOperator.slugify(zettel.title or "")
            if not stem:
                raise ValueError(
                    f"title '{zettel.title}' gives an empty slug; use a title with Latin letters or digits"
                )
        else:
            stem = str(zettel.id)
        path = (self.zettelkasten_path / (getattr(template, "folder", "") or "") / f"{stem}.md").resolve()
        if not path.is_relative_to(self.zettelkasten_path.resolve()):
            raise ValueError(f"Note destination must be inside {self.zettelkasten_path}")
        return path

    def execute(self, template: ZettelTemplate, answers: dict[str, Any], *, body: str | None = None) -> Path:
        self.warnings = []
        remaining_attempts = MAX_ID_ATTEMPTS
        while True:
            path, zettel, remaining_attempts = self._prepare(template, answers, body, remaining_attempts)
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
            except FileExistsError:
                if not _retries_on_collision(template) or not remaining_attempts:
                    raise FileExistsError(f"Zettel already exists: {path}") from None
                time.sleep(1)
                continue
            break
        reservation = None
        saved = False
        try:
            try:
                reservation = os.fstat(descriptor)
            finally:
                os.close(descriptor)
            if self.hook_runner:
                try:
                    reported = self.hook_runner(template.hooks(), zettel.get_data(), self.zettelkasten_path)
                except Exception as exc:
                    raise RuntimeError(f"hook failed: {exc}") from exc
                self.warnings = list(reported or [])
            self.writer.save(zettel)
            saved = True
        finally:
            if not saved and reservation is not None:
                with suppress(FileNotFoundError):
                    current = path.stat()
                    if (current.st_dev, current.st_ino) == (reservation.st_dev, reservation.st_ino):
                        path.unlink()
        return path


def _retries_on_collision(template: ZettelTemplate) -> bool:
    return getattr(template, "file_stem", "id") != "slug"


def _append_body(data: ZettelData, template: ZettelTemplate, answers: dict[str, Any], body: str | None) -> None:
    if not body or not body.strip():
        return
    lines = body.replace("\r\n", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    content = "\n".join(lines).rstrip()
    if not data.sections:
        data.sections = [(f"# {answers.get('title', '')}", content)]
        return
    heading = getattr(template, "body_section", None)
    index = next((i for i, (name, _) in enumerate(data.sections) if name == heading), 0)
    name, existing = data.sections[index]
    existing = existing.rstrip("\r\n")
    data.sections[index] = (name, f"{existing}\n\n{content}" if existing else content)
