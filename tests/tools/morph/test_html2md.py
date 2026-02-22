from __future__ import annotations

import re
import sys
import types
from unittest.mock import patch

if "markdownify" not in sys.modules:
    fake_markdownify = types.ModuleType("markdownify")

    def _markdownify(html: str, **_kwargs) -> str:
        text = html
        text = re.sub(r"<h1>(.*?)</h1>", lambda m: f"# {m.group(1)}\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<h2>(.*?)</h2>", lambda m: f"## {m.group(1)}\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<p>(.*?)</p>", lambda m: f"{m.group(1)}\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<li>(.*?)</li>", lambda m: f"* {m.group(1)}\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</?ul>", "", text, flags=re.IGNORECASE)
        return text

    fake_markdownify.markdownify = _markdownify
    sys.modules["markdownify"] = fake_markdownify

from morph.commands.html2md.html2md import CommandHtml2Md


class TestHtml2MdBasic:
    def test_convert_single_file(self, tmp_path) -> None:
        html_file = tmp_path / "note.html"
        html_file.write_text("<h1>Title</h1><p>Hello</p>", encoding="utf-8")

        result = CommandHtml2Md(directory=str(tmp_path)).execute()

        assert result.success
        assert result.output == "Converted 1 file(s)"
        assert result.warnings == []
        assert result.error is None
        assert (tmp_path / "note.md").read_text(encoding="utf-8").strip() == "# Title\n\nHello"

    def test_convert_multiple_files(self, tmp_path) -> None:
        (tmp_path / "a.html").write_text("<h1>A</h1><p>one</p>", encoding="utf-8")
        (tmp_path / "b.html").write_text("<h1>B</h1><p>two</p>", encoding="utf-8")

        result = CommandHtml2Md(directory=str(tmp_path)).execute()

        assert result.success
        assert result.output == "Converted 2 file(s)"
        assert result.warnings == []
        assert result.error is None
        assert (tmp_path / "a.md").exists()
        assert (tmp_path / "b.md").exists()

    def test_empty_directory(self, tmp_path) -> None:
        result = CommandHtml2Md(directory=str(tmp_path)).execute()

        assert result.success
        assert result.output == "Converted 0 file(s)"
        assert result.warnings == []
        assert result.error is None

    def test_non_html_files_skipped(self, tmp_path) -> None:
        (tmp_path / "note.txt").write_text("plain text", encoding="utf-8")

        result = CommandHtml2Md(directory=str(tmp_path)).execute()

        assert result.success
        assert result.output == "Converted 0 file(s)"
        assert result.warnings == []
        assert result.error is None
        assert not (tmp_path / "note.md").exists()

    def test_subdirectory_skipped(self, tmp_path) -> None:
        (tmp_path / "subdir").mkdir()

        result = CommandHtml2Md(directory=str(tmp_path)).execute()

        assert result.success
        assert result.output == "Converted 0 file(s)"

    def test_uppercase_html_extension(self, tmp_path) -> None:
        (tmp_path / "note.HTML").write_text("<h1>Title</h1><p>Body</p>", encoding="utf-8")

        result = CommandHtml2Md(directory=str(tmp_path)).execute()

        assert result.success
        assert result.output == "Converted 1 file(s)"
        assert (tmp_path / "note.md").exists()


class TestHtml2MdMarkdown:
    def test_atx_headings(self, tmp_path) -> None:
        (tmp_path / "headings.html").write_text("<h1>Main</h1><h2>Sub</h2>", encoding="utf-8")

        CommandHtml2Md(directory=str(tmp_path)).execute()

        content = (tmp_path / "headings.md").read_text(encoding="utf-8")
        assert "# Main" in content
        assert "## Sub" in content

    def test_list_markers_dashes(self, tmp_path) -> None:
        (tmp_path / "list.html").write_text("<ul><li>one</li><li>two</li></ul>", encoding="utf-8")

        CommandHtml2Md(directory=str(tmp_path)).execute()

        content = (tmp_path / "list.md").read_text(encoding="utf-8")
        assert "- one" in content
        assert "- two" in content
        assert "* one" not in content

    def test_duplicate_h1_removed(self, tmp_path) -> None:
        (tmp_path / "dup.html").write_text("<p>Title</p><h1>Title</h1><p>Body</p>", encoding="utf-8")

        CommandHtml2Md(directory=str(tmp_path)).execute()

        content = (tmp_path / "dup.md").read_text(encoding="utf-8")
        assert content.strip() == "# Title\n\nBody"
        assert "\nTitle\n" not in content

    def test_trailing_whitespace_stripped(self, tmp_path) -> None:
        (tmp_path / "spaces.html").write_text("<p>ignored</p>", encoding="utf-8")

        with patch(
            "morph.commands.html2md.html2md.markdownify",
            return_value="line with spaces   \nnext line   \n",
        ):
            CommandHtml2Md(directory=str(tmp_path)).execute()

        content = (tmp_path / "spaces.md").read_text(encoding="utf-8")
        assert content == "line with spaces\nnext line"


class TestCleanMarkdown:
    def test_escaped_asterisk_list_replaced(self) -> None:
        md = "\\* item one\n\\* item two"

        result = CommandHtml2Md._clean_markdown(md)

        assert "- item one" in result
        assert "- item two" in result
        assert "\\*" not in result

    def test_star_space_list_replaced(self) -> None:
        md = "# Title\n\n* item one\n* item two"

        result = CommandHtml2Md._clean_markdown(md)

        assert "- item one" in result
        assert "- item two" in result

    def test_indented_star_list_replaced(self) -> None:
        md = "# Title\n\n * item one\n * item two"

        result = CommandHtml2Md._clean_markdown(md)

        assert "- item one" in result
        assert "- item two" in result

    def test_duplicate_title_after_heading_removed(self) -> None:
        md = "# My Title\n\nMy Title\n\nBody text"

        result = CommandHtml2Md._clean_markdown(md)

        assert "My Title\n\nMy Title" not in result
        assert "# My Title" in result
        assert "Body text" in result

    def test_no_heading_preserves_content(self) -> None:
        md = "Just some text\nAnother line"

        result = CommandHtml2Md._clean_markdown(md)

        assert "Just some text" in result
        assert "Another line" in result

    def test_blank_lines_before_heading_stripped(self) -> None:
        md = "\n\n\n# Title\n\nBody"

        result = CommandHtml2Md._clean_markdown(md)

        assert result.startswith("# Title")

    def test_blank_lines_after_content_stripped(self) -> None:
        md = "# Title\n\nBody\n\n\n"

        result = CommandHtml2Md._clean_markdown(md)

        assert result.endswith("Body")

    def test_empty_input(self) -> None:
        result = CommandHtml2Md._clean_markdown("")

        assert result == ""

    def test_only_blank_lines(self) -> None:
        result = CommandHtml2Md._clean_markdown("\n\n\n")

        assert result == ""

    def test_pre_heading_text_matching_h1_skipped(self) -> None:
        md = "My Title\n\n# My Title\n\nBody"

        result = CommandHtml2Md._clean_markdown(md)

        assert result == "# My Title\n\nBody"


class TestStripOuterBlankLines:
    def test_empty_list(self) -> None:
        result = CommandHtml2Md._strip_outer_blank_lines([])

        assert result == []

    def test_all_blank(self) -> None:
        result = CommandHtml2Md._strip_outer_blank_lines(["", "  ", ""])

        assert result == []

    def test_no_blanks(self) -> None:
        result = CommandHtml2Md._strip_outer_blank_lines(["a", "b"])

        assert result == ["a", "b"]

    def test_leading_and_trailing_blanks(self) -> None:
        result = CommandHtml2Md._strip_outer_blank_lines(["", "a", "b", ""])

        assert result == ["a", "b"]


class TestHtml2MdErrors:
    def test_unreadable_file(self, tmp_path) -> None:
        (tmp_path / "bad.html").write_text("<p>x</p>", encoding="utf-8")

        with patch("morph.commands.html2md.html2md.Path.read_text", side_effect=OSError("denied")):
            result = CommandHtml2Md(directory=str(tmp_path)).execute()

        assert result.success
        assert result.output == "Converted 0 file(s)"
        assert result.error is None
        assert any("Failed to convert" in warning for warning in result.warnings)

    def test_encoding_error(self, tmp_path) -> None:
        (tmp_path / "broken.html").write_bytes(b"\xff\xfe\x00")

        result = CommandHtml2Md(directory=str(tmp_path)).execute()

        assert result.success
        assert result.output == "Converted 0 file(s)"
        assert result.error is None
        assert any("Failed to convert" in warning for warning in result.warnings)

    def test_markdownify_raises(self, tmp_path) -> None:
        (tmp_path / "crash.html").write_text("<p>data</p>", encoding="utf-8")

        with patch(
            "morph.commands.html2md.html2md.markdownify",
            side_effect=ValueError("parse error"),
        ):
            result = CommandHtml2Md(directory=str(tmp_path)).execute()

        assert result.success
        assert result.output == "Converted 0 file(s)"
        assert any("Failed to convert" in w for w in result.warnings)
