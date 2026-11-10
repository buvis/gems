from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult

from .delete_by_extension import delete_by_extension
from .lowercase_file_extensions import (
    lowercase_file_extensions,
)
from .merge_mac_metadata import (
    merge_mac_metadata,
)
from .remove_empty_directories import (
    remove_empty_directories,
)
from .rename_equivalent_extensions import (
    rename_equivalent_extensions,
)
from .safe_rglob import is_safe_path, safe_rglob


class DirTree:
    """Utility with static directory operations.

    Provides static methods for counting files, cleanup routines, and normalization
    helpers. No instantiation is required.

    Example:
        >>> from muc.shared.dir_tree import DirTree
        >>> from pathlib import Path
        >>> count = DirTree.count_files(Path('/data'))
    """

    _is_safe_path = staticmethod(is_safe_path)
    _safe_rglob = staticmethod(safe_rglob)

    @staticmethod
    def count_files(directory: Path) -> int:
        """Count the number of files in the directory and its subdirectories.

        Args:
            directory: Path to the directory to process.

        Returns:
            Number of files in the directory and its subdirectories.
        """
        return sum(1 for p in safe_rglob(directory) if p.is_file())

    @staticmethod
    def get_max_depth(directory: Path) -> int:
        """Determine the maximum depth of the directory tree.

        Args:
            directory: Path to the directory to process.

        Returns:
            Maximum depth of the directory tree.
        """
        paths = list(safe_rglob(directory))
        if not paths:
            return 0
        return max(len(p.relative_to(directory).parts) for p in paths)

    @staticmethod
    def delete_by_extension(directory: Path, extensions_to_delete: list[str]) -> CommandResult:
        """Delete files with specific extensions in the given directory.

        Args:
            directory: Path to the directory to process.
            extensions_to_delete: List of file extensions to delete.

        Returns:
            Completed actions and recoverable failures.
        """
        return delete_by_extension(directory, extensions_to_delete)

    @staticmethod
    def normalize_file_extensions(directory: Path) -> CommandResult:
        """Normalize file extensions in the given directory:
        1) lowercase the extensions
        2) replace equivalents

        Args:
            directory: Path to the directory to process.

        Returns:
            Completed actions and recoverable failures from both passes.
        """
        lowercase_result = lowercase_file_extensions(directory)

        # TODO: this should be configurable
        equivalent_extensions = [
            ["jpg", "jpeg", "jfif"],
            ["mp3", "mp2"],
            ["flac", "fla"],
        ]
        equivalent_result = rename_equivalent_extensions(directory, equivalent_extensions)
        return CommandResult(
            success=True,
            info=lowercase_result.info + equivalent_result.info,
            warnings=lowercase_result.warnings + equivalent_result.warnings,
        )

    @staticmethod
    def remove_empty_directories(directory: Path) -> CommandResult:
        """Recursively remove all empty directories.

        Traverses bottom-up to remove directories that become empty
        after their children are removed.

        Args:
            directory: Root directory to clean.

        Returns:
            Completed actions and recoverable failures.

        Note:
            Modifies the directory tree in place. Non-empty directories
            and files are preserved.
        """
        return remove_empty_directories(directory)

    @staticmethod
    def merge_mac_metadata(directory: Path) -> CommandResult:
        """Restore macOS metadata from AppleDouble helper files.

        Walks the directory tree for AppleDouble files (._*) and, when not on
        Windows, applies their extended attributes back to the corresponding
        originals before cleaning up any orphaned helper files. This serves as
        a post-copy cleanup for macOS metadata files.

        Args:
            directory: Directory containing files and AppleDouble metadata.

        Returns:
            Completed actions and warnings for metadata files that were kept.
        """
        return merge_mac_metadata(directory)
