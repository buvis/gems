from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import suppress
from itertools import chain
from pathlib import Path
from typing import Any

from buvis.pybase.formatting import StringOperator
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelWriter
from buvis.pybase.zettel.domain.services.zettel_factory import ZettelFactory
from buvis.pybase.zettel.domain.templates import HookRunner, ZettelTemplate
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


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
        zettel = _build(template, answers, body)
        candidates = self._candidate_paths(template, zettel)
        base_path = next(candidates)
        for path in chain([base_path], candidates):
            if not path.exists():
                zettel.get_data().file_path = str(path)
                return path, zettel
        raise FileExistsError(f"Zettel already exists: {base_path}")

    def _candidate_paths(self, template: ZettelTemplate, zettel: Zettel) -> Iterator[Path]:
        """Yield the base path, then the 60-99 suffixed id paths, computing each one lazily."""
        base = zettel.id
        yield self._path_for(template, zettel)
        if not _retries_on_collision(template) or base is None or len(str(base)) != 14:
            return
        for seconds in range(60, 100):
            zettel.id = _suffixed_id(base, seconds)
            yield self._path_for(template, zettel)

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
        zettel = _build(template, answers, body)
        candidates = self._candidate_paths(template, zettel)
        base_path = next(candidates)
        for path in chain([base_path], candidates):
            if path.exists():
                continue
            zettel.get_data().file_path = str(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
            except FileExistsError:
                continue
            break
        else:
            raise FileExistsError(f"Zettel already exists: {base_path}") from None
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


def _suffixed_id(base_id: int, seconds: int) -> int:
    """Return base_id with its last two digits replaced by ``seconds`` (60-99)."""
    return int(f"{str(base_id)[:12]}{seconds:02d}")


def _build(template: ZettelTemplate, answers: dict[str, Any], body: str | None) -> Zettel:
    data = template.build_data(answers)
    _append_body(data, template, answers, body)
    return ZettelFactory.create(Zettel(data))


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
