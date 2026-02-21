from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult
from markdownify import markdownify


class CommandHtml2Md:
    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)

    def execute(self) -> CommandResult:
        warnings: list[str] = []
        converted = 0

        for html_file in self.directory.iterdir():
            if not html_file.is_file() or html_file.suffix.lower() != ".html":
                continue

            try:
                html_content = html_file.read_text(encoding="utf-8")
                markdown_content = markdownify(
                    html_content,
                    heading_style="ATX",
                    escape_asterisks=False,
                    escape_underscores=False,
                )
                cleaned = self._clean_markdown(markdown_content)
                html_file.with_suffix(".md").write_text(cleaned, encoding="utf-8")
                converted += 1
            except Exception as exc:
                warnings.append(f"Failed to convert {html_file}: {exc}")

        return CommandResult(
            success=True,
            output=f"Converted {converted} file(s)",
            warnings=warnings,
        )

    @staticmethod
    def _clean_markdown(markdown_content: str) -> str:
        lines = [line.rstrip() for line in markdown_content.replace("\\* ", "- ").splitlines()]
        lines = CommandHtml2Md._strip_outer_blank_lines(lines)

        first_heading = next((line for line in lines if line.startswith("# ")), None)
        h1_text = first_heading[2:].strip() if first_heading else None

        rebuilt: list[str] = []
        seen_heading = False
        for line in lines:
            if not seen_heading:
                if not line.strip():
                    continue
                if line.startswith("# "):
                    seen_heading = True
                elif h1_text and line.strip() == h1_text:
                    continue

            if h1_text and line.strip() == h1_text:
                continue

            if line.startswith(" * "):
                line = f"- {line[3:]}"
            elif line.startswith("* "):
                line = f"- {line[2:]}"
            rebuilt.append(line)

        rebuilt = CommandHtml2Md._strip_outer_blank_lines(rebuilt)
        return "\n".join(rebuilt)

    @staticmethod
    def _strip_outer_blank_lines(lines: list[str]) -> list[str]:
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return lines
