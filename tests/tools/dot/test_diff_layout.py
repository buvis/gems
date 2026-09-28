from __future__ import annotations

import pytest
from dot.tui.patch import parse_diff
from dot.tui.widgets.diff_layout import DiffLayout, VisibleRegion

# These tests exercise the pure diff coordinate math WITHOUT importing Textual.
# Each historical scroll/offset bug is pinned to the commit that fixed it.

MULTI_HUNK = """\
--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 line1
+added1
 line2
 line3
@@ -10,3 +11,4 @@
 line10
+added2
 line11
 line12"""

THREE_HUNKS = """\
--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 line1
+added1
 line2
 line3
@@ -10,3 +11,4 @@
 line10
+added2
 line11
 line12
@@ -20,3 +21,4 @@
 line20
+added3
 line21
 line22"""

SINGLE_HUNK = """\
--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 line1
+added1
 line2
 line3"""

HEADERLESS_HUNK = "@@ -1,2 +1,3 @@\n line1\n+added\n line2"


def _layout(diff_text: str) -> DiffLayout:
    return DiffLayout.from_diff(diff_text, parse_diff(diff_text))


class TestDiffLayoutConstruction:
    def test_no_textual_import(self) -> None:
        # Guard the pure-model invariant: the diff_layout source must not import
        # Textual. If a Textual dependency creeps in, this fails.
        from pathlib import Path

        import dot.tui.widgets.diff_layout as mod

        assert mod.__file__ is not None
        text = Path(mod.__file__).read_text(encoding="utf-8")
        assert "import textual" not in text
        assert "from textual" not in text

    def test_hunk_count_matches_parsed(self) -> None:
        assert _layout(MULTI_HUNK).hunk_count == 2
        assert _layout(THREE_HUNKS).hunk_count == 3
        assert _layout(SINGLE_HUNK).hunk_count == 1

    def test_empty_diff_has_no_hunks(self) -> None:
        assert _layout("").hunk_count == 0

    def test_file_header_lines_counted(self) -> None:
        # MULTI_HUNK: "--- a/file.py" and "+++ b/file.py" precede the first @@.
        assert _layout(MULTI_HUNK).file_header_lines == 2


class TestOffsetOf:
    def test_first_hunk_offset_is_file_header_count(self) -> None:
        layout = _layout(MULTI_HUNK)
        assert layout.offset_of(0) == 2

    def test_second_hunk_offset_adds_header_plus_content(self) -> None:
        # hunk 0 has 4 content lines -> hunk 1 header at 2 + (1 + 4) = 7.
        layout = _layout(MULTI_HUNK)
        assert layout.offset_of(1) == 7

    def test_third_hunk_offset_accumulates(self) -> None:
        # 2 header lines + 2*(1 + 4) = 12.
        layout = _layout(THREE_HUNKS)
        assert layout.offset_of(2) == 12

    def test_offset_out_of_range_raises(self) -> None:
        layout = _layout(SINGLE_HUNK)
        with pytest.raises(IndexError):
            layout.offset_of(1)
        with pytest.raises(IndexError):
            layout.offset_of(-1)


class TestHeaderlessDiff:
    """Regression for 66ada63: headerless diff offset calculation.

    A diff whose text starts at an ``@@`` line has zero file-header lines, so
    hunk 0 sits at rendered offset 0.
    """

    def test_headerless_first_hunk_at_zero(self) -> None:
        layout = _layout(HEADERLESS_HUNK)
        assert layout.file_header_lines == 0
        assert layout.hunk_count == 1
        assert layout.offset_of(0) == 0


class TestSingleHunkInitialLoad:
    """Regression for 9d06d0a: single-hunk diff stays anchored to its header.

    Opening a single-hunk file must land at the hunk header (top of the diff),
    NOT at the bottom of the hunk. hunk_reveal encodes the ``index > 0`` guard.
    """

    def test_single_hunk_reveal_targets_header_not_bottom(self) -> None:
        layout = _layout(SINGLE_HUNK)
        # 2 file-header lines -> header at y=2. Bottom would be 2 + 4 = 6.
        assert layout.hunk_reveal(0) == VisibleRegion(y=2, height=1)

    def test_headerless_single_hunk_reveal_at_zero(self) -> None:
        layout = _layout(HEADERLESS_HUNK)
        assert layout.hunk_reveal(0) == VisibleRegion(y=0, height=1)


class TestRevealPastLastHunk:
    """Regression for 24474a7: reveal content past the last hunk.

    The last hunk of a *multi-hunk* diff targets the bottom of its content so a
    long final hunk is reachable by keyboard alone.
    """

    def test_last_hunk_of_multi_targets_bottom(self) -> None:
        layout = _layout(MULTI_HUNK)
        # last hunk header at y=7, 4 content lines -> bottom target y=11.
        assert layout.hunk_reveal(1) == VisibleRegion(y=11, height=1)

    def test_non_last_hunk_targets_header(self) -> None:
        layout = _layout(THREE_HUNKS)
        # middle hunk header offset = 2 + (1 + 4) = 7, header only (not bottom).
        assert layout.hunk_reveal(1) == VisibleRegion(y=7, height=1)

    def test_last_hunk_of_three_targets_bottom(self) -> None:
        layout = _layout(THREE_HUNKS)
        # last header at y=12, +4 content -> y=16.
        assert layout.hunk_reveal(2) == VisibleRegion(y=16, height=1)


class TestClampBothEnds:
    """Regression for 73462f1 + 24474a7: clamp indices at both ends.

    Hunk-index clamping keeps navigation in range; line-index and selection
    clamping keep a restored cursor valid after the underlying hunk shrank.
    """

    def test_clamp_hunk_index_upper(self) -> None:
        layout = _layout(MULTI_HUNK)  # 2 hunks -> valid 0..1
        assert layout.clamp(5) == 1

    def test_clamp_hunk_index_lower(self) -> None:
        layout = _layout(MULTI_HUNK)
        assert layout.clamp(-3) == 0

    def test_clamp_hunk_index_in_range_unchanged(self) -> None:
        layout = _layout(THREE_HUNKS)
        assert layout.clamp(1) == 1

    def test_clamp_no_hunks_returns_zero(self) -> None:
        layout = _layout("")
        assert layout.clamp(4) == 0

    def test_clamp_line_upper(self) -> None:
        layout = _layout(SINGLE_HUNK)  # hunk 0 has 4 content lines -> max idx 3
        assert layout.clamp_line(0, 99) == 3

    def test_clamp_line_lower(self) -> None:
        layout = _layout(SINGLE_HUNK)
        assert layout.clamp_line(0, -5) == 0

    def test_clamp_selected_lines_drops_stale(self) -> None:
        layout = _layout(SINGLE_HUNK)  # max content-line index 3
        assert layout.clamp_selected_lines(0, frozenset({0, 2, 3, 4, 10})) == frozenset({0, 2, 3})

    def test_max_line_index_empty_hunk_is_zero(self) -> None:
        # A hunk with no content lines clamps the cursor to 0 (never negative).
        layout = DiffLayout(file_header_lines=2, hunk_line_counts=(0,))
        assert layout.max_line_index(0) == 0
        assert layout.clamp_line(0, 5) == 0
        assert layout.clamp_selected_lines(0, frozenset({0, 1})) == frozenset({0})


class TestEmptyDiff:
    """Regression for 9d06d0a chain / empty-diff safety.

    An empty diff has no hunks; clamp must not raise and offset queries are
    rejected rather than returning a bogus index.
    """

    def test_empty_diff_clamp_safe(self) -> None:
        layout = _layout("")
        assert layout.hunk_count == 0
        assert layout.clamp(0) == 0

    def test_empty_diff_offset_raises(self) -> None:
        layout = _layout("")
        with pytest.raises(IndexError):
            layout.offset_of(0)


class TestLineReveal:
    """Regression for 4abf1c3 / 5b8cee5: line-cursor scroll target math.

    Target = offset_of(hunk) + 1 (header) + line_cursor. The 5b8cee5 fix removed
    the spurious extra separator so this stays offset + 1 + cursor.
    """

    def test_line_reveal_target(self) -> None:
        layout = _layout(MULTI_HUNK)
        # hunk 0 header at y=2, +1 header +2 cursor = 5.
        assert layout.line_reveal(0, 2) == VisibleRegion(y=5, height=1)

    def test_line_reveal_second_hunk(self) -> None:
        layout = _layout(MULTI_HUNK)
        # hunk 1 header at y=7, +1 +0 cursor = 8.
        assert layout.line_reveal(1, 0) == VisibleRegion(y=8, height=1)
