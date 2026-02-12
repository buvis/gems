"""
This module contains pytest tests for CommandTidy

Imports:
    pytest: Used for creating and running tests.
    pathlib: Used for object-oriented filesystem path operations.
    remove_music_junk: The module we're testing.
"""

import pytest
from buvis.pybase.filesystem import DirTree


@pytest.fixture
def temp_music_dir(tmp_path):
    """
    Create a temporary directory structure for testing.

    :param tmp_path: Pytest fixture that provides a temporary directory
    :type tmp_path: :class:`Path`
    :return: Path to the temporary music directory
    :rtype: :class:`Path`
    """
    music_dir = tmp_path / "media" / "music-inbox"
    music_dir.mkdir(parents=True)

    # Create test files
    (music_dir / "song1.MP3").touch()
    (music_dir / "song2.mp3").touch()
    (music_dir / "cover.JPG").touch()
    (music_dir / "image.jfif").touch()
    (music_dir / "info.TXT").touch()
    (music_dir / "playlist.m3u").touch()

    # Create an empty directory
    (music_dir / "empty_dir").mkdir()

    return music_dir


def test_normalize_file_extensions(temp_music_dir):
    """
    Test the normalize_file_extensions function.

    :param temp_music_dir: Temporary music directory
    :type temp_music_dir: :class:`Path`
    """
    DirTree.normalize_file_extensions(temp_music_dir)

    assert (temp_music_dir / "song1.mp3").exists()
    assert (temp_music_dir / "song2.mp3").exists()
    assert (temp_music_dir / "image.jpg").exists()
    assert not any(f.name == "song1.MP3" for f in temp_music_dir.iterdir())
    assert not any(f.name == "image.jfif" for f in temp_music_dir.iterdir())


def test_delete_specific_files(temp_music_dir):
    """
    Test the delete_specific_files function.

    :param temp_music_dir: Temporary music directory
    :type temp_music_dir: :class:`Path`
    """
    junk = [".jpg", ".txt", ".m3u"]
    DirTree.delete_by_extension(temp_music_dir, junk)

    assert (temp_music_dir / "song1.MP3").exists()
    assert (temp_music_dir / "song2.mp3").exists()
    assert not (temp_music_dir / "cover.JPG").exists()
    assert not (temp_music_dir / "info.TXT").exists()
    assert not (temp_music_dir / "playlist.m3u").exists()


def test_remove_empty_directories(temp_music_dir):
    """
    Test the remove_empty_directories function.

    :param temp_music_dir: Temporary music directory
    :type temp_music_dir: :class:`Path`
    """
    DirTree.remove_empty_directories(temp_music_dir)

    assert not (temp_music_dir / "empty_dir").exists()
