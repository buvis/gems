"""Git hooks that refresh dot host links after checkout, merge, and rewrite."""

from __future__ import annotations

from pathlib import Path

from buvis.pybase.filesystem import atomic_write_text

__all__ = ["HOOK_NAMES", "HOOK_SCRIPT", "install_hooks"]

HOOK_NAMES: tuple[str, ...] = ("post-checkout", "post-merge", "post-rewrite")

HOOK_SCRIPT: str = """#!/usr/bin/env python3
# Installed by dot: relink host-specific config after checkout, merge, rewrite.
import os
import shutil
import subprocess
import sys

dot = shutil.which("dot")
if dot is None:
    print("dot hook: 'dot' not found, host links not refreshed", file=sys.stderr)
else:
    env = {**os.environ, "BUVIS_AUTO_UPDATE": "false"}
    subprocess.run([dot, "materialize", "--hook"], check=False, env=env)
sys.exit(0)
"""


def install_hooks(hooks_dir: Path) -> list[str]:
    """Install dot git hooks into ``hooks_dir``, leaving existing hooks alone.

    A hook that already exists (including a dangling symlink) is never read
    or written.

    Args:
        hooks_dir: Directory to write the hooks into, created if missing.

    Returns:
        One ``installed hook <name>`` line per hook written, in hook order.

    Raises:
        OSError: When a write fails. Hooks written before the failure stay
            installed but get no line, since the error aborts the call.
    """
    hooks_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for name in HOOK_NAMES:
        path = hooks_dir / name
        if not path.exists() and not path.is_symlink():
            atomic_write_text(path, HOOK_SCRIPT, mode=0o755)
            lines.append(f"installed hook {name}")
    return lines
