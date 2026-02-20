from __future__ import annotations

from pathlib import Path

from fren.commands.flatten.flatten import CommandFlatten


class TestFlattenBasic:
    def test_copies_nested_files(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        destination = tmp_path / "dest"
        (source / "a" / "b").mkdir(parents=True)
        (source / "c").mkdir()
        (source / "a" / "b" / "file.txt").write_text("one")
        (source / "c" / "other.txt").write_text("two")

        CommandFlatten(source=str(source), destination=str(destination)).execute()

        assert (destination / "file.txt").exists()
        assert (destination / "other.txt").exists()

    def test_creates_destination(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        destination = tmp_path / "new-dest"
        source.mkdir()
        (source / "file.txt").write_text("x")

        CommandFlatten(source=str(source), destination=str(destination)).execute()

        assert destination.exists()
        assert (destination / "file.txt").exists()

    def test_preserves_content(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        destination = tmp_path / "dest"
        source.mkdir()
        content = "same-content"
        (source / "file.txt").write_text(content)

        CommandFlatten(source=str(source), destination=str(destination)).execute()

        assert (destination / "file.txt").read_text() == content

    def test_skips_hidden_files(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        destination = tmp_path / "dest"
        source.mkdir()
        (source / ".hidden.txt").write_text("x")

        result = CommandFlatten(source=str(source), destination=str(destination)).execute()

        assert not (destination / ".hidden.txt").exists()
        assert result.output == f"Copied 0 file(s) to {destination}"


class TestFlattenCollision:
    def test_collision_suffix(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        destination = tmp_path / "dest"
        (source / "a").mkdir(parents=True)
        (source / "b").mkdir(parents=True)
        (source / "a" / "file.txt").write_text("one")
        (source / "b" / "file.txt").write_text("two")

        CommandFlatten(source=str(source), destination=str(destination)).execute()

        assert (destination / "file.txt").exists()
        assert (destination / "file-1.txt").exists()

    def test_multiple_collision_suffix(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        destination = tmp_path / "dest"
        (source / "a").mkdir(parents=True)
        (source / "b").mkdir(parents=True)
        (source / "c").mkdir(parents=True)
        (source / "a" / "file.txt").write_text("one")
        (source / "b" / "file.txt").write_text("two")
        (source / "c" / "file.txt").write_text("three")

        CommandFlatten(source=str(source), destination=str(destination)).execute()

        assert (destination / "file.txt").exists()
        assert (destination / "file-1.txt").exists()
        assert (destination / "file-2.txt").exists()


class TestFlattenMetadata:
    def test_preserves_mtime(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        destination = tmp_path / "dest"
        source.mkdir()
        original = source / "file.txt"
        original.write_text("x")

        mtime_ns = 1_700_000_000_123_456_789
        original.touch()
        original.chmod(0o644)
        import os

        os.utime(original, ns=(mtime_ns, mtime_ns))

        CommandFlatten(source=str(source), destination=str(destination)).execute()

        copied = destination / "file.txt"
        assert copied.exists()
        assert copied.stat().st_mtime_ns == original.stat().st_mtime_ns
