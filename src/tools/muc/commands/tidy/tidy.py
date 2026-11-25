from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult

from muc.shared.dir_tree import DirTree


class CommandTidy:
    def __init__(self: CommandTidy, directory: Path, junk_extensions: list[str]) -> None:
        self.dir = directory
        self.junk_extensions = junk_extensions

    def execute(self: CommandTidy) -> CommandResult:
        results = [
            DirTree.merge_mac_metadata(self.dir),
            DirTree.normalize_file_extensions(self.dir),
            DirTree.delete_by_extension(self.dir, self.junk_extensions),
            DirTree.remove_empty_directories(self.dir),
        ]
        return CommandResult(
            success=True,
            output=f"Tidied {self.dir}",
            info=[message for result in results for message in result.info],
            warnings=[message for result in results for message in result.warnings],
            metadata={"steps": results},  # step order, for interfaces that render as it happened
        )
