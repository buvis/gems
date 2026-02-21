from __future__ import annotations

import subprocess

import pytest
from buvis.pybase.result import FatalError
from puc.commands.strip.strip import CommandStrip

KEEP_TAGS = ["DateTimeOriginal", "CreateDate", "Copyright"]


class TestCommandStrip:
    def test_missing_exiftool(self, mocker) -> None:
        mocker.patch("puc.commands.strip.strip.shutil.which", return_value=None)
        with pytest.raises(FatalError, match="exiftool not found"):
            CommandStrip(files=("photo.jpg",), keep_tags=KEEP_TAGS).execute()

    def test_file_not_found(self, mocker, tmp_path) -> None:
        mocker.patch("puc.commands.strip.strip.shutil.which", return_value="/usr/local/bin/exiftool")
        mocker.patch("puc.commands.strip.strip.sys.platform", "darwin")
        missing = str(tmp_path / "nonexistent.jpg")
        result = CommandStrip(files=(missing,), keep_tags=KEEP_TAGS).execute()
        assert result.success is True
        assert result.output == "Processed 0 file(s)"
        assert any("not a file" in w for w in result.warnings)

    def test_successful_strip_macos(self, mocker, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.touch()

        mocker.patch("puc.commands.strip.strip.sys.platform", "darwin")

        def which_side_effect(cmd):
            if cmd == "exiftool":
                return "/usr/local/bin/exiftool"
            if cmd == "SetFile":
                return "/usr/bin/SetFile"
            return None

        mocker.patch("puc.commands.strip.strip.shutil.which", side_effect=which_side_effect)

        run_mock = mocker.patch(
            "puc.commands.strip.strip.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="01/15/2024 10:30:00\n", stderr=""),
        )

        result = CommandStrip(files=(str(photo),), keep_tags=KEEP_TAGS).execute()

        assert result.success is True
        assert result.output == "Processed 1 file(s)"
        assert run_mock.call_count == 3  # exiftool read date + SetFile + exiftool strip

    def test_successful_strip_non_macos(self, mocker, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.touch()

        mocker.patch("puc.commands.strip.strip.sys.platform", "linux")
        mocker.patch("puc.commands.strip.strip.shutil.which", return_value="/usr/bin/exiftool")
        run_mock = mocker.patch(
            "puc.commands.strip.strip.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        )

        result = CommandStrip(files=(str(photo),), keep_tags=KEEP_TAGS).execute()

        assert result.success is True
        assert result.output == "Processed 1 file(s)"
        assert run_mock.call_count == 1  # only exiftool strip, no date phase

    def test_missing_datetime_original(self, mocker, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.touch()

        mocker.patch("puc.commands.strip.strip.sys.platform", "darwin")

        def which_side_effect(cmd):
            if cmd == "exiftool":
                return "/usr/local/bin/exiftool"
            if cmd == "SetFile":
                return "/usr/bin/SetFile"
            return None

        mocker.patch("puc.commands.strip.strip.shutil.which", side_effect=which_side_effect)

        call_count = 0

        def run_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # exiftool read date - empty result
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        mocker.patch("puc.commands.strip.strip.subprocess.run", side_effect=run_side_effect)

        result = CommandStrip(files=(str(photo),), keep_tags=KEEP_TAGS).execute()

        assert result.success is True
        assert any("no DateTimeOriginal" in w for w in result.warnings)
        assert result.output == "Processed 1 file(s)"

    def test_strip_failure(self, mocker, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.touch()

        mocker.patch("puc.commands.strip.strip.sys.platform", "linux")
        mocker.patch("puc.commands.strip.strip.shutil.which", return_value="/usr/bin/exiftool")
        mocker.patch(
            "puc.commands.strip.strip.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="write error"),
        )

        result = CommandStrip(files=(str(photo),), keep_tags=KEEP_TAGS).execute()

        assert result.success is True
        assert result.output == "Processed 0 file(s)"
        assert any("failed to strip" in w for w in result.warnings)

    def test_multiple_files_mixed_results(self, mocker, tmp_path) -> None:
        good = tmp_path / "good.jpg"
        bad = tmp_path / "bad.jpg"
        good.touch()
        bad.touch()

        mocker.patch("puc.commands.strip.strip.sys.platform", "linux")
        mocker.patch("puc.commands.strip.strip.shutil.which", return_value="/usr/bin/exiftool")

        call_count = 0

        def run_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # first file succeeds
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="error")

        mocker.patch("puc.commands.strip.strip.subprocess.run", side_effect=run_side_effect)

        result = CommandStrip(files=(str(good), str(bad)), keep_tags=KEEP_TAGS).execute()

        assert result.success is True
        assert result.output == "Processed 1 file(s)"
        assert len(result.warnings) == 1

    def test_missing_setfile_on_macos(self, mocker, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.touch()

        mocker.patch("puc.commands.strip.strip.sys.platform", "darwin")

        def which_side_effect(cmd):
            if cmd == "exiftool":
                return "/usr/local/bin/exiftool"
            return None  # SetFile not found

        mocker.patch("puc.commands.strip.strip.shutil.which", side_effect=which_side_effect)
        mocker.patch(
            "puc.commands.strip.strip.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        )

        result = CommandStrip(files=(str(photo),), keep_tags=KEEP_TAGS).execute()

        assert result.success is True
        assert any("SetFile not found" in w for w in result.warnings)

    def test_setfile_failure(self, mocker, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.touch()

        mocker.patch("puc.commands.strip.strip.sys.platform", "darwin")

        def which_side_effect(cmd):
            if cmd == "exiftool":
                return "/usr/local/bin/exiftool"
            if cmd == "SetFile":
                return "/usr/bin/SetFile"
            return None

        mocker.patch("puc.commands.strip.strip.shutil.which", side_effect=which_side_effect)

        call_count = 0

        def run_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # exiftool read date - success
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="01/15/2024 10:30:00\n", stderr="")
            if call_count == 2:  # SetFile - failure
                return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        mocker.patch("puc.commands.strip.strip.subprocess.run", side_effect=run_side_effect)

        result = CommandStrip(files=(str(photo),), keep_tags=KEEP_TAGS).execute()

        assert result.success is True
        assert result.output == "Processed 1 file(s)"
        assert any("failed to set creation date" in w for w in result.warnings)

    def test_keep_tags_passed_to_exiftool(self, mocker, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.touch()

        mocker.patch("puc.commands.strip.strip.sys.platform", "linux")
        mocker.patch("puc.commands.strip.strip.shutil.which", return_value="/usr/bin/exiftool")
        run_mock = mocker.patch(
            "puc.commands.strip.strip.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        )

        custom_tags = ["Copyright", "Artist"]
        CommandStrip(files=(str(photo),), keep_tags=custom_tags).execute()

        strip_call_args = run_mock.call_args[0][0]
        assert "-Copyright" in strip_call_args
        assert "-Artist" in strip_call_args
        assert "-all=" in strip_call_args
        assert "-tagsfromfile" in strip_call_args
