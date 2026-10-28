from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

from sysup.step_result import StepResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from sysup.config import RefreshSpec

__all__ = ["run_refresh"]

# gh's own environment contract (see capabilities/gh_token.py): these override
# the stored credential and host. Stripped from a gh login step's child
# environment so the renewal writes to the configured directory for github.com,
# never an ambient one. The parent environment is never mutated.
_GH_AMBIENT_OVERRIDES = (
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN",
    "GH_HOST",
)


def run_refresh(name: str, spec: RefreshSpec, read_secret: Callable[[], str]) -> StepResult:
    """Run a refresh procedure's commands in order, stopping at the first failure.

    Returns one :class:`StepResult` for the whole procedure. The pasted secret is
    read via ``read_secret`` only for a command that declares ``stdin: secret``,
    passed solely on that command's standard input, and dropped immediately after
    the call: it never reaches argv, the environment, logs, state or a
    notification. For a ``gh auth login`` step carrying ``GH_CONFIG_DIR`` the five
    ambient gh token/host overrides are removed from the merged child
    environment; ``os.environ`` is left unchanged throughout.

    Args:
        name: The expiry item being refreshed.
        spec: The refresh procedure.
        read_secret: A no-argument callable returning the pasted secret.

    Returns:
        A ``kind="item"`` success step when every command completed, or a failure
        step naming the first command that failed.
    """
    for command in spec.commands:
        binary = shutil.which(command.argv[0])
        if binary is None:
            return StepResult(name, success=False, message=f"{command.argv[0]} not found", kind="item")

        env = command.child_env()
        if command.argv[0] == "gh" and "GH_CONFIG_DIR" in command.env:
            for override in _GH_AMBIENT_OVERRIDES:
                env.pop(override, None)

        resolved = [binary, *command.argv[1:]]
        if command.stdin == "secret":
            secret = read_secret()
            returncode = subprocess.run(resolved, env=env, input=secret, text=True, check=False).returncode
            del secret
        else:
            returncode = subprocess.run(resolved, env=env, check=False).returncode

        if returncode != 0:
            joined = " ".join(command.argv)
            return StepResult(name, success=False, message=f"{joined} failed: exit code {returncode}", kind="item")

    return StepResult(name, success=True, message=f"{name}: refresh commands completed", kind="item")
