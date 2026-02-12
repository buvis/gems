from __future__ import annotations

import re
import sys
from importlib.metadata import distributions, requires
from pathlib import Path

from buvis.pybase.adapters import console


class CommandDiagnostics:
    def execute(self: "CommandDiagnostics") -> None:
        console.print(f"Script: {Path(__file__).resolve()}", mode="raw")
        console.print(f"Python: {sys.executable}", mode="raw")
        console.print("\nDirect dependencies:", mode="raw")
        reqs = requires("hello-world") or []
        direct_deps = {re.split(r"[<>=!~\[;]", r)[0].lower().replace("-", "_") for r in reqs}
        for dist in sorted(distributions(), key=lambda d: d.metadata["Name"].lower()):
            name = dist.metadata["Name"]
            normalized = name.lower().replace("-", "_")
            if normalized in direct_deps:
                version = dist.version
                location = getattr(dist, "_path", None)
                location = location.parent if location else "unknown"
                console.print(f"  {name}=={version} ({location})", mode="raw")
