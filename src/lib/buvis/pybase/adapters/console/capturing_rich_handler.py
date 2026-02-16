from __future__ import annotations

from logging import LogRecord
from typing import Any

from rich.console import Console
from rich.logging import RichHandler


class CapturingRichHandler(RichHandler):
    def __init__(self, console: Console, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.console = console

    def emit(self, record: LogRecord) -> None:
        message = self.format(record)
        message_renderable = self.render_message(record, message)
        rendered = self.render(
            record=record,
            traceback=None,
            message_renderable=message_renderable,
        )
        self.console.print(rendered)
