from __future__ import annotations

import shutil
from pathlib import Path

import ffmpeg
from buvis.pybase.result import CommandResult


class CommandLimit:
    def __init__(
        self: CommandLimit,
        source_dir: Path,
        output_dir: Path,
        bitrate: int,
        bit_depth: int,
        sampling_rate: int,
    ) -> None:
        self.source_dir = source_dir
        self.output_dir = output_dir
        self.bitrate = bitrate
        self.bit_depth = bit_depth
        self.sampling_rate = sampling_rate

    def execute(self: CommandLimit) -> CommandResult:
        successes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        for file_path in self.source_dir.rglob("*.flac"):
            if not file_path.is_relative_to(self.output_dir):
                self._transcode_flac(file_path, successes, warnings, errors)

        if errors:
            return CommandResult(
                success=False,
                output="\n".join(successes) if successes else None,
                error="\n".join(errors),
                warnings=warnings,
            )
        return CommandResult(
            success=True,
            output="\n".join(successes) if successes else "No files to transcode",
            warnings=warnings,
        )

    def _transcode_flac(
        self: CommandLimit,
        file_path: Path,
        successes: list[str],
        warnings: list[str],
        errors: list[str],
    ) -> None:
        try:
            probe = ffmpeg.probe(str(file_path), loglevel="quiet")
            audio_stream = next(
                (stream for stream in probe["streams"] if stream["codec_type"] == "audio"),
                None,
            )

            relative_path = file_path.relative_to(self.source_dir)
            output_path = self.output_dir / relative_path

            output_path.parent.mkdir(parents=True, exist_ok=True)

            if audio_stream:
                bitrate = int(audio_stream.get("bit_rate", 0))
                sampling_rate = int(audio_stream.get("sample_rate", 0))
                bit_depth = int(audio_stream.get("bits_per_sample", 0))

                if bitrate > self.bitrate or sampling_rate > self.sampling_rate or bit_depth > self.bit_depth:
                    stream = ffmpeg.input(str(file_path))
                    stream = ffmpeg.output(
                        stream,
                        str(output_path),
                        audio_bitrate=f"{self.bitrate}",
                        ar=f"{self.sampling_rate}",
                        sample_fmt=f"s{self.bit_depth}",
                        loglevel="quiet",
                    )
                    ffmpeg.run(stream, overwrite_output=True)

                    successes.append(f"Transcoded: {file_path}  -> {output_path}")
                else:
                    shutil.copy2(file_path, output_path)
                    successes.append(f"Copied: {file_path}  -> {output_path}")
            else:
                warnings.append(f"Skipped (no audio stream found): {file_path}")
        except ffmpeg.Error as e:
            errors.append(f"Error processing {file_path}: {e.stderr}")
