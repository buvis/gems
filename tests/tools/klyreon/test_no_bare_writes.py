"""Invariant: every persisting write in the tool goes through atomic_write_*.

The spec engine's writer is the single serialization seam; it calls
``atomic_write_text``. No module in ``src/tools/klyreon`` may call a bare
``Path.write_text`` / ``.write_bytes`` or ``open(..., "w"/"a"/"x")``. This
test greps the source and fails on any such call.
"""

from __future__ import annotations

import re
from pathlib import Path

_TOOL_SRC = Path(__file__).resolve().parents[3] / "src" / "tools" / "klyreon"

# Bare write calls we forbid. atomic_write_text / atomic_write_bytes are allowed.
_BARE_WRITE_RE = re.compile(r"\.write_text\s*\(|\.write_bytes\s*\(")
_OPEN_WRITE_RE = re.compile(r"\bopen\s*\([^)]*['\"][wax]b?\+?['\"]")


class TestNoBareWrites:
    def test_tool_source_has_no_bare_writes(self) -> None:
        offenders: list[str] = []
        for py in sorted(_TOOL_SRC.rglob("*.py")):
            text = py.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _BARE_WRITE_RE.search(line) or _OPEN_WRITE_RE.search(line):
                    offenders.append(f"{py.relative_to(_TOOL_SRC)}:{lineno}: {line.strip()}")
        assert not offenders, "bare write calls found (use atomic_write_text):\n" + "\n".join(offenders)

    def test_atomic_write_is_actually_used(self) -> None:
        writer = (_TOOL_SRC / "spec" / "writer.py").read_text(encoding="utf-8")
        assert "atomic_write_text" in writer
