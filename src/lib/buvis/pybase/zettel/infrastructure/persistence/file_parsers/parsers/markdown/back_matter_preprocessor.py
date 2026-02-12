from __future__ import annotations

import re


class ZettelParserMarkdownBackMatterPreprocessor:
    @staticmethod
    def preprocess(text: str) -> str:
        text = ZettelParserMarkdownBackMatterPreprocessor.fix_obsidian_dataview_keys(
            text,
        )
        return ZettelParserMarkdownBackMatterPreprocessor.quote_unsafe_strings(text)

    @staticmethod
    def fix_obsidian_dataview_keys(text: str) -> str:
        dataview_key_pattern = r"^(\S+)::"

        def replace(match: re.Match[str]) -> str:
            return match.group(1) + ":"

        corrected_lines = [re.sub(dataview_key_pattern, replace, line, count=1) for line in text.split("\n")]
        return "\n".join(corrected_lines)

    @staticmethod
    def quote_unsafe_strings(text: str) -> str:
        lines = text.split("\n")
        yaml_lines = []

        for line in lines:
            if ":" in line:
                try:
                    key, value = line.split(": ", 1)
                except ValueError:
                    key = line.split(":", 1)[0]
                    value = ""
                if (
                    (":" in value or "[" in value or "]" in value)
                    and not value.startswith('"')
                    and not value.endswith('"')
                ):
                    value = f'"{value}"'
                yaml_lines.append(f"{key}: {value}")
            else:
                yaml_lines.append(line)

        return "\n".join(yaml_lines)
