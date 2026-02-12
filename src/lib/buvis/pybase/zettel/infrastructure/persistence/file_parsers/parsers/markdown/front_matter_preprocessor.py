from __future__ import annotations

import re


class ZettelParserMarkdownFrontMatterPreprocessor:
    @staticmethod
    def preprocess(text: str) -> str:
        return ZettelParserMarkdownFrontMatterPreprocessor.normalize_tags(text)

    @staticmethod
    def normalize_tags(text: str) -> str:
        # Define the regex pattern to match lines starting with "tag:" or "tags:"
        pattern = r"^(?:tag|tags):(?!\n)\s*(.*)$"

        # Define a replacement function that processes the matched tags
        def replace_tags(match: re.Match[str]) -> str:
            # Extract the matched group (the tags part)
            tags_part = match.group(1)

            # Remove unsafe characters
            tags_part = tags_part.replace("[", "").replace("]", "").replace(", ", " ").replace(",", " ")

            # Remove hashes and split tags into a list
            tags_list = [tag.replace("#", "") for tag in tags_part.split()]

            # Join the list items with commas and enclose in brackets
            processed_tags = "[" + ", ".join(tags_list) + "]"

            # Return the modified line
            return f"{match.group(0).split(':')[0]}: {processed_tags}"

        # Replace matches in the multiline string
        return re.sub(pattern, replace_tags, text, flags=re.MULTILINE)
