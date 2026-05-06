from __future__ import annotations

import hashlib
from pathlib import Path

from bim.commands.doc.shared.hashing import sha256_file


class TestSha256File:
    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty"
        f.write_bytes(b"")
        assert sha256_file(f) == hashlib.sha256(b"").hexdigest()

    def test_single_block(self, tmp_path: Path) -> None:
        data = b"hello world"
        f = tmp_path / "small"
        f.write_bytes(data)
        assert sha256_file(f) == hashlib.sha256(data).hexdigest()

    def test_multi_block(self, tmp_path: Path) -> None:
        # Larger than _BLOCK_SIZE (64 KiB) to exercise multiple read iterations.
        data = b"A" * (200 * 1024)  # 200 KiB
        f = tmp_path / "large"
        f.write_bytes(data)
        assert sha256_file(f) == hashlib.sha256(data).hexdigest()

    def test_known_digest(self, tmp_path: Path) -> None:
        data = b"abc"
        f = tmp_path / "abc"
        f.write_bytes(data)
        # sha256("abc") = ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
        assert sha256_file(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
