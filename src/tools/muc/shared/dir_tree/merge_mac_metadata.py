from __future__ import annotations

import ctypes
import logging
import os
import struct
import sys
from pathlib import Path

from .safe_rglob import safe_rglob

logger = logging.getLogger(__name__)

# AppleDouble layout (RFC 1740 plus Apple's packed-xattr extension used by copyfile).
_MAGIC = 0x00051607
_HEADER_SIZE = 26  # magic, version, 16-byte filler, entry count
_ENTRY_SIZE = 12  # id, offset, length
_RESOURCE_FORK_ID = 2
_FINDER_INFO_ID = 9
_FINDER_INFO_SIZE = 32
_ATTR_MAGIC = b"ATTR"
_ATTR_HEADER_SIZE = 36  # magic, debug tag, total, data start, data length, 3 reserved, flags, count
_ATTR_ENTRY_SIZE = 11  # offset, length, flags, name length

if sys.platform == "darwin":
    # macOS has setxattr(2) but Python's os module does not expose it there.
    _libc = ctypes.CDLL(None, use_errno=True)
    _libc.setxattr.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_size_t,
        ctypes.c_uint32,
        ctypes.c_int,
    ]
    _libc.setxattr.restype = ctypes.c_int


def parse_apple_double(data: bytes) -> list[tuple[str, bytes]]:
    """Return the extended attributes an AppleDouble file carries for its data file.

    Yields the Finder info (unless all zero), the resource fork (unless empty),
    and every attribute macOS packed after the Finder info.

    Raises:
        ValueError: ``data`` is not a well-formed AppleDouble file.
    """
    if len(data) < _HEADER_SIZE or struct.unpack_from(">I", data)[0] != _MAGIC:
        raise ValueError("not an AppleDouble file")
    try:
        (count,) = struct.unpack_from(">H", data, _HEADER_SIZE - 2)
        attrs: list[tuple[str, bytes]] = []
        for index in range(count):
            entry_id, offset, length = struct.unpack_from(">III", data, _HEADER_SIZE + _ENTRY_SIZE * index)
            _check_range(data, offset, length)
            if entry_id == _RESOURCE_FORK_ID and length:
                attrs.append(("com.apple.ResourceFork", data[offset : offset + length]))
            elif entry_id == _FINDER_INFO_ID and length >= _FINDER_INFO_SIZE:
                finder_info = data[offset : offset + _FINDER_INFO_SIZE]
                if any(finder_info):
                    attrs.append(("com.apple.FinderInfo", finder_info))
                attrs.extend(_packed_attrs(data, offset + _FINDER_INFO_SIZE, offset + length))
    except struct.error as exc:
        raise ValueError(f"truncated AppleDouble file: {exc}") from exc
    return attrs


def _packed_attrs(data: bytes, start: int, end: int) -> list[tuple[str, bytes]]:
    """Read the ``ATTR`` block macOS appends to the Finder info entry, if any."""
    start = (start + 3) & ~3  # the header is 4-byte aligned after the Finder info
    if end - start < _ATTR_HEADER_SIZE or data[start : start + 4] != _ATTR_MAGIC:
        return []
    (count,) = struct.unpack_from(">H", data, start + _ATTR_HEADER_SIZE - 2)
    attrs: list[tuple[str, bytes]] = []
    pos = start + _ATTR_HEADER_SIZE
    for _ in range(count):
        offset, length, _flags, name_length = struct.unpack_from(">IIHB", data, pos)
        name_start = pos + _ATTR_ENTRY_SIZE
        _check_range(data, name_start, name_length)
        _check_range(data, offset, length)
        name = data[name_start : name_start + name_length].rstrip(b"\0").decode()
        attrs.append((name, data[offset : offset + length]))
        pos = (name_start + name_length + 3) & ~3
    return attrs


def _check_range(data: bytes, offset: int, length: int) -> None:
    if offset + length > len(data):
        raise ValueError("AppleDouble entry points past end of file")


def _setxattr(path: Path, name: str, value: bytes) -> None:
    """Set one extended attribute, replacing any existing value."""
    if sys.platform == "darwin":
        if _libc.setxattr(os.fsencode(path), name.encode(), value, len(value), 0, 0) != 0:
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err), str(path))
        return
    os.setxattr(path, name, value)


def merge_mac_metadata(directory: Path) -> None:
    """Clean Mac metadata by merging extended attributes and removing ._ files.

    Mimics the behavior of 'dot_clean -mn':
    - For each ._ file, restores the metadata it carries (Finder info, resource
      fork, extended attributes) onto the corresponding data file.
    - If merging is successful, removes the ._ file.
    - If merging fails or the ._ file is not valid AppleDouble, keeps it.
    - If there's no corresponding data file, removes the ._ file.

    Args:
        directory: Path to the directory to process.
    """
    for apple_double in safe_rglob(directory, "._*"):
        if apple_double.is_file():
            data_file = apple_double.with_name(apple_double.name[2:])
            if os.name != "nt" and data_file.exists():
                try:
                    for name, value in parse_apple_double(apple_double.read_bytes()):
                        _setxattr(data_file, name, value)
                    apple_double.unlink()
                    logger.info(
                        "Merged metadata from %s to %s",
                        apple_double,
                        data_file,
                    )
                except (OSError, ValueError) as exc:
                    logger.warning("Kept %s: %s", apple_double, exc)
            else:
                # If there's no corresponding data file, just remove the ._ file
                try:
                    apple_double.unlink()
                    logger.info("Deleted %s", apple_double)
                except OSError:
                    pass
