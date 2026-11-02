"""Run documented pytest with process-only agent/config isolation."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

task_root = Path(__file__).resolve().parents[3]
child_env = {
    key: value
    for key, value in os.environ.items()
    if not key.startswith(("GIT_CONFIG_", "GIT_AUTHOR_", "GIT_COMMITTER_"))
}
child_env["GIT_CONFIG_GLOBAL"] = "/dev/null"
child_env["BUVIS_CONFIG_DIR"] = str(task_root / "docs/dev/tmp/rework-test-config")
result = subprocess.run(
    ["uv", "run", "pytest", *sys.argv[1:]],
    cwd=task_root,
    env=child_env,
    timeout=int(os.environ.get("REWORK_GATE_TIMEOUT", "300")),
    check=False,
)
raise SystemExit(result.returncode)
