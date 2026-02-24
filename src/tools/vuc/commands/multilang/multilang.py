from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from buvis.pybase.result import CommandResult

VIDEO_EXTENSIONS = frozenset(
    {
        ".avi",
        ".flv",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".ts",
        ".webm",
        ".wmv",
    },
)


class CommandMultilang:
    def __init__(self, directory: Path, output_csv: Path) -> None:
        self.directory = directory
        self.output_csv = output_csv

    def execute(self) -> CommandResult:
        warnings: list[str] = []
        multi_audio_files: list[tuple[str, int]] = []

        video_files = sorted(
            f
            for f in self.directory.rglob("*")
            if f.is_file()
            and not f.is_symlink()
            and not any(p.name.startswith(".") for p in f.relative_to(self.directory).parents)
            and not f.name.startswith(".")
            and f.suffix.lower() in VIDEO_EXTENSIONS
        )

        for video_file in video_files:
            try:
                proc = subprocess.run(
                    ["mediainfo", "--Output=JSON", str(video_file)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                warnings.append(f"Timeout scanning {video_file}")
                continue

            if proc.returncode != 0:
                warnings.append(f"mediainfo failed for {video_file}: {proc.stderr.strip()}")
                continue

            try:
                data = json.loads(proc.stdout)
            except json.JSONDecodeError as exc:
                warnings.append(f"Invalid JSON from mediainfo for {video_file}: {exc}")
                continue

            audio_tracks = [track for track in data.get("media", {}).get("track", []) if track.get("@type") == "Audio"]

            if len(audio_tracks) > 1:
                multi_audio_files.append((str(video_file), len(audio_tracks)))

        try:
            with self.output_csv.open("w", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["file", "audio_track_count"])
                for file_path, count in multi_audio_files:
                    writer.writerow([file_path, count])
        except OSError as exc:
            return CommandResult(
                success=False,
                error=f"Failed to write CSV: {exc}",
                warnings=warnings,
            )

        scanned = len(video_files)
        found = len(multi_audio_files)
        return CommandResult(
            success=True,
            output=f"Scanned {scanned} files, found {found} with multiple audio tracks",
            warnings=warnings,
        )
