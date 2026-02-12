import logging
from io import StringIO
from logging import LogRecord

import pytest
from rich.console import Console

from buvis.pybase.adapters.console.capturing_rich_handler import CapturingRichHandler


@pytest.fixture
def console_stream() -> StringIO:
    return StringIO()


@pytest.fixture
def console(console_stream: StringIO) -> Console:
    return Console(file=console_stream, force_terminal=True, color_system=None, width=80)


@pytest.fixture
def log_record() -> LogRecord:
    return LogRecord(__name__, logging.INFO, __file__, 1, "fixture message", args=(), exc_info=None)


def test_init_stores_console(console: Console) -> None:
    handler = CapturingRichHandler(console)
    assert handler.console is console


def test_emit_calls_format_render_and_print_in_order(
    monkeypatch: pytest.MonkeyPatch, console: Console, log_record: LogRecord
) -> None:
    handler = CapturingRichHandler(console)
    calls: list[str] = []

    def fake_format(record: LogRecord) -> str:
        calls.append("format")
        assert record is log_record
        return "formatted message"

    def fake_render_message(record: LogRecord, message: str) -> str:
        calls.append("render_message")
        assert record is log_record
        assert message == "formatted message"
        return "message renderable"

    def fake_render(record: LogRecord, traceback: object, message_renderable: str) -> str:
        calls.append("render")
        assert record is log_record
        assert traceback is None
        assert message_renderable == "message renderable"
        return "rendered"

    def fake_print(rendered: str) -> None:
        calls.append("print")
        assert rendered == "rendered"

    monkeypatch.setattr(handler, "format", fake_format, raising=True)
    monkeypatch.setattr(handler, "render_message", fake_render_message, raising=True)
    monkeypatch.setattr(handler, "render", fake_render, raising=True)
    monkeypatch.setattr(console, "print", fake_print, raising=True)

    handler.emit(log_record)

    assert calls == ["format", "render_message", "render", "print"]


def test_emit_outputs_to_console(console_stream: StringIO, console: Console, log_record: LogRecord) -> None:
    handler = CapturingRichHandler(console, show_time=False, show_path=False)
    handler.emit(log_record)
    assert "fixture message" in console_stream.getvalue()


def test_handler_works_with_logging(console_stream: StringIO, console: Console) -> None:
    handler = CapturingRichHandler(console, show_time=False, show_path=False)
    logger = logging.getLogger("buvis.pybase.adapters.console.tests")
    logger.setLevel(logging.DEBUG)
    original_propagate = logger.propagate
    logger.propagate = False
    logger.addHandler(handler)
    try:
        logger.info("logging module message")
    finally:
        logger.removeHandler(handler)
        logger.propagate = original_propagate

    assert "logging module message" in console_stream.getvalue()
