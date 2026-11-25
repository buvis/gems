from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from muc.shared.dir_tree.merge_mac_metadata import merge_mac_metadata, parse_apple_double

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="extended attributes are not merged on Windows",
)

# Written by macOS bsdtar (copyfile) for a file carrying Finder info, a
# resource fork and three extended attributes.
FIXTURE = (Path(__file__).parent / "fixtures" / "apple_double_track.flac.bin").read_bytes()
FINDER_INFO = bytes(8) + b"\x00\x04" + bytes(22)
FIXTURE_ATTRS = {
    "com.apple.FinderInfo": FINDER_INFO,
    "com.apple.ResourceFork": b"RSRCDATA",
    "com.apple.metadata:kMDItemWhereFroms": b"from-web",
    "com.apple.provenance": b"\x01\x02\x00\x30\xb5\x50\x84\xb3\x8b\xa2\xdd",
    "com.example.tag": b"hello",
}
SETXATTR = "muc.shared.dir_tree.merge_mac_metadata._setxattr"


class TestParseAppleDouble:
    def test_reads_finder_info_resource_fork_and_packed_attributes(self) -> None:
        assert dict(parse_apple_double(FIXTURE)) == FIXTURE_ATTRS

    def test_omits_all_zero_finder_info(self) -> None:
        data = FIXTURE[:0x32] + bytes(32) + FIXTURE[0x52:]

        assert "com.apple.FinderInfo" not in dict(parse_apple_double(data))

    def test_rejects_non_apple_double(self) -> None:
        with pytest.raises(ValueError, match="not an AppleDouble"):
            parse_apple_double(b"resource fork data that is not AppleDouble")

    def test_rejects_truncated_file(self) -> None:
        with pytest.raises(ValueError):
            parse_apple_double(FIXTURE[:0xA0])


class TestMergeMacMetadata:
    """Tests for merge_mac_metadata function."""

    def test_orphan_apple_double_is_removed(self, tmp_path: Path) -> None:
        """Orphan ._ files (no data file) are removed."""
        apple_double = tmp_path / "._orphan.txt"
        apple_double.write_bytes(b"\x00\x05\x16\x07")

        merge_mac_metadata(tmp_path)

        assert not apple_double.exists()

    def test_merge_restores_every_attribute_and_removes_apple_double(self, tmp_path: Path) -> None:
        data_file = tmp_path / "track.flac"
        data_file.write_bytes(b"song")
        apple_double = tmp_path / "._track.flac"
        apple_double.write_bytes(FIXTURE)

        with patch(SETXATTR) as mock_setxattr:
            result = merge_mac_metadata(tmp_path)

        written = {call.args[1]: call.args[2] for call in mock_setxattr.call_args_list}
        assert written == FIXTURE_ATTRS
        assert {call.args[0] for call in mock_setxattr.call_args_list} == {data_file}
        assert not apple_double.exists()
        assert result.info == [f"Merged metadata from {apple_double} to {data_file}"]
        assert result.warnings == []

    def test_never_writes_metadata_through_a_symlinked_data_file(self, tmp_path: Path) -> None:
        victim = tmp_path / "outside" / "victim.flac"
        victim.parent.mkdir()
        victim.write_bytes(b"song")
        tree = tmp_path / "tree"
        tree.mkdir()
        link = tree / "track.flac"
        link.symlink_to(victim)
        apple_double = tree / "._track.flac"
        apple_double.write_bytes(FIXTURE)

        with patch(SETXATTR) as mock_setxattr:
            result = merge_mac_metadata(tree)

        mock_setxattr.assert_not_called()
        assert apple_double.exists()
        assert result.warnings == [f"Kept {apple_double}: {link} is a symlink"]

    def test_non_apple_double_file_is_kept(self, tmp_path: Path, caplog) -> None:
        """A ._ file that is not AppleDouble is not written into the data file."""
        data_file = tmp_path / "photo.jpg"
        data_file.write_bytes(b"\xff\xd8\xff")
        apple_double = tmp_path / "._photo.jpg"
        apple_double.write_bytes(b"resource fork data")

        with patch(SETXATTR) as mock_setxattr:
            result = merge_mac_metadata(tmp_path)

        mock_setxattr.assert_not_called()
        assert apple_double.exists()
        assert result.info == []
        assert result.warnings == [f"Kept {apple_double}: not an AppleDouble file"]
        assert caplog.records == []

    def test_oserror_on_setxattr_keeps_apple_double(self, tmp_path: Path) -> None:
        data_file = tmp_path / "photo.jpg"
        data_file.write_bytes(b"\xff\xd8\xff")
        apple_double = tmp_path / "._photo.jpg"
        apple_double.write_bytes(FIXTURE)

        with patch(SETXATTR, side_effect=OSError("xattr failed")):
            result = merge_mac_metadata(tmp_path)

        assert apple_double.exists()
        assert data_file.exists()
        assert result.info == []
        assert result.warnings == [f"Kept {apple_double}: xattr failed"]

    def test_oserror_on_unlink_orphan_is_caught(self, tmp_path: Path) -> None:
        """OSError during orphan ._ file deletion is caught."""
        apple_double = tmp_path / "._orphan.txt"
        apple_double.write_bytes(b"\x00")

        original_unlink = Path.unlink

        def mock_unlink(self, *args, **kwargs):
            if self.name.startswith("._"):
                raise OSError("busy")
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", mock_unlink):
            result = merge_mac_metadata(tmp_path)

        assert result.warnings == [f"Kept {apple_double}: busy"]
        assert result.info == []

    def test_skips_non_file_apple_double(self, tmp_path: Path) -> None:
        """Directories named ._ are not processed."""
        apple_dir = tmp_path / "._subdir"
        apple_dir.mkdir()

        merge_mac_metadata(tmp_path)

        assert apple_dir.exists()

    def test_nested_apple_double(self, tmp_path: Path) -> None:
        """Recursively finds ._ files in subdirectories."""
        sub = tmp_path / "sub"
        sub.mkdir()
        apple_double = sub / "._nested.txt"
        apple_double.write_bytes(b"\x00")

        merge_mac_metadata(tmp_path)

        assert not apple_double.exists()
