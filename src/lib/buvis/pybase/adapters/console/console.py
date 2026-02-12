from __future__ import annotations

import io
import logging
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from rich.console import Capture
    from rich.status import Status

from rich.columns import Columns
from rich.console import Console, Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text

from buvis.pybase.adapters.console.capturing_rich_handler import CapturingRichHandler

CHECKMARK = "[bold green1]\u2714[/bold green1]"
WARNING = "[bold orange3]\u26a0[/bold orange3]"
CROSSMARK = "[bold indian_red]\u2718[/bold indian_red]"
STYLE_SUCCESS_MSG = "spring_green1"
STYLE_WARNING_MSG = "light_goldenrod3"
STYLE_FAILURE_MSG = "bold light_salmon3"


class ConsoleAdapter:
    """Rich console wrapper for styled terminal output.

    Example:
        >>> from buvis.pybase.adapters import ConsoleAdapter
        >>> console = ConsoleAdapter()
        >>> console.success("Operation completed")

    Checkmark, warning, and failure flows reuse the
    `CHECKMARK`, `WARNING`, and `CROSSMARK` markers together with
    `STYLE_SUCCESS_MSG`, `STYLE_WARNING_MSG`, and `STYLE_FAILURE_MSG`
    so decorated messages remain consistent.
    """

    def __init__(self: ConsoleAdapter) -> None:
        """Initialize the console adapter.

        On Windows wrap `sys.stdout.buffer` with UTF-8 so `CHECKMARK`,
        `WARNING`, and `CROSSMARK` glyphs render properly using their
        respective `STYLE_*_MSG` colors.
        """
        if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
            utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
            self.console = Console(file=utf8_stdout, log_path=False)
        else:
            self.console = Console(log_path=False)

    def format_success(self: ConsoleAdapter, message: str) -> str:
        """Return a green checkmark Rich markup string.

        Args:
            message (str): Text to format.

        Returns:
            str: Rich markup string with checkmark and green styling.
        """
        return f" {CHECKMARK} [{STYLE_SUCCESS_MSG}]{message}[/{STYLE_SUCCESS_MSG}]"

    def success(self: ConsoleAdapter, message: str) -> None:
        """Print a green checkmark status message.

        Args:
            message (str): Text to display.
        """
        self.console.print(self.format_success(message))

    def format_warning(self: ConsoleAdapter, message: str) -> str:
        """Return an orange warning symbol Rich markup string.

        Args:
            message (str): Text to format.

        Returns:
            str: Rich markup string with warning symbol and orange styling.
        """
        return f" {WARNING} [{STYLE_WARNING_MSG}]{message}[/{STYLE_WARNING_MSG}]"

    def warning(self: ConsoleAdapter, message: str) -> None:
        """Print an orange warning status message.

        Args:
            message (str): Text to display.
        """
        self.console.print(self.format_warning(message))

    def format_failure(self: ConsoleAdapter, message: str, details: str | None = None) -> str:
        """Return a red crossmark Rich markup string with optional details.

        Args:
            message (str): Text to format.
            details (str | None): Additional detail text to append.

        Returns:
            str: Rich markup string with crossmark and red styling.
        """
        formatted_message = f" {CROSSMARK} [{STYLE_FAILURE_MSG}]{message}[/{STYLE_FAILURE_MSG}]"

        if details:
            formatted_message += f" \n\n Details:\n\n {details}"

        return formatted_message

    def failure(self: ConsoleAdapter, message: str, details: str | None = None) -> None:
        """Print a red failure message, optionally including details.

        Args:
            message (str): Text to display.
            details (str | None): Additional information to display after the failure message.
        """
        self.console.print(self.format_failure(message, details))

    def panic(self: ConsoleAdapter, message: str, details: str | None = None) -> None:
        """Print a failure message and exit the program.

        Args:
            message (str): Text to display.
            details (str | None): Additional information to display after the failure message.

        Note:
            Terminates the program by calling `sys.exit()`.
        """
        self.failure(message, details)
        sys.exit()

    def status(self: ConsoleAdapter, message: str) -> Status:
        """Return a Rich Status context manager with arrow3 spinner.

        Args:
            message (str): Text to display while the status context is active.

        Returns:
            Status: Context manager for long-running operations.
        """
        return self.console.status(message, spinner="arrow3")

    def capture(self: ConsoleAdapter) -> Capture:
        """Return a Rich Capture context manager for console output.

        Returns:
            Capture: Context manager that captures console output.
        """
        return self.console.capture()

    def confirm(self: ConsoleAdapter, question: str) -> bool:
        """Prompt the user for confirmation via Rich Confirm.ask.

        Args:
            question (str): Prompt text presented to the user.

        Returns:
            bool: Result of the confirmation.
        """
        return Confirm.ask(question)

    def print(self: ConsoleAdapter, message: str, *, mode: str = "normal") -> None:
        """Render text through the console with optional rendering modes.

        Args:
            message (str): Content to print.
            mode (str): Rendering mode, one of ``normal``, ``raw``, or
                ``markdown_with_frontmatter``.
        """
        return self.console.print(_stylize_text(message, mode))

    def info(self: ConsoleAdapter, message: str) -> None:
        """Print dimmed informational text."""
        self.console.print(f"[dim]{message}[/dim]")

    def print_side_by_side(
        self: ConsoleAdapter,
        title_left: str,
        text_left: str,
        title_right: str,
        text_right: str,
        *,
        mode_left: str = "normal",
        mode_right: str = "normal",
    ) -> None:
        """Render two panels in a half-width, side-by-side layout where each panel
        uses half the console width to keep columns balanced.

        Args:
            title_left (str): Panel title for the left column.
            text_left (str): Content for the left column body.
            title_right (str): Panel title for the right column.
            text_right (str): Content for the right column body.
            mode_left (str): Rendering mode for the left column content.
            mode_right (str): Rendering mode for the right column content.

        Example:
            >>> console.print_side_by_side(
            ...     title_left="Config",
            ...     text_left="name: buvis\\n---\\n# details",
            ...     title_right="Result",
            ...     text_right="Success",
            ...     mode_left="markdown_with_frontmatter",
            ...     mode_right="raw",
            ... )
        """
        width = self.console.width // 2

        panel_left = Panel.fit(
            _stylize_text(text_left, mode_left),
            title=title_left,
            width=width,
        )
        panel_right = Panel.fit(
            _stylize_text(text_right, mode_right),
            title=title_right,
            width=width,
        )

        columns = Columns(
            [panel_left, panel_right],
            expand=True,
            equal=True,
            padding=(0, 1),
        )

        return self.console.print(columns)

    def nl(self: ConsoleAdapter) -> None:
        """Output an empty line to the console."""
        return self.console.out("")


def _stylize_text(text: str, mode: str) -> RenderableType:
    if mode == "raw":
        return Text(text)

    if mode == "markdown_with_frontmatter":
        return Group(*_stylize_text_md_frontmatter(text))

    return text


def _stylize_text_md_frontmatter(markdown_text: str) -> list[RenderableType]:
    yaml_content, _, markdown_content = markdown_text.partition("\n---\n")

    def highlight_yaml(yaml_text: str) -> list[RenderableType]:
        lines = yaml_text.split("\n")
        highlighted_lines: list[RenderableType] = []

        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                highlighted_line = Text()
                highlighted_line.append(key.strip(), style="#859900")
                highlighted_line.append(":", style="bold gray")
                highlighted_line.append(value, style="#b58900")
            else:
                highlighted_line = Text(line, style="#859900")

            highlighted_lines.append(highlighted_line)

        return highlighted_lines

    md = Markdown(markdown_content)
    output_lines: list[RenderableType] = [line for line in highlight_yaml(yaml_content) if str(line).rstrip() != "---"]
    output_lines.append(md)

    return output_lines


console = ConsoleAdapter()


@contextmanager
def logging_to_console(
    *,
    show_level: bool = True,
    show_time: bool = False,
    show_path: bool = False,
) -> Generator[None, None, None]:
    """Context manager that routes logging output through the Rich console.

    Temporarily adds a :class:`CapturingRichHandler` to the root logger, setting the
    logger level to ``INFO`` while the context is active and restoring the previous
    handler and level on exit.

    Args:
        show_level (bool): Include the log level in the captured output. Defaults to ``True``.
        show_time (bool): Include timestamps in the captured output. Defaults to ``False``.
        show_path (bool): Include the logger path in the captured output. Defaults to ``False``.

    Yields:
        None: Logging is redirected to the Rich console for the duration of the context.

    Example:
        >>> with logging_to_console():
        ...     logging.info("Hello Rich")
    """
    handler = CapturingRichHandler(
        console=console.console,
        show_level=show_level,
        show_time=show_time,
        show_path=show_path,
        rich_tracebacks=False,
        tracebacks_show_locals=False,
    )

    logger = logging.getLogger()
    logger.addHandler(handler)
    original_level = logger.level
    logger.setLevel(logging.INFO)

    try:
        yield
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
