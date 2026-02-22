from __future__ import annotations

from unittest.mock import patch

from muc.commands.tidy.tidy import CommandTidy


class TestCommandTidy:
    def test_execute_calls_all_dirtree_methods(self, tmp_path) -> None:
        junk = [".txt", ".nfo"]

        with patch("muc.commands.tidy.tidy.DirTree") as mock_dirtree:
            cmd = CommandTidy(directory=tmp_path, junk_extensions=junk)
            cmd.execute()

        mock_dirtree.merge_mac_metadata.assert_called_once_with(tmp_path)
        mock_dirtree.normalize_file_extensions.assert_called_once_with(tmp_path)
        mock_dirtree.delete_by_extension.assert_called_once_with(tmp_path, junk)
        mock_dirtree.remove_empty_directories.assert_called_once_with(tmp_path)

    def test_execute_calls_in_order(self, tmp_path) -> None:
        junk = [".log"]
        call_order: list[str] = []

        with patch("muc.commands.tidy.tidy.DirTree") as mock_dirtree:
            mock_dirtree.merge_mac_metadata.side_effect = lambda d: call_order.append("merge_mac_metadata")
            mock_dirtree.normalize_file_extensions.side_effect = lambda d: call_order.append("normalize")
            mock_dirtree.delete_by_extension.side_effect = lambda d, e: call_order.append("delete")
            mock_dirtree.remove_empty_directories.side_effect = lambda d: call_order.append("remove_empty")

            cmd = CommandTidy(directory=tmp_path, junk_extensions=junk)
            cmd.execute()

        assert call_order == ["merge_mac_metadata", "normalize", "delete", "remove_empty"]

    def test_execute_returns_none(self, tmp_path) -> None:
        with patch("muc.commands.tidy.tidy.DirTree"):
            cmd = CommandTidy(directory=tmp_path, junk_extensions=[])
            result = cmd.execute()

        assert result is None

    def test_stores_directory_and_extensions(self, tmp_path) -> None:
        junk = [".cue", ".m3u"]

        cmd = CommandTidy(directory=tmp_path, junk_extensions=junk)

        assert cmd.dir == tmp_path
        assert cmd.junk_extensions == junk

    def test_empty_junk_extensions(self, tmp_path) -> None:
        with patch("muc.commands.tidy.tidy.DirTree") as mock_dirtree:
            cmd = CommandTidy(directory=tmp_path, junk_extensions=[])
            cmd.execute()

        mock_dirtree.delete_by_extension.assert_called_once_with(tmp_path, [])


class TestCommandTidyIntegration:
    def test_removes_junk_and_empty_dirs(self, tmp_path) -> None:
        music_dir = tmp_path / "album"
        music_dir.mkdir()
        (music_dir / "track.mp3").touch()
        (music_dir / "cover.jpg").touch()
        (music_dir / "info.nfo").touch()
        empty_dir = music_dir / "extras"
        empty_dir.mkdir()

        cmd = CommandTidy(directory=music_dir, junk_extensions=[".jpg", ".nfo"])
        cmd.execute()

        assert (music_dir / "track.mp3").exists()
        assert not (music_dir / "cover.jpg").exists()
        assert not (music_dir / "info.nfo").exists()
        assert not empty_dir.exists()
