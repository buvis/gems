"""Run pytest with isolated agent identity, Git config and portfolio roots."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_", "GIT_CONFIG_"))
    }
    environment.update(
        UV_CACHE_DIR="/tmp/gems-autocodex-uv-cache",
        XDG_STATE_HOME="/tmp/gems-autocodex-test-state",
        BUVIS_CONFIG_DIR=str(Path(__file__).with_name("00111-verification-config").resolve()),
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_SYSTEM=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
    )
    result = subprocess.run(
        ["uv", "run", "--no-sync", "pytest", "-q", "--tb=line", *sys.argv[1:]],
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=600,
        check=False,
    )
    sys.stdout.write(result.stdout)
    summary = next(
        (line for line in reversed(result.stdout.splitlines()) if re.search(r"\d+ (?:passed|failed)", line)),
        "",
    )
    counts = {kind: int(value) for value, kind in re.findall(r"(\d+) (passed|failed|skipped)", summary)}
    if not counts:
        return result.returncode or 2
    print(
        f"PASS {counts.get('passed', 0)} FAIL {counts.get('failed', 0)} "
        f"SKIP {counts.get('skipped', 0)} EXIT {result.returncode}"
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
