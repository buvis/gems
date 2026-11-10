from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from muc.cli import cli
from muc.commands.tidy.tidy import CommandTidy
from muc.shared.dir_tree.delete_by_extension import delete_by_extension
from muc.shared.dir_tree.lowercase_file_extensions import lowercase_file_extensions
from muc.shared.dir_tree.merge_mac_metadata import merge_mac_metadata
from muc.shared.dir_tree.remove_empty_directories import remove_empty_directories
from muc.shared.dir_tree.rename_equivalent_extensions import rename_equivalent_extensions


class TestTidyReporting:
    def test_reports_actions_from_every_stage(self, tmp_path):
        (tmp_path / "._orphan").touch()
        (tmp_path / "track.MP2").touch()
        (tmp_path / "info.nfo").touch()
        (tmp_path / "empty").mkdir()

        result = CommandTidy(tmp_path, [".nfo"]).execute()

        assert result.success
        assert result.warnings == []
        assert result.info == [
            f"Deleted {tmp_path / '._orphan'}",
            f"Renamed {tmp_path / 'track.MP2'} -> track.mp2",
            f"Renamed {tmp_path / 'track.mp2'} -> track.mp3",
            f"Removed extra file {tmp_path / 'info.nfo'}",
            f"Removed empty directory {tmp_path / 'empty'}",
        ]
        assert (tmp_path / "track.mp3").exists()

    @pytest.mark.parametrize(
        ("operation", "args", "filename", "other_name", "method"),
        [
            (lowercase_file_extensions, (), "track.MP3", "other.MP3", "rename"),
            (rename_equivalent_extensions, ([["mp3", "mp2"]],), "track.mp2", "other.mp2", "rename"),
            (delete_by_extension, ([".nfo"],), "info.nfo", "other.nfo", "unlink"),
            (merge_mac_metadata, (), "._orphan", "._other", "unlink"),
        ],
    )
    def test_file_failure_is_reported_and_other_files_continue(
        self, tmp_path, operation, args, filename, other_name, method
    ):
        blocked = tmp_path / filename
        blocked.touch()
        other = tmp_path / other_name
        other.touch()
        original = getattr(Path, method)

        def fail_one(path, *args, **kwargs):
            if path == blocked:
                raise OSError("busy")
            return original(path, *args, **kwargs)

        with patch.object(Path, method, autospec=True, side_effect=fail_one):
            result = operation(tmp_path, *args)

        assert result.success
        assert len(result.warnings) == 1
        assert str(blocked) in result.warnings[0]
        assert "busy" in result.warnings[0]
        assert len(result.info) == 1
        assert blocked.exists()

    @pytest.mark.parametrize("method", ["rmdir", "iterdir"])
    def test_directory_failure_is_reported_and_cleanup_continues(self, tmp_path, method):
        blocked = tmp_path / "blocked"
        blocked.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        original = getattr(Path, method)

        def fail_one(path, *args, **kwargs):
            if path == blocked:
                raise OSError("busy")
            return original(path, *args, **kwargs)

        with patch.object(Path, method, autospec=True, side_effect=fail_one):
            result = remove_empty_directories(tmp_path)

        assert result.warnings == [f"Could not remove empty directory {blocked}: busy"]
        assert result.info == [f"Removed empty directory {other}"]
        assert blocked.exists()
        assert not other.exists()

    def test_cli_renders_actions_and_warnings_without_failing(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "track.mp3").touch()
        (tmp_path / "[bold].txt").touch()
        (tmp_path / "empty").mkdir()
        original = Path.unlink

        def fail_junk(path, *args, **kwargs):
            if path.name == "[bold].txt":
                raise OSError("busy")
            return original(path, *args, **kwargs)

        with patch.object(Path, "unlink", autospec=True, side_effect=fail_junk):
            result = runner.invoke(cli, ["tidy", "-y", "."])

        assert result.exit_code == 0
        assert "Could not remove" in result.output
        assert "busy" in result.output
        assert "[bold].txt" in result.output
        assert "Removed empty directory" in result.output
        assert "Tidied" in result.output
        assert not (tmp_path / "empty").exists()

    def test_no_changes_has_no_actions_or_warnings(self, tmp_path):
        (tmp_path / "track.mp3").touch()

        result = CommandTidy(tmp_path, []).execute()

        assert result.success
        assert result.info == []
        assert result.warnings == []

    def test_cli_preserves_brackets_in_filenames(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "[bold].TXT").touch()

        result = runner.invoke(cli, ["tidy", "-y", "."])

        assert result.exit_code == 0
        assert "[bold].TXT" in result.output
        assert "[bold].txt" in result.output

    def test_normalization_warnings_reach_command_result(self, tmp_path):
        track = tmp_path / "track.MP2"
        track.touch()
        (tmp_path / "empty").mkdir()

        with patch.object(Path, "rename", autospec=True, side_effect=OSError("busy")):
            result = CommandTidy(tmp_path, []).execute()

        assert result.success
        assert result.warnings == [
            f"Could not lowercase extension of {track}: busy",
            f"Could not normalize extension of {track}: busy",
        ]
        assert result.info == [f"Removed empty directory {tmp_path / 'empty'}"]
