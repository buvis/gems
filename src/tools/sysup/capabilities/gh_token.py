from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["GhTokenExpiry", "parse_expiration"]

# gh's own environment contract: these override the stored credential and host.
# Stripped from the child environment so this probe always reads the token in
# the configured directory for github.com, never an ambient one. Verified
# against https://cli.github.com/manual/gh_help_environment (2026-10-13).
_GH_AMBIENT_OVERRIDES = (
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN",
    "GH_HOST",
)

# Matched case-insensitively at a line start; the measured header is
# `Github-Authentication-Token-Expiration: 2027-10-13 18:05:04 UTC`.
_EXPIRATION_HEADER_RE = re.compile(r"(?im)^github-authentication-token-expiration:\s*(.+?)\s*$")

_GH_TIMEOUT = 30


def parse_expiration(value: str) -> datetime:
    """Parse a gh expiration header value into an aware datetime.

    Accepts the measured ``YYYY-MM-DD HH:MM:SS UTC`` form (``UTC`` is rewritten
    to a numeric ``+0000`` offset) as well as a header that already carries a
    numeric offset.

    Args:
        value: The raw header value.

    Returns:
        The parsed timezone-aware datetime.

    Raises:
        ValueError: If the value does not match the expected format.
    """
    return datetime.strptime(value.replace(" UTC", " +0000"), "%Y-%m-%d %H:%M:%S %z")


class GhTokenExpiry:
    """Report when a gh token expires, and whether its grant still works.

    Reads the ``Github-Authentication-Token-Expiration`` header from
    ``gh api -i user`` under the item's ``config_dir``, then probes the grant
    with one authenticated call that needs private-repository access. Both calls
    pin ``--hostname github.com`` and run with the five ambient gh token/host
    overrides stripped from a copied child environment, so the configured
    credential directory is always the one consulted; the parent environment is
    never mutated.
    """

    @property
    def inputs(self: GhTokenExpiry) -> Mapping[str, object]:
        return {"config_dir": None, "probe": None}

    def expires_at(self: GhTokenExpiry, **kwargs: object) -> datetime | str:
        """Return the token expiry datetime, or a string naming why it is unknown.

        Args:
            **kwargs: ``config_dir`` (the gh config directory) and ``probe`` (a
                ``gh api`` path needing private-repository access).

        Returns:
            The parsed expiration datetime, or one of the documented unknown
            reasons as a string.
        """
        gh = shutil.which("gh")
        if gh is None:
            return "gh not found"

        config_dir = str(kwargs.get("config_dir", ""))
        probe = str(kwargs.get("probe", ""))

        env = dict(os.environ)
        for name in _GH_AMBIENT_OVERRIDES:
            env.pop(name, None)
        env["GH_CONFIG_DIR"] = str(Path(config_dir).expanduser())

        user = subprocess.run(
            [gh, "api", "--hostname", "github.com", "-i", "user"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=_GH_TIMEOUT,
        )
        if user.returncode != 0:
            return f"gh api user failed: {user.stderr.strip()}"

        match = _EXPIRATION_HEADER_RE.search(user.stdout)
        if match is None:
            return "no Github-Authentication-Token-Expiration header (token without expiry?)"

        raw = match.group(1)
        try:
            expiry = parse_expiration(raw)
        except ValueError:
            return f"unparseable expiration header: {raw}"

        grant = subprocess.run(
            [gh, "api", "--hostname", "github.com", "--silent", probe],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=_GH_TIMEOUT,
        )
        if grant.returncode != 0:
            return f"grant broken: gh api {probe}: {grant.stderr.strip()}"

        return expiry
