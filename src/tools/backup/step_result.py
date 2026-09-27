from __future__ import annotations

from typing import NamedTuple


class ArchiveMeta(NamedTuple):
    """The archive facts a ``tar-archive`` run (or dry-run preview) produces."""

    out_path: str
    file_count: int
    total_bytes: int


class StepResult:
    """Structured outcome of one capability step.

    ``label`` names the instance, ``success`` is the verdict, and ``message`` is
    a human-readable line the CLI renders via ``console``. ``archive`` carries
    the produced/previewed archive facts, or ``None`` for a step that produces
    no archive.
    """

    def __init__(
        self: StepResult,
        label: str,
        success: bool,
        message: str = "",
        archive: ArchiveMeta | None = None,
    ) -> None:
        self.label = label
        self.success = success
        self.message = message
        self.archive = archive

    @property
    def out_path(self: StepResult) -> str | None:
        return self.archive.out_path if self.archive is not None else None

    @property
    def file_count(self: StepResult) -> int | None:
        return self.archive.file_count if self.archive is not None else None

    @property
    def total_bytes(self: StepResult) -> int | None:
        return self.archive.total_bytes if self.archive is not None else None
