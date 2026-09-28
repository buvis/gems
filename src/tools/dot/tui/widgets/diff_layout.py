from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dot.tui.patch import Hunk

__all__ = ["DiffLayout", "VisibleRegion"]


@dataclass(frozen=True, slots=True)
class VisibleRegion:
    """A vertical span the renderer should keep in view.

    Attributes:
        y: Zero-based rendered line index the viewport should reveal.
        height: Number of rendered lines the span covers (always at least 1).
    """

    y: int
    height: int


@dataclass(frozen=True, slots=True)
class DiffLayout:
    """Pure coordinate math for the diff pane, independent of any TUI.

    The diff pane renders, top to bottom: the file-header lines (everything
    before the first ``@@`` hunk header), then for each hunk one header line
    followed by its content lines. ``DiffLayout`` owns the arithmetic that maps
    a hunk (and a line within it) to a rendered line index, clamps indices to
    valid ranges, and decides which region the renderer should scroll into view.

    It holds only plain data — the file-header line count and the per-hunk
    content-line counts — so every historical scroll/offset edge case is
    testable without instantiating a Textual widget.

    Attributes:
        file_header_lines: Rendered lines before the first hunk header. Zero for
            a headerless diff (one whose text starts at an ``@@`` line).
        hunk_line_counts: Content-line count of each hunk, in render order. Its
            length is the number of hunks.
    """

    file_header_lines: int
    hunk_line_counts: tuple[int, ...]

    @classmethod
    def from_diff(cls, diff_text: str, hunks: Sequence[Hunk]) -> DiffLayout:
        """Build a layout from raw diff text and its parsed hunks.

        Args:
            diff_text: The raw unified-diff text as rendered.
            hunks: The hunks parsed from ``diff_text`` (see
                :func:`dot.tui.patch.parse_diff`), in render order.

        Returns:
            A layout describing the rendered geometry of that diff.
        """
        return cls(
            file_header_lines=_file_header_line_count(diff_text),
            hunk_line_counts=tuple(len(hunk.lines) for hunk in hunks),
        )

    @property
    def hunk_count(self) -> int:
        """Number of hunks in the diff."""
        return len(self.hunk_line_counts)

    def offset_of(self, hunk_index: int) -> int:
        """Rendered line index of a hunk's header.

        The offset is the file-header line count plus, for each preceding hunk,
        one header line and its content lines. A headerless single hunk is at
        offset ``0``.

        Args:
            hunk_index: Zero-based hunk index. Must be in ``range(hunk_count)``.

        Returns:
            The zero-based rendered line index of that hunk's header.

        Raises:
            IndexError: If ``hunk_index`` is out of range.
        """
        if not 0 <= hunk_index < self.hunk_count:
            msg = f"hunk_index {hunk_index} out of range for {self.hunk_count} hunks"
            raise IndexError(msg)
        offset = self.file_header_lines
        for i in range(hunk_index):
            offset += 1 + self.hunk_line_counts[i]  # header + content lines
        return offset

    def clamp(self, index: int) -> int:
        """Clamp a hunk index to the valid ``[0, hunk_count - 1]`` range.

        Returns ``0`` when there are no hunks, so callers can clamp
        unconditionally.

        Args:
            index: A candidate hunk index (may be negative or too large).

        Returns:
            The nearest in-range hunk index, or ``0`` when there are no hunks.
        """
        if self.hunk_count == 0:
            return 0
        return max(0, min(index, self.hunk_count - 1))

    def max_line_index(self, hunk_index: int) -> int:
        """Highest valid content-line index within a hunk.

        Returns ``0`` for an empty hunk (no content lines), matching the widget's
        historical clamp behaviour where a cursor cannot leave line ``0``.

        Args:
            hunk_index: Zero-based hunk index. Must be in ``range(hunk_count)``.

        Returns:
            ``len(lines) - 1`` for a non-empty hunk, else ``0``.

        Raises:
            IndexError: If ``hunk_index`` is out of range.
        """
        if not 0 <= hunk_index < self.hunk_count:
            msg = f"hunk_index {hunk_index} out of range for {self.hunk_count} hunks"
            raise IndexError(msg)
        count = self.hunk_line_counts[hunk_index]
        return count - 1 if count else 0

    def clamp_line(self, hunk_index: int, line_index: int) -> int:
        """Clamp a content-line cursor to a hunk's valid range.

        Args:
            hunk_index: Zero-based hunk index. Must be in ``range(hunk_count)``.
            line_index: A candidate line index (may exceed the hunk length after
                the hunk shrank underneath a restored cursor).

        Returns:
            ``min(line_index, max_line_index)`` bounded below by ``0``.

        Raises:
            IndexError: If ``hunk_index`` is out of range.
        """
        return max(0, min(line_index, self.max_line_index(hunk_index)))

    def clamp_selected_lines(self, hunk_index: int, selected: frozenset[int]) -> frozenset[int]:
        """Drop selected line indices that no longer fit the hunk.

        Args:
            hunk_index: Zero-based hunk index. Must be in ``range(hunk_count)``.
            selected: Candidate selected content-line indices.

        Returns:
            The subset of ``selected`` that is ``<= max_line_index``.

        Raises:
            IndexError: If ``hunk_index`` is out of range.
        """
        max_line = self.max_line_index(hunk_index)
        return frozenset(i for i in selected if i <= max_line)

    def hunk_reveal(self, hunk_index: int) -> VisibleRegion:
        """Region to reveal when focusing a hunk.

        A hunk is normally revealed at its header. The last hunk of a
        *multi-hunk* diff is instead revealed at the bottom of its content, so a
        long final hunk is reachable by keyboard navigation alone. A single-hunk
        diff always targets the header, so opening a file lands at the top of its
        diff rather than the bottom.

        Args:
            hunk_index: Zero-based hunk index. Must be in ``range(hunk_count)``.

        Returns:
            The single-line region the renderer should scroll into view.

        Raises:
            IndexError: If ``hunk_index`` is out of range.
        """
        line = self.offset_of(hunk_index)
        is_last = hunk_index == self.hunk_count - 1
        if hunk_index > 0 and is_last:
            line += self.hunk_line_counts[hunk_index]
        return VisibleRegion(y=line, height=1)

    def line_reveal(self, hunk_index: int, line_index: int) -> VisibleRegion:
        """Region to reveal for a content-line cursor within a hunk.

        The target is the hunk header offset, plus one for the header line,
        plus the line cursor.

        Args:
            hunk_index: Zero-based hunk index. Must be in ``range(hunk_count)``.
            line_index: Zero-based content-line index within the hunk.

        Returns:
            The single-line region the renderer should scroll into view.

        Raises:
            IndexError: If ``hunk_index`` is out of range.
        """
        line = self.offset_of(hunk_index) + 1 + line_index
        return VisibleRegion(y=line, height=1)


def _file_header_line_count(diff_text: str) -> int:
    """Count rendered lines before the first hunk header.

    Args:
        diff_text: The raw unified-diff text as rendered.

    Returns:
        The number of lines preceding the first ``@@`` line; ``0`` for a
        headerless diff.
    """
    count = 0
    for line in diff_text.split("\n"):
        if line.startswith("@@"):
            break
        count += 1
    return count
