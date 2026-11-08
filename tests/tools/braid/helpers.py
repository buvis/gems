from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from braid.domain.engine import Mode, Settings


def make_skill(source: Path, name: str) -> Path:
    skill = source / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test {name}.\n---\n\n# {name}\n")
    return skill


def make_rule(source: Path, name: str, body: str = "...") -> Path:
    rule = source / "rules" / name
    rule.mkdir(parents=True)
    (rule / "RULE.md").write_text(body, encoding="utf-8")
    return rule


def make_host_rule(source: Path, host: str, name: str, body: str = "...") -> Path:
    rule = source / "hosts" / host / "rules" / name
    rule.mkdir(parents=True)
    (rule / "RULE.md").write_text(body, encoding="utf-8")
    return rule


def settings(
    tmp_path: Path,
    *sources: Path,
    mode: Mode = Mode.SYNC,
    policy_files: tuple[Path, ...] = (),
) -> Settings:
    return Settings(
        sources=tuple(sources),
        agents_root=tmp_path / "home" / ".agents",
        claude_root=tmp_path / "home" / ".claude",
        mode=mode,
        policy_files=policy_files,
    )


def kiro_root(config: Settings) -> Path:
    return config.agents_root.parent / ".kiro"


def enroll(config: Settings, *agents: str) -> Settings:
    return replace(config, enable_kiro=True, kiro_root=kiro_root(config), kiro_agents=agents)


def write_agent(config: Settings, name: str, body: object) -> Path:
    agent = kiro_root(config) / "agents" / f"{name}.json"
    agent.parent.mkdir(parents=True, exist_ok=True)
    agent.write_text(json.dumps(body))
    return agent


def read_state(config: Settings) -> dict:
    return json.loads((config.agents_root / ".braid-state.json").read_text())


def generated_file(config: Settings, host: str) -> Path:
    return config.agents_root / "hosts" / host / "AGENTS.md"


def make_host_roots(config: Settings, *hosts: str) -> None:
    """Create ``~/.<host>`` beside the agents root (the autouse fixture's HOME)."""
    for host in hosts:
        (config.agents_root.parent / f".{host}").mkdir(parents=True, exist_ok=True)


def write_policy(directory: Path, *names: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    policy = directory / ".braidignore"
    policy.write_text("".join(f"{name}\n" for name in names))
    return policy


class SymlinkPrivilegeError(OSError):
    """The OSError Windows raises for a file symlink without the privilege (winerror 1314)."""

    winerror = 1314


def deny_file_symlinks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate Windows without symlink privilege: only RULE.md / AGENTS.md symlinks fail."""
    real_symlink = os.symlink

    def symlink(src: str | Path, dst: str | Path, target_is_directory: bool = False) -> None:
        if Path(src).name in {"RULE.md", "AGENTS.md"}:
            raise SymlinkPrivilegeError(1314, "A required privilege is not held by the client")
        real_symlink(src, dst, target_is_directory)

    monkeypatch.setattr(os, "symlink", symlink)
