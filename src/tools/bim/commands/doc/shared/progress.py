"""Progress reporting hook for the doc ingest pipeline.

The pipeline runs three slow boundary calls (OCR, classifier LLM, extractor
LLM) that can take several seconds each. In a TTY-attached interactive run
the user wants to know which one is in flight; in a batch run (cron, watcher,
piped output) we stay silent.

The pipeline does not depend on the console adapter directly. It accepts an
optional :class:`ProgressReporter` and calls ``.stage(message)`` before each
slow step. The CLI handler picks the concrete reporter:

- :class:`SpinnerProgressReporter` — wraps ``console.status()`` so each
  ``.stage()`` updates the Rich spinner label in place.
- :class:`NoOpProgressReporter` — swallows everything; the default and the
  one used by tests.

Both reporters are context managers so the CLI can use ``with reporter:`` to
cover spinner start/stop. The pipeline itself only needs ``.stage()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from types import TracebackType

    from buvis.pybase.adapters.console.console import ConsoleAdapter
    from rich.status import Status

__all__ = ["NoOpProgressReporter", "ProgressReporter", "SpinnerProgressReporter"]


class ProgressReporter(Protocol):
    """Receives stage notifications during a long-running pipeline run.

    Implementations are also context managers so the CLI handler can manage
    spinner lifetime with ``with reporter: ...``. The pipeline only calls
    ``.stage()``; lifetime is the caller's concern.
    """

    def stage(self, message: str) -> None: ...
    def __enter__(self) -> ProgressReporter: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...


class NoOpProgressReporter:
    """Default reporter. Drops every call. Used in tests and batch mode."""

    def stage(self, _message: str) -> None:
        return None

    def __enter__(self) -> NoOpProgressReporter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        return None


class SpinnerProgressReporter:
    """Rich-spinner reporter for interactive (TTY) runs.

    Wraps ``ConsoleAdapter.status()`` so each ``.stage(msg)`` updates the
    spinner label without printing a new line. Rich Status is itself a context
    manager; this class delegates ``__enter__``/``__exit__`` to it so the
    spinner appears on ``with reporter:`` and is torn down on exit.
    """

    def __init__(self, console_adapter: ConsoleAdapter) -> None:
        self._console = console_adapter
        self._status: Status | None = None

    def stage(self, message: str) -> None:
        if self._status is not None:
            self._status.update(f"{message}…")

    def __enter__(self) -> SpinnerProgressReporter:
        self._status = self._console.status("starting…")
        self._status.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._status is not None:
            self._status.__exit__(exc_type, exc_val, exc_tb)
            self._status = None
