from __future__ import annotations

import re
import sys
from importlib.metadata import distributions, requires
from pathlib import Path

from buvis.pybase.result import CommandResult


class CommandDiagnostics:
    def execute(self) -> CommandResult:
        lines = [
            f"Script: {Path(__file__).resolve()}",
            f"Python: {sys.executable}",
            "",
            "Direct dependencies:",
        ]
        reqs = requires("hello-world") or []
        direct_deps = {re.split(r"[<>=!~\[;]", r)[0].lower().replace("-", "_") for r in reqs}
        for dist in sorted(distributions(), key=lambda d: d.metadata["Name"].lower()):
            name = dist.metadata["Name"]
            normalized = name.lower().replace("-", "_")
            if normalized in direct_deps:
                version = dist.version
                location = getattr(dist, "_path", None)
                location = location.parent if location else "unknown"
                lines.append(f"  {name}=={version} ({location})")
        return CommandResult(success=True, output="\n".join(lines))
