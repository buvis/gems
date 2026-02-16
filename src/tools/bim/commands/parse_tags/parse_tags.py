from __future__ import annotations

import json
from pathlib import Path

from buvis.pybase.adapters import console


class CommandParseTags:
    def __init__(
        self: CommandParseTags,
        path_tags_json: Path,
        path_output: Path | None = None,
    ) -> None:
        if not path_tags_json.is_file():
            raise FileNotFoundError(f"Tags file not found: {path_tags_json}")
        self.path_tags_json = path_tags_json
        self.path_output = path_output.resolve() if path_output else None

    def execute(self: CommandParseTags) -> None:
        data = json.loads(self.path_tags_json.read_text())
        tags = [item["tag"] for item in data]
        unique_sorted_tags = sorted(set(tags))

        if self.path_output:
            self.path_output.write_text("\n".join(unique_sorted_tags))
        else:
            console.print("\n".join(unique_sorted_tags), mode="raw")
