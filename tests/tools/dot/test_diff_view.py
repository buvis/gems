from __future__ import annotations

from rich.text import Text

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
