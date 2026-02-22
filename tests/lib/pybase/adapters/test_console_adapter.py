import io
import logging
import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from buvis.pybase.adapters.console.capturing_rich_handler import CapturingRichHandler
from buvis.pybase.adapters.console.console import (
    ConsoleAdapter,
    _stylize_text,
    console,
    logging_to_console,
)
from buvis.pybase.result import CommandResult
from rich.columns import Columns
from rich.console import Group, Text
from rich.markdown import Markdown
from rich.status import Status


@pytest.fixture
def console_adapter() -> ConsoleAdapter:
    return ConsoleAdapter()


def test_format_success(console_adapter: ConsoleAdapter) -> None:
    message = "Success message"
    expected = " [bold green1]\u2714[/bold green1] [spring_green1]Success message[/spring_green1]"
    assert console_adapter.format_success(message) == expected


def test_format_warning(console_adapter: ConsoleAdapter) -> None:
    message = "Warning message"
    expected = " [bold orange3]\u26a0[/bold orange3] [light_goldenrod3]Warning message[/light_goldenrod3]"
    assert console_adapter.format_warning(message) == expected


def test_format_failure(console_adapter: ConsoleAdapter) -> None:
    message = "Failure message"
    details = "Failure details"
    expected = " [bold indian_red]\u2718[/bold indian_red] [bold light_salmon3]Failure message[/bold light_salmon3]"
    assert console_adapter.format_failure(message) == expected

    expected_with_details = (
        " [bold indian_red]\u2718[/bold indian_red] [bold light_salmon3]Failure message[/bold light_salmon3] \n\n "
        "Details:\n\n Failure details"
    )
    assert console_adapter.format_failure(message, details) == expected_with_details


def test_success(capsys: Any, console_adapter: ConsoleAdapter) -> None:
    message = "Success message"
    console_adapter.success(message)
    captured = capsys.readouterr()
    assert captured.out.strip() == f"✔ {message}"


def test_warning(capsys: Any, console_adapter: ConsoleAdapter) -> None:
    message = "Warning message"
    console_adapter.warning(message)
    captured = capsys.readouterr()
    assert captured.out.strip() == f"⚠ {message}"


def test_failure(capsys: Any, console_adapter: ConsoleAdapter) -> None:
    message = "Failure message"
    details = "Failure details"
    console_adapter.failure(message, details)
    captured = capsys.readouterr()
    assert captured.out.strip() == f"✘ {message} \n\n Details:\n\n {details}"


def test_panic(capsys: Any, console_adapter: ConsoleAdapter) -> None:
    message = "Panic message"
    details = "Panic details"
    with pytest.raises(SystemExit):
        console_adapter.panic(message, details)
    captured = capsys.readouterr()
    assert captured.out.strip() == f"✘ {message} \n\n Details:\n\n {details}"


def test_status(console_adapter: ConsoleAdapter) -> None:
    message = "Status message"
    status = console_adapter.status(message)
    assert isinstance(status, Status)
    assert status.status == message


def test_print(capsys: Any, console_adapter: ConsoleAdapter) -> None:
    message = "Print message"
    console_adapter.print(message)
    captured = capsys.readouterr()
    assert captured.out.strip() == message


def test_nl(capsys: Any, console_adapter: ConsoleAdapter) -> None:
    console_adapter.nl()
    captured = capsys.readouterr()
    assert captured.out.strip() == ""


def test_console_instance() -> None:
    assert isinstance(console, ConsoleAdapter)


def test_windows_stdout_wrapping() -> None:
    """Test Windows platform wraps stdout with UTF-8 TextIOWrapper."""
    import importlib

    console_module = importlib.import_module("buvis.pybase.adapters.console.console")

    class DummyStdout:
        def __init__(self) -> None:
            self.buffer = io.BytesIO()

    class DummyConsole:
        def __init__(self, file: io.TextIOWrapper | None = None, log_path: bool = True) -> None:
            self.file = file
            self.log_path = log_path

    with (
        patch.object(sys, "platform", "win32"),
        patch.object(sys, "stdout", DummyStdout()),
        patch.object(console_module, "Console", DummyConsole),
    ):
        adapter = ConsoleAdapter()

        assert isinstance(adapter.console, DummyConsole)
        assert isinstance(adapter.console.file, io.TextIOWrapper)
        assert adapter.console.log_path is False


def test_capture_returns_context_manager(console_adapter: ConsoleAdapter) -> None:
    with console_adapter.capture() as capture:
        console_adapter.print("captured output")

    assert "captured output" in capture.get()


def test_confirm_returns_mocked_answer(console_adapter: ConsoleAdapter) -> None:
    """Test confirm method returns mocked answers."""
    import importlib

    console_module = importlib.import_module("buvis.pybase.adapters.console.console")
    answers = iter([True, False])

    with patch.object(console_module.Confirm, "ask", side_effect=lambda _: next(answers)):
        assert console_adapter.confirm("Proceed?")
        assert not console_adapter.confirm("Proceed?")


def test_print_side_by_side_renders_columns(console_adapter: ConsoleAdapter, monkeypatch) -> None:
    mock_print = Mock()
    monkeypatch.setattr(console_adapter.console, "print", mock_print)

    console_adapter.print_side_by_side(
        title_left="Left",
        text_left="left text",
        title_right="Right",
        text_right="right text",
    )

    mock_print.assert_called_once()
    printed_columns = mock_print.call_args[0][0]
    assert isinstance(printed_columns, Columns)
    assert len(printed_columns.renderables) == 2


def test_stylize_text_raw_returns_text() -> None:
    result = _stylize_text("raw text", "raw")
    assert isinstance(result, Text)
    assert result.plain == "raw text"


def test_stylize_text_markdown_with_frontmatter_returns_group() -> None:
    markdown_input = "key: value\n---\n# Title\nBody text"

    result = _stylize_text(markdown_input, "markdown_with_frontmatter")

    assert isinstance(result, Group)
    assert isinstance(result.renderables[0], Text)
    assert isinstance(result.renderables[-1], Markdown)


def test_logging_to_console_manages_handler_and_level(monkeypatch) -> None:
    logger = logging.getLogger()
    previous_level = logger.level
    logger.setLevel(logging.WARNING)

    initial_handler_ids = {id(handler) for handler in logger.handlers}
    mock_console_print = Mock()
    monkeypatch.setattr(console, "print", mock_console_print)

    capturing_handler: CapturingRichHandler | None = None

    with logging_to_console():
        logging.getLogger().info("test log")
        assert logger.level == logging.INFO
        capturing_handler = next(
            (
                handler
                for handler in logger.handlers
                if isinstance(handler, CapturingRichHandler) and id(handler) not in initial_handler_ids
            ),
            None,
        )
        assert capturing_handler is not None

    assert logger.level == logging.WARNING
    assert capturing_handler not in logger.handlers

    logger.setLevel(previous_level)


class TestReportResult:
    def test_success_with_output(self, capsys: Any, console_adapter: ConsoleAdapter) -> None:
        result = CommandResult(success=True, output="Created note")
        console_adapter.report_result(result)
        captured = capsys.readouterr()
        assert "Created note" in captured.out

    def test_success_with_override_msg(self, capsys: Any, console_adapter: ConsoleAdapter) -> None:
        result = CommandResult(success=True, output="original")
        console_adapter.report_result(result, success_msg="override")
        captured = capsys.readouterr()
        assert "override" in captured.out
        assert "original" not in captured.out

    def test_success_no_output_prints_nothing(self, capsys: Any, console_adapter: ConsoleAdapter) -> None:
        result = CommandResult(success=True)
        console_adapter.report_result(result)
        captured = capsys.readouterr()
        assert captured.out.strip() == ""

    def test_failure_with_error(self, capsys: Any, console_adapter: ConsoleAdapter) -> None:
        result = CommandResult(success=False, error="Disk full")
        console_adapter.report_result(result)
        captured = capsys.readouterr()
        assert "Disk full" in captured.out

    def test_failure_fallback_msg(self, capsys: Any, console_adapter: ConsoleAdapter) -> None:
        result = CommandResult(success=False)
        console_adapter.report_result(result, failure_msg="Custom fail")
        captured = capsys.readouterr()
        assert "Custom fail" in captured.out

    def test_warnings_printed(self, capsys: Any, console_adapter: ConsoleAdapter) -> None:
        result = CommandResult(success=True, output="ok", warnings=["w1", "w2"])
        console_adapter.report_result(result)
        captured = capsys.readouterr()
        assert "w1" in captured.out
        assert "w2" in captured.out

    def test_on_success_callback(self, console_adapter: ConsoleAdapter) -> None:
        result = CommandResult(success=True, metadata={"count": 3})
        callback = Mock()
        console_adapter.report_result(result, on_success=callback)
        callback.assert_called_once_with(result)

    def test_on_failure_callback(self, console_adapter: ConsoleAdapter) -> None:
        result = CommandResult(success=False, error="err")
        callback = Mock()
        console_adapter.report_result(result, on_failure=callback)
        callback.assert_called_once_with(result)


class TestRequireImport:
    def test_panics_with_install_hint(self, console_adapter: ConsoleAdapter) -> None:
        with pytest.raises(SystemExit):
            console_adapter.require_import("muc")

    def test_message_format(self, capsys: Any, console_adapter: ConsoleAdapter) -> None:
        with pytest.raises(SystemExit):
            console_adapter.require_import("muc")
        captured = capsys.readouterr()
        assert "muc requires the 'muc' extra" in captured.out
        assert "uv tool install buvis-gems" in captured.out
        assert "muc" in captured.out

    def test_custom_tool_name(self, capsys: Any, console_adapter: ConsoleAdapter) -> None:
        with pytest.raises(SystemExit):
            console_adapter.require_import("hello-world", tool_name="hello_world")
        captured = capsys.readouterr()
        assert "hello_world requires the 'hello-world' extra" in captured.out


class TestValidatePath:
    def test_valid_dir_passes(self, console_adapter: ConsoleAdapter, tmp_path: Path) -> None:
        console_adapter.validate_path(tmp_path)  # should not raise

    def test_invalid_dir_panics(self, console_adapter: ConsoleAdapter, tmp_path: Path) -> None:
        bad = tmp_path / "nonexistent"
        with pytest.raises(SystemExit):
            console_adapter.validate_path(bad)

    def test_invalid_dir_message(self, capsys: Any, console_adapter: ConsoleAdapter, tmp_path: Path) -> None:
        bad = tmp_path / "nonexistent"
        with pytest.raises(SystemExit):
            console_adapter.validate_path(bad)
        captured = capsys.readouterr()
        assert "isn't a directory" in captured.out

    def test_valid_file_passes(self, console_adapter: ConsoleAdapter, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("x")
        console_adapter.validate_path(f, kind="file")

    def test_invalid_file_panics(self, capsys: Any, console_adapter: ConsoleAdapter, tmp_path: Path) -> None:
        bad = tmp_path / "missing.txt"
        with pytest.raises(SystemExit):
            console_adapter.validate_path(bad, kind="file")
        captured = capsys.readouterr()
        assert "doesn't exist" in captured.out

    def test_custom_label(self, capsys: Any, console_adapter: ConsoleAdapter, tmp_path: Path) -> None:
        bad = tmp_path / "nope"
        with pytest.raises(SystemExit):
            console_adapter.validate_path(bad, label="music library")
        captured = capsys.readouterr()
        assert "music library" in captured.out
