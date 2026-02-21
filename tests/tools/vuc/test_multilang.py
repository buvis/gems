from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from click.testing import CliRunner
from vuc.cli import cli
from vuc.commands.multilang import CommandMultilang


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def _mediainfo_json(audio_tracks: int) -> str:
    tracks = [{"@type": "General"}]
    tracks.extend({"@type": "Audio", "ID": str(idx)} for idx in range(audio_tracks))
    return json.dumps({"media": {"track": tracks}})


def _completed(stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["mediainfo"], returncode=returncode, stdout=stdout, stderr=stderr)


def _csv_rows(path: Path) -> list[list[str]]:
    with path.open(newline="") as fh:
        return list(csv.reader(fh))


class TestCommandMultilang:
    def test_single_audio_track_skipped(self, tmp_path, mocker) -> None:
        video = _touch(tmp_path / "single.mkv")
        output = tmp_path / "out.csv"
        mocker.patch("vuc.commands.multilang.subprocess.run", return_value=_completed(_mediainfo_json(audio_tracks=1)))

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert _csv_rows(output) == [["file", "audio_track_count"]]
        assert str(video) not in output.read_text()

    def test_multi_audio_tracks_reported(self, tmp_path, mocker) -> None:
        video = _touch(tmp_path / "multi.mkv")
        output = tmp_path / "out.csv"
        mocker.patch("vuc.commands.multilang.subprocess.run", return_value=_completed(_mediainfo_json(audio_tracks=2)))

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert _csv_rows(output) == [["file", "audio_track_count"], [str(video), "2"]]

    def test_mixed_files(self, tmp_path, mocker) -> None:
        single = _touch(tmp_path / "single.mkv")
        multi = _touch(tmp_path / "multi.mkv")
        output = tmp_path / "out.csv"

        def fake_run(args, **_kwargs):
            current = Path(args[-1])
            if current == single:
                return _completed(_mediainfo_json(audio_tracks=1))
            return _completed(_mediainfo_json(audio_tracks=3))

        mocker.patch("vuc.commands.multilang.subprocess.run", side_effect=fake_run)

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert _csv_rows(output) == [["file", "audio_track_count"], [str(multi), "3"]]

    def test_recursive_scan(self, tmp_path, mocker) -> None:
        video = _touch(tmp_path / "nested" / "deep" / "movie.mkv")
        output = tmp_path / "out.csv"
        mocker.patch("vuc.commands.multilang.subprocess.run", return_value=_completed(_mediainfo_json(audio_tracks=2)))

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert _csv_rows(output) == [["file", "audio_track_count"], [str(video), "2"]]

    def test_extension_filtering(self, tmp_path, mocker) -> None:
        mkv = _touch(tmp_path / "one.mkv")
        mp4 = _touch(tmp_path / "two.mp4")
        _touch(tmp_path / "notes.txt")
        _touch(tmp_path / "cover.jpg")
        output = tmp_path / "out.csv"
        run = mocker.patch(
            "vuc.commands.multilang.subprocess.run", return_value=_completed(_mediainfo_json(audio_tracks=2))
        )

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        called_files = {Path(call.args[0][-1]) for call in run.call_args_list}
        assert result.success is True
        assert called_files == {mkv, mp4}

    def test_case_insensitive_extensions(self, tmp_path, mocker) -> None:
        video = _touch(tmp_path / "MOVIE.MKV")
        output = tmp_path / "out.csv"
        mocker.patch("vuc.commands.multilang.subprocess.run", return_value=_completed(_mediainfo_json(audio_tracks=2)))

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert _csv_rows(output) == [["file", "audio_track_count"], [str(video), "2"]]

    def test_csv_headers(self, tmp_path, mocker) -> None:
        _touch(tmp_path / "movie.mkv")
        output = tmp_path / "out.csv"
        mocker.patch("vuc.commands.multilang.subprocess.run", return_value=_completed(_mediainfo_json(audio_tracks=2)))

        CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert _csv_rows(output)[0] == ["file", "audio_track_count"]

    def test_csv_quoting(self, tmp_path, mocker) -> None:
        video = _touch(tmp_path / "movie,part1.mkv")
        output = tmp_path / "out.csv"
        mocker.patch("vuc.commands.multilang.subprocess.run", return_value=_completed(_mediainfo_json(audio_tracks=2)))

        CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert f'"{video}",2' in output.read_text()

    def test_deterministic_order(self, tmp_path, mocker) -> None:
        first = _touch(tmp_path / "a.mkv")
        second = _touch(tmp_path / "z.mkv")
        output = tmp_path / "out.csv"
        mocker.patch("vuc.commands.multilang.subprocess.run", return_value=_completed(_mediainfo_json(audio_tracks=2)))

        CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert _csv_rows(output) == [
            ["file", "audio_track_count"],
            [str(first), "2"],
            [str(second), "2"],
        ]

    def test_skips_symlinks(self, tmp_path, mocker) -> None:
        target = _touch(tmp_path / "real.mkv")
        symlink = tmp_path / "link.mkv"
        symlink.symlink_to(target)
        output = tmp_path / "out.csv"
        run = mocker.patch(
            "vuc.commands.multilang.subprocess.run", return_value=_completed(_mediainfo_json(audio_tracks=2))
        )

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert _csv_rows(output) == [["file", "audio_track_count"], [str(target), "2"]]
        assert {Path(call.args[0][-1]) for call in run.call_args_list} == {target}

    def test_skips_hidden_files(self, tmp_path, mocker) -> None:
        visible = _touch(tmp_path / "visible.mkv")
        _touch(tmp_path / ".hidden.mkv")
        output = tmp_path / "out.csv"
        run = mocker.patch(
            "vuc.commands.multilang.subprocess.run", return_value=_completed(_mediainfo_json(audio_tracks=2))
        )

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert _csv_rows(output) == [["file", "audio_track_count"], [str(visible), "2"]]
        assert {Path(call.args[0][-1]) for call in run.call_args_list} == {visible}

    def test_skips_hidden_dirs(self, tmp_path, mocker) -> None:
        visible = _touch(tmp_path / "videos" / "visible.mkv")
        _touch(tmp_path / ".secret" / "hidden.mkv")
        output = tmp_path / "out.csv"
        run = mocker.patch(
            "vuc.commands.multilang.subprocess.run", return_value=_completed(_mediainfo_json(audio_tracks=2))
        )

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert _csv_rows(output) == [["file", "audio_track_count"], [str(visible), "2"]]
        assert {Path(call.args[0][-1]) for call in run.call_args_list} == {visible}

    def test_mediainfo_failure_continues(self, tmp_path, mocker) -> None:
        bad = _touch(tmp_path / "a.mkv")
        good = _touch(tmp_path / "b.mkv")
        output = tmp_path / "out.csv"

        def fake_run(args, **_kwargs):
            current = Path(args[-1])
            if current == bad:
                return _completed("", returncode=1, stderr="boom")
            return _completed(_mediainfo_json(audio_tracks=2))

        mocker.patch("vuc.commands.multilang.subprocess.run", side_effect=fake_run)

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert any(f"mediainfo failed for {bad}: boom" in warning for warning in result.warnings)
        assert _csv_rows(output) == [["file", "audio_track_count"], [str(good), "2"]]

    def test_mediainfo_timeout(self, tmp_path, mocker) -> None:
        timeout_file = _touch(tmp_path / "a.mkv")
        good = _touch(tmp_path / "b.mkv")
        output = tmp_path / "out.csv"

        def fake_run(args, **_kwargs):
            current = Path(args[-1])
            if current == timeout_file:
                raise subprocess.TimeoutExpired(cmd=args, timeout=30)
            return _completed(_mediainfo_json(audio_tracks=2))

        mocker.patch("vuc.commands.multilang.subprocess.run", side_effect=fake_run)

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert f"Timeout scanning {timeout_file}" in result.warnings
        assert _csv_rows(output) == [["file", "audio_track_count"], [str(good), "2"]]

    def test_malformed_json(self, tmp_path, mocker) -> None:
        bad = _touch(tmp_path / "a.mkv")
        good = _touch(tmp_path / "b.mkv")
        output = tmp_path / "out.csv"

        def fake_run(args, **_kwargs):
            current = Path(args[-1])
            if current == bad:
                return _completed("{not-json")
            return _completed(_mediainfo_json(audio_tracks=2))

        mocker.patch("vuc.commands.multilang.subprocess.run", side_effect=fake_run)

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert any(f"Invalid JSON from mediainfo for {bad}:" in warning for warning in result.warnings)
        assert _csv_rows(output) == [["file", "audio_track_count"], [str(good), "2"]]

    def test_empty_directory(self, tmp_path, mocker) -> None:
        output = tmp_path / "out.csv"
        run = mocker.patch("vuc.commands.multilang.subprocess.run")

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert result.output == "Scanned 0 files, found 0 with multiple audio tracks"
        assert _csv_rows(output) == [["file", "audio_track_count"]]
        run.assert_not_called()

    def test_no_audio_tracks(self, tmp_path, mocker) -> None:
        video = _touch(tmp_path / "video_only.mkv")
        output = tmp_path / "out.csv"
        payload = json.dumps({"media": {"track": [{"@type": "General"}, {"@type": "Video"}]}})
        mocker.patch("vuc.commands.multilang.subprocess.run", return_value=_completed(payload))

        result = CommandMultilang(directory=tmp_path, output_csv=output).execute()

        assert result.success is True
        assert _csv_rows(output) == [["file", "audio_track_count"]]
        assert str(video) not in output.read_text()


class TestCliWiring:
    def test_missing_mediainfo(self, tmp_path, mocker) -> None:
        output = tmp_path / "out.csv"
        mocker.patch("vuc.cli.shutil.which", return_value=None)
        panic = mocker.patch("vuc.cli.console.panic", side_effect=SystemExit(1))
        runner = CliRunner()

        result = runner.invoke(cli, ["multilang", str(tmp_path), str(output)])

        assert result.exit_code != 0
        panic.assert_called_once()
        assert "mediainfo is required" in panic.call_args.args[0]

    def test_invalid_directory(self, tmp_path, mocker) -> None:
        missing = tmp_path / "missing"
        output = tmp_path / "out.csv"
        panic = mocker.patch("vuc.cli.console.panic", side_effect=SystemExit(1))
        runner = CliRunner()

        result = runner.invoke(cli, ["multilang", str(missing), str(output)])

        assert result.exit_code != 0
        panic.assert_called_once()
        assert "isn't a directory" in panic.call_args.args[0]
