from __future__ import annotations

import platform
import subprocess
from datetime import datetime
from pathlib import Path

import tzlocal


class FileMetadataReader:
    """Utility reader that exposes static helpers for file metadata.

    The class is not meant to be instantiated; callers just need to invoke the
    static helpers to obtain timestamps such as the file creation datetime or
    the first commit datetime in a Git repository. Creation-time resolution is
    platform specific (Windows uses `st_ctime` while Unix systems prefer
    `st_birthtime` with a fallback to modification time).

    Example:

        >>> FileMetadataReader.get_creation_datetime(Path("example.txt"))
        datetime(2024, 7, 8, 12, 34, tzinfo=...)
    """

    @staticmethod
    def get_creation_datetime(file_path: Path) -> datetime:
        """
        Retrieve the creation date of a file, falling back to modification date if creation date is unavailable.

        Args:
            file_path (Path): Path to the file.

        Returns:
            datetime: Datetime when file was created.
        """
        if platform.system() == "Windows":
            creation_time = file_path.stat().st_ctime

        else:
            stat = file_path.stat()
            try:
                creation_time = stat.st_birthtime
            except AttributeError:
                creation_time = stat.st_mtime

        local_tz = tzlocal.get_localzone()
        return datetime.fromtimestamp(creation_time, tz=local_tz)

    @staticmethod
    def get_first_commit_datetime(file_path: Path) -> datetime | None:
        """
        Retrieve the date a file was first added to a Git repository located at the parent directory of file_path.

        Args:
            file_path (Path): Path to the file.

        Returns:
            datatime | None: Datetime of the first commit involving the file
                or None if the file wasn't committed to any Git repository.
        """
        try:
            file_path_obj = Path(file_path)
            git_repo_path = file_path_obj.parent
            output = subprocess.check_output(  # noqa: S603
                [
                    "git",
                    "log",
                    "--pretty=format:%ad",
                    "--date=format:%Y-%m-%dT%H:%M:%S%z",
                    "--diff-filter=A",
                    "--reverse",
                    file_path_obj.name,
                ],
                cwd=str(git_repo_path),
                stderr=subprocess.STDOUT,
                text=True,
            )
            first_commit_line = output.split("\n")[0].strip()
            try:
                return datetime.strptime(first_commit_line, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                return None

        except subprocess.CalledProcessError:
            return None
