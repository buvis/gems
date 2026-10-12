from __future__ import annotations

from pathlib import Path

import pytest
from dot.commands.links.links import CommandLinkStatus
from dot.hostlinks import MANIFEST_PATH, reconcile_links


def write_manifest(root: Path, *lines: str) -> None:
    manifest = root / MANIFEST_PATH
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("\n".join(lines) + "\n")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    dotroot = tmp_path / "dotroot"
    (dotroot / "hosts" / "h1").mkdir(parents=True)
    (dotroot / "hosts" / "h1" / "bashrc").write_text("export A=1\n")
    return dotroot


class TestCommandLinkStatus:
    def test_warns_when_host_file_missing(self, root: Path) -> None:
        write_manifest(root, ".gone => hosts/h1/gone")

        result = CommandLinkStatus(str(root)).execute()

        assert result.success is True
        assert result.warnings == [".gone: no host file at hosts/h1/gone"]

    def test_warns_about_missing_link_without_creating_it(self, root: Path) -> None:
        write_manifest(root, ".bashrc => hosts/h1/bashrc")

        result = CommandLinkStatus(str(root)).execute()

        assert result.success is True
        assert result.warnings == [".bashrc: link missing; run 'dot materialize'"]
        assert not (root / ".bashrc").is_symlink()
        assert not (root / ".bashrc").exists()

    def test_current_link_has_no_warnings(self, root: Path) -> None:
        write_manifest(root, ".bashrc => hosts/h1/bashrc")
        reconcile_links(root, apply=True)

        result = CommandLinkStatus(str(root)).execute()

        assert result.success is True
        assert result.warnings == []
        assert (root / ".bashrc").is_symlink()

    def test_no_manifest_has_no_warnings(self, tmp_path: Path) -> None:
        result = CommandLinkStatus(str(tmp_path)).execute()

        assert result.success is True
        assert result.warnings == []

    def test_info_is_always_empty(self, root: Path) -> None:
        write_manifest(root, ".bashrc => hosts/h1/bashrc", ".gone => hosts/h1/gone")

        result = CommandLinkStatus(str(root)).execute()

        assert result.info == []
        assert result.success is True
        assert len(result.warnings) == 2
