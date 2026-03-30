from __future__ import annotations

from rich.text import Text

from dot.tui.patch import Hunk
from dot.tui.widgets.diff_view import DiffView


def _render(diff_text: str) -> Text:
    widget = DiffView(id="diff")
    widget.update_diff(diff_text)
    return widget.render()


class TestDiffView:
    def test_empty_diff_shows_placeholder(self) -> None:
        result = _render("")
        assert "(no diff)" in str(result)

    def test_added_line_green(self) -> None:
        result = _render("+added line")
        spans = result._spans
        assert any("green" in str(s.style) for s in spans)

    def test_removed_line_red(self) -> None:
        result = _render("-removed line")
        spans = result._spans
        assert any("red" in str(s.style) for s in spans)

    def test_hunk_header_dim(self) -> None:
        result = _render("@@ -1,3 +1,4 @@")
        spans = result._spans
        assert any("dim" in str(s.style) for s in spans)

    def test_file_header_bold(self) -> None:
        result = _render("--- a/file.txt\n+++ b/file.txt")
        spans = result._spans
        assert any("bold" in str(s.style) for s in spans)

    def test_context_line_default(self) -> None:
        result = _render(" context line")
        assert "context line" in str(result)
        styled = [
            s for s in result._spans
            if any(k in str(s.style) for k in ("green", "red", "cyan", "bold", "dim"))
        ]
        assert len(styled) == 0

    def test_binary_file_message(self) -> None:
        result = _render("Binary files a/img.png and b/img.png differ")
        assert "(binary file)" in str(result)

    def test_update_diff_replaces_content(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff("+first")
        assert "first" in str(widget.render())
        widget.update_diff("+second")
        text = str(widget.render())
        assert "second" in text
        assert "first" not in text

    def test_file_header_not_treated_as_add_remove(self) -> None:
        result = _render("--- a/file.txt\n+++ b/file.txt")
        spans = result._spans
        assert not any("green" in str(s.style) for s in spans)
        assert not any("red" in str(s.style) for s in spans)

    def test_mixed_diff_output(self) -> None:
        diff = "\n".join([
            "--- a/hello.py",
            "+++ b/hello.py",
            "@@ -1,3 +1,4 @@",
            " import os",
            "-old_line",
            "+new_line",
            " unchanged",
        ])
        result = _render(diff)
        text = str(result)
        spans = result._spans

        assert "--- a/hello.py" in text
        assert "+new_line" in text
        assert "-old_line" in text

        style_strs = [str(s.style) for s in spans]
        assert any("bold" in s for s in style_strs)
        assert any("dim" in s for s in style_strs)
        assert any("green" in s for s in style_strs)
        assert any("red" in s for s in style_strs)


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

SINGLE_HUNK = """\
--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 line1
+added1
 line2
 line3"""

BINARY_DIFF = "Binary files a/img.png and b/img.png differ"


class TestDiffViewHunkNavigation:
    def test_update_diff_parses_hunks(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(MULTI_HUNK)
        assert widget.hunk_count == 2

    def test_focused_hunk_starts_at_zero(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(MULTI_HUNK)
        assert widget.focused_hunk_index == 0

    def test_focused_hunk_returns_correct_hunk(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(MULTI_HUNK)
        hunk = widget.focused_hunk
        assert hunk is not None
        assert isinstance(hunk, Hunk)
        assert "@@ -1,3 +1,4 @@" in hunk.header

    def test_action_next_hunk_moves_forward(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(MULTI_HUNK)
        widget.action_next_hunk()
        assert widget.focused_hunk_index == 1

    def test_action_prev_hunk_moves_backward(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(MULTI_HUNK)
        widget.action_next_hunk()
        assert widget.focused_hunk_index == 1
        widget.action_prev_hunk()
        assert widget.focused_hunk_index == 0

    def test_action_next_hunk_clamps_at_end(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(MULTI_HUNK)
        widget.action_next_hunk()
        widget.action_next_hunk()
        widget.action_next_hunk()
        assert widget.focused_hunk_index == 1

    def test_action_prev_hunk_clamps_at_zero(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(MULTI_HUNK)
        widget.action_prev_hunk()
        assert widget.focused_hunk_index == 0

    def test_update_diff_resets_focus_to_zero(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(MULTI_HUNK)
        widget.action_next_hunk()
        assert widget.focused_hunk_index == 1
        widget.update_diff(MULTI_HUNK)
        assert widget.focused_hunk_index == 0

    def test_empty_diff_returns_none_focused_hunk(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff("")
        assert widget.focused_hunk is None

    def test_binary_diff_returns_none_focused_hunk(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(BINARY_DIFF)
        assert widget.focused_hunk is None

    def test_is_staged_tracks_staged_parameter(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(MULTI_HUNK, staged=True)
        assert widget.is_staged is True

    def test_is_staged_defaults_to_false(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(MULTI_HUNK)
        assert widget.is_staged is False

    def test_single_hunk_navigation(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(SINGLE_HUNK)
        assert widget.hunk_count == 1
        assert widget.focused_hunk_index == 0
        widget.action_next_hunk()
        assert widget.focused_hunk_index == 0
        widget.action_prev_hunk()
        assert widget.focused_hunk_index == 0

    def test_focused_hunk_changes_after_navigation(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(MULTI_HUNK)
        first_header = widget.focused_hunk.header
        widget.action_next_hunk()
        second_header = widget.focused_hunk.header
        assert first_header != second_header
        assert "@@ -10,3 +11,4 @@" in second_header


LINE_SELECT_DIFF = (
    "--- a/f.py\n+++ b/f.py\n@@ -1,4 +1,4 @@\n"
    " context1\n-old1\n-old2\n+new1\n+new2\n context2"
)

# Hunk with context between changed lines for skip-context test:
# 0: " ctx1"  <- context
# 1: "-a"     <- changed
# 2: " ctx2"  <- context (should be skipped)
# 3: "+b"     <- changed
# 4: " ctx3"  <- context
LINE_SELECT_SKIP_DIFF = (
    "--- a/f.py\n+++ b/f.py\n@@ -1,4 +1,4 @@\n"
    " ctx1\n-a\n ctx2\n+b\n ctx3"
)


class TestDiffViewLineSelect:
    def test_enter_sets_mode(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(LINE_SELECT_DIFF)
        widget.action_enter_line_select()
        assert widget.in_line_select_mode is True

    def test_enter_positions_cursor_on_first_changed_line(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(LINE_SELECT_DIFF)
        widget.action_enter_line_select()
        assert widget.line_cursor == 1

    def test_enter_with_no_hunk_is_noop(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff("")
        widget.action_enter_line_select()
        assert widget.in_line_select_mode is False

    def test_line_down_moves_to_next_changed(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(LINE_SELECT_DIFF)
        widget.action_enter_line_select()
        assert widget.line_cursor == 1
        widget.action_line_down()
        assert widget.line_cursor == 2

    def test_line_down_skips_context_lines(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(LINE_SELECT_SKIP_DIFF)
        widget.action_enter_line_select()
        assert widget.line_cursor == 1  # "-a"
        widget.action_line_down()
        assert widget.line_cursor == 3  # "+b", skipped " ctx2" at index 2

    def test_line_up_moves_to_prev_changed(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(LINE_SELECT_DIFF)
        widget.action_enter_line_select()
        widget.action_line_down()
        assert widget.line_cursor == 2
        widget.action_line_up()
        assert widget.line_cursor == 1

    def test_line_up_clamps_at_first_changed(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(LINE_SELECT_DIFF)
        widget.action_enter_line_select()
        assert widget.line_cursor == 1
        widget.action_line_up()
        assert widget.line_cursor == 1

    def test_line_down_clamps_at_last_changed(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(LINE_SELECT_DIFF)
        widget.action_enter_line_select()
        # Move to last changed line (index 4: "+new2")
        widget.action_line_down()  # 1 -> 2
        widget.action_line_down()  # 2 -> 3
        widget.action_line_down()  # 3 -> 4
        widget.action_line_down()  # should clamp at 4
        assert widget.line_cursor == 4

    def test_toggle_adds_to_selection(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(LINE_SELECT_DIFF)
        widget.action_enter_line_select()
        widget.action_toggle_line()
        assert 1 in widget.selected_line_indices

    def test_toggle_twice_removes_from_selection(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(LINE_SELECT_DIFF)
        widget.action_enter_line_select()
        widget.action_toggle_line()
        widget.action_toggle_line()
        assert 1 not in widget.selected_line_indices

    def test_exit_clears_mode_and_selection(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(LINE_SELECT_DIFF)
        widget.action_enter_line_select()
        widget.action_toggle_line()
        widget.action_exit_line_select()
        assert widget.in_line_select_mode is False
        assert widget.selected_line_indices == set()

    def test_selected_line_indices_starts_empty(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(LINE_SELECT_DIFF)
        widget.action_enter_line_select()
        assert widget.selected_line_indices == set()

    def test_j_in_line_select_navigates_lines_not_hunks(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(MULTI_HUNK)
        widget.action_enter_line_select()
        assert widget.in_line_select_mode is True
        initial_hunk = widget.focused_hunk_index
        widget.action_next_hunk()  # j key - should move line, not hunk
        assert widget.in_line_select_mode is True
        assert widget.focused_hunk_index == initial_hunk

    def test_update_diff_exits_line_select(self) -> None:
        widget = DiffView(id="diff")
        widget.update_diff(LINE_SELECT_DIFF)
        widget.action_enter_line_select()
        assert widget.in_line_select_mode is True
        widget.update_diff(LINE_SELECT_DIFF)
        assert widget.in_line_select_mode is False
