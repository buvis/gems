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
