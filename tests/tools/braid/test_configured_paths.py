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


def link_snapshot(root: Path) -> dict:
    return {
        str(path): (stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns, os.readlink(path))
        for path in root.rglob("*")
        if path.is_symlink()
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


@pytest.fixture(params=["missing", "directory", "fifo", "device"])
def non_file_policy(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    path = tmp_path / "[red]policy"
    if request.param == "directory":
        path.mkdir()
    elif request.param == "fifo":
        if not hasattr(os, "mkfifo"):
            pytest.skip("FIFOs are unavailable")
        os.mkfifo(path)
    elif request.param == "device":
        path = Path("/dev/zero")
        if not path.is_char_device():
            pytest.skip("/dev/zero is unavailable")
    return path


class TestOptionalPolicies:
    @pytest.mark.parametrize("key", ["configured_policies", "policies"])
    def test_command_warns_without_reading_non_files_or_changing_links(
        self,
        tmp_path: Path,
        request_with_skill: ComposeRequest,
        non_file_policy: Path,
        monkeypatch: pytest.MonkeyPatch,
        key: str,
    ) -> None:
        assert CommandCompose(request_with_skill).execute().success
        before = link_snapshot(tmp_path)
        state = request_with_skill.agents_root / ".braid-state.json"
        previous_state = state.read_bytes()
        original_open = Path.open

        def guarded_open(path: Path, *args, **kwargs):
            assert path.resolve() != non_file_policy.resolve(), "must not open a non-file policy"
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(Path, "open", guarded_open)
        request = replace(request_with_skill, **{key: (non_file_policy,)})

        result = CommandCompose(request).execute()

        assert result.success
        assert result.metadata["exit_code"] == 0
        assert result.metadata["drift"] == 0
        assert len(result.warnings) == 1
        assert str(non_file_policy) in result.warnings[0]
        assert "not a regular file" in result.warnings[0]
        assert link_snapshot(tmp_path) == before
        assert state.read_bytes() == previous_state

    @pytest.mark.parametrize("via_cli", [False, True], ids=["yaml", "cli-option"])
    @pytest.mark.parametrize("mode", [Mode.SYNC, Mode.DRY_RUN, Mode.CHECK])
    def test_real_cli_warns_and_finishes_without_changing_links(
        self,
        tmp_path: Path,
        request_with_skill: ComposeRequest,
        non_file_policy: Path,
        via_cli: bool,
        mode: Mode,
    ) -> None:
        config = tmp_path / "braid.yaml"
        values = {"sources": [str(request_with_skill.configured_sources[0])]}
        config.write_text(yaml.safe_dump(values))
        assert invoke_braid(config).returncode == 0
        args = [] if mode is Mode.SYNC else [f"--{mode.value}"]
        if via_cli:
            args.extend(["--policy", str(non_file_policy)])
        else:
            values["policies"] = [str(non_file_policy)]
            config.write_text(yaml.safe_dump(values))
        before = link_snapshot(tmp_path)
        state = request_with_skill.agents_root / ".braid-state.json"
        previous_state = state.read_bytes()

        result = invoke_braid(config, *args)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Traceback" not in result.stdout + result.stderr
        assert "⚠" in result.stdout, result.stdout
        assert str(non_file_policy) in result.stdout
        assert "not a regular file" in result.stdout
        assert "0 change(s)" in result.stdout or "0 drift" in result.stdout
        assert link_snapshot(tmp_path) == before
        assert state.read_bytes() == previous_state

    def test_absent_implicit_policies_are_silent(self, request_with_skill: ComposeRequest) -> None:
        result = CommandCompose(request_with_skill).execute()

        assert result.success
        assert result.warnings == []

    def test_warning_does_not_prevent_sync_or_valid_policy_loading(
        self, tmp_path: Path, request_with_skill: ComposeRequest
    ) -> None:
        policy = tmp_path / "valid.braidignore"
        policy.write_text("portable\n")
        missing = tmp_path / "missing.braidignore"
        request = replace(request_with_skill, configured_policies=(missing, policy), policies=(missing,))

        result = CommandCompose(request).execute()

        assert result.success
        assert len(result.warnings) == 1
        assert str(missing) in result.warnings[0]
        assert (request.agents_root / "skills" / "portable").is_symlink()
        assert not (request.claude_root / "skills" / "portable").exists()
        assert "1 ignored" in result.output

    def test_warnings_survive_a_later_sync_failure(self, tmp_path: Path, request_with_skill: ComposeRequest) -> None:
        other = tmp_path / "other-source"
        make_skill(other, "portable")
        missing = tmp_path / "missing.braidignore"
        request = replace(request_with_skill, sources=(other,), configured_policies=(missing,))

        result = CommandCompose(request).execute()

        assert not result.success
        assert result.metadata["exit_code"] == 2
        assert len(result.warnings) == 1
        assert str(missing) in result.warnings[0]
