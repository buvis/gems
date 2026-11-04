from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from braid.domain.engine import Mode, Settings


def make_skill(source: Path, name: str) -> Path:
    skill = source / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test {name}.\n---\n\n# {name}\n")
    return skill


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
