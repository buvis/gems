from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from braid.commands.compose.compose import CommandCompose
from braid.domain.engine import ComposeRequest, Mode

from tests.tools.braid.helpers import make_skill


def snapshot(root: Path) -> dict:
    """Capture contents and identity without following links or reading special files."""
    return {
        str(path.relative_to(root)): (
            (stat.st_mode, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns),
            os.readlink(path) if path.is_symlink() else path.read_bytes() if path.is_file() else None,
        )
        for path in root.rglob("*")
        for stat in [path.lstat()]
    }


def invoke_braid(config: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "braid", "--config", str(config), *args],
        capture_output=True,
        text=True,
        timeout=10,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


@pytest.fixture
def request_with_skill(tmp_path: Path) -> ComposeRequest:
    source = tmp_path / "source"
    make_skill(source, "portable")
    return ComposeRequest(
        agents_root=Path.home() / ".agents",
        claude_root=Path.home() / ".claude",
        configured_sources=(source,),
    )


@pytest.mark.parametrize("key", ["sources", "policies"])
@pytest.mark.parametrize("entry", ["~nosuchuser_agoge/x", "/invalid\0path"], ids=["unknown-user", "nul"])
class TestMalformedConfiguredPaths:
    def test_command_returns_error_without_changing_existing_links(
        self, tmp_path: Path, request_with_skill: ComposeRequest, key: str, entry: str
    ) -> None:
        assert CommandCompose(request_with_skill).execute().success
        before = snapshot(tmp_path)
        request = replace(request_with_skill, **{f"configured_{key}": (Path(entry),)})

        result = CommandCompose(request).execute()

        assert not result.success
        assert result.metadata["exit_code"] == 2
        assert key in result.error
        assert repr(entry) in result.error
        assert snapshot(tmp_path) == before

    @pytest.mark.parametrize("mode", [Mode.SYNC, Mode.DRY_RUN, Mode.CHECK])
    def test_real_cli_exits_cleanly_without_filesystem_changes(
        self, tmp_path: Path, request_with_skill: ComposeRequest, key: str, entry: str, mode: Mode
    ) -> None:
        config = tmp_path / "braid.yaml"
        config.write_text(yaml.safe_dump({"sources": [str(request_with_skill.configured_sources[0])], key: [entry]}))
        before = snapshot(tmp_path)

        result = invoke_braid(config, *([] if mode is Mode.SYNC else [f"--{mode.value}"]))

        assert result.returncode == 2, result.stdout + result.stderr
        assert "Traceback" not in result.stdout + result.stderr
        assert key in result.stdout
        assert repr(entry) in result.stdout
        assert snapshot(tmp_path) == before
