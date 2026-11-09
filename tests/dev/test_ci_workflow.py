"""Exercise the workflow's shell logic, including its failure paths."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/test.yml"


def _script(job: str, step_id: str) -> str:
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"][job]["steps"]
    return next(step["run"] for step in steps if step.get("id") == step_id)


def _run(script: str, root: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail"],
        input=script,
        cwd=root,
        env={**os.environ, **env},
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.fixture
def repo(tmp_path):
    for tool in ("bim", "dot", "pinger", "new_tool"):
        directory = tmp_path / "src/tools" / tool
        directory.mkdir(parents=True)
        (directory / "__init__.py").touch()
    return tmp_path


class TestDetection:
    @pytest.mark.parametrize(
        ("paths", "force_all", "base", "expected"),
        [
            ("docs/readme.md", "false", "base", []),
            ("", "false", "base", []),
            ("src/tools/pinger/cli.py\ntests/tools/pinger/test_cli.py", "false", "base", ["pinger"]),
            ("src/tools/new_tool/cli.py", "false", "base", ["new_tool"]),
            ("src/lib/shared.py", "false", "base", ["bim", "dot", "new_tool", "pinger"]),
            ("uv.lock", "false", "base", ["bim", "dot", "new_tool", "pinger"]),
            (".github/workflows/test.yml", "false", "base", ["bim", "dot", "new_tool", "pinger"]),
            ("docs/readme.md", "true", "base", ["bim", "dot", "new_tool", "pinger"]),
            ("", "false", "", ["bim", "dot", "new_tool", "pinger"]),
            ("", "false", "0" * 40, ["bim", "dot", "new_tool", "pinger"]),
        ],
    )
    def test_selects_tools(self, repo, paths, force_all, base, expected):
        output = repo / "output"
        result = _run(
            'git() { printf "%s\\n" "$CHANGED_PATHS"; }\n' + _script("detect", "filter"),
            repo,
            CHANGED_PATHS=paths,
            FORCE_ALL=force_all,
            BASE_SHA=base,
            GITHUB_OUTPUT=str(output),
        )
        assert result.returncode == 0, result.stderr
        values = dict(line.split("=", 1) for line in output.read_text().splitlines())
        assert json.loads(values["changed_tools"]) == expected

    def test_diff_failure_fails_detection(self, repo):
        result = _run(
            "git() { return 128; }\n" + _script("detect", "filter"),
            repo,
            FORCE_ALL="false",
            BASE_SHA="missing",
            GITHUB_OUTPUT=str(repo / "output"),
        )
        assert result.returncode != 0

    @pytest.mark.parametrize("tools", [[], ["pinger"], ["bim", "dot", "new_tool", "pinger"]])
    def test_groups_keep_every_tool_once(self, repo, tools):
        output = repo / "output"
        result = _run(_script("detect", "groups"), repo, CHANGED_TOOLS=json.dumps(tools), GITHUB_OUTPUT=str(output))
        assert result.returncode == 0, result.stderr
        groups = json.loads(output.read_text().split("=", 1)[1])
        assert sorted(tool for group in groups for tool in group["tools"]) == sorted(tools)
        assert all(group["tools"] for group in groups)
        assert len(groups) <= 3


class TestGate:
    @pytest.mark.parametrize(
        ("detect", "lint", "lib", "tools", "changed", "success"),
        [
            ("success", "success", "success", "success", '["dot"]', True),
            ("success", "success", "success", "skipped", "[]", True),
            ("failure", "success", "success", "skipped", "", False),
            ("cancelled", "success", "success", "skipped", "", False),
            ("success", "failure", "success", "success", '["dot"]', False),
            ("success", "success", "failure", "success", '["dot"]', False),
            ("success", "success", "success", "failure", '["dot"]', False),
            ("success", "success", "success", "skipped", '["dot"]', False),
            ("success", "success", "success", "cancelled", '["dot"]', False),
        ],
    )
    def test_requires_every_selected_suite(self, tmp_path, detect, lint, lib, tools, changed, success):
        result = _run(
            _script("test", "gate"),
            tmp_path,
            DETECT_RESULT=detect,
            FRONTEND_RESULT="success",
            LINT_RESULT=lint,
            LIB_RESULT=lib,
            TOOLS_RESULT=tools,
            CHANGED_TOOLS=changed,
        )
        assert (result.returncode == 0) is success

    @pytest.mark.parametrize("frontend", ["failure", "skipped", "cancelled"])
    def test_frontend_must_pass_even_when_tools_are_skipped(self, tmp_path, frontend):
        result = _run(
            _script("test", "gate"),
            tmp_path,
            DETECT_RESULT="success",
            FRONTEND_RESULT=frontend,
            LINT_RESULT="success",
            LIB_RESULT="success",
            TOOLS_RESULT="skipped",
            CHANGED_TOOLS="[]",
        )
        assert result.returncode != 0


class TestGroupedTests:
    def test_failure_does_not_skip_remaining_tools(self, tmp_path):
        result = _run(
            'uv() { printf "%s\\n" "$*"; [[ "$*" != *tests/tools/broken* ]]; }\n' + _script("tools", "tests"),
            tmp_path,
            GROUP_TOOLS='["broken", "pinger"]',
        )
        assert result.returncode != 0
        assert "tests/tools/broken --cov=src/tools/broken" in result.stdout
        assert "tests/tools/pinger --cov=src/tools/pinger" in result.stdout
        assert result.stdout.count("--cov-fail-under=50") == 2
