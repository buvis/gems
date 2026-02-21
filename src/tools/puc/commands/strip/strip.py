from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from buvis.pybase.result import CommandResult, FatalError


class CommandStrip:
    def __init__(self: CommandStrip, files: tuple[str, ...], keep_tags: list[str]) -> None:
        self.files = files
        self.keep_tags = keep_tags

    def execute(self: CommandStrip) -> CommandResult:
        if shutil.which("exiftool") is None:
            msg = "exiftool not found. Install: brew install exiftool (macOS)"
            msg += " or apt install libimage-exiftool-perl (Linux)"
            raise FatalError(msg)

        is_macos = sys.platform == "darwin"
        setfile_path = shutil.which("SetFile") if is_macos else None

        warnings: list[str] = []
        processed = 0

        if is_macos and setfile_path is None:
            warnings.append("SetFile not found; skipping creation-date updates")

        for file_path_str in self.files:
            path = Path(file_path_str)
            if not path.is_file():
                warnings.append(f"Skipping {path}: not a file")
                continue

            if is_macos and setfile_path is not None:
                date_result = subprocess.run(
                    [
                        "exiftool",
                        "-DateTimeOriginal",
                        "-s3",
                        "-d",
                        "%m/%d/%Y %H:%M:%S",
                        str(path),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if date_result.returncode != 0 or date_result.stdout.strip() == "":
                    warnings.append(f"{path.name}: no DateTimeOriginal, skipping date set")
                else:
                    set_date_result = subprocess.run(
                        [setfile_path, "-d", date_result.stdout.strip(), str(path)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if set_date_result.returncode != 0:
                        warnings.append(f"{path.name}: failed to set creation date")

            strip_result = subprocess.run(
                [
                    "exiftool",
                    "-all=",
                    "-tagsfromfile",
                    "@",
                    *[f"-{tag}" for tag in self.keep_tags],
                    "-ICC_Profile:all",
                    "-overwrite_original",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if strip_result.returncode != 0:
                warnings.append(f"{path.name}: failed to strip metadata: {strip_result.stderr.strip()}")
                continue

            processed += 1

        return CommandResult(success=True, output=f"Processed {processed} file(s)", warnings=warnings)
