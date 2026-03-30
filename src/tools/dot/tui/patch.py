from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["Hunk", "build_hunk_patch", "build_line_patch", "parse_diff"]

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True, slots=True)
class Hunk:
    """A single hunk from a unified diff."""

    header: str
    lines: list[str]
    start_old: int
    count_old: int
    start_new: int
    count_new: int


def parse_diff(raw_diff: str) -> list[Hunk]:
    """Parse a unified diff string into a list of Hunk objects.

    Args:
        raw_diff: Raw unified diff output.

    Returns:
        List of parsed hunks. Empty for blank input or binary diffs.
    """
    if not raw_diff or raw_diff.startswith("Binary files"):
        return []

    hunks: list[Hunk] = []
    current_header: str | None = None
    current_lines: list[str] = []
    start_old = count_old = start_new = count_new = 0

    for line in raw_diff.splitlines():
        m = _HUNK_RE.match(line)
        if m:
            if current_header is not None:
                hunks.append(
                    Hunk(
                        header=current_header,
                        lines=current_lines,
                        start_old=start_old,
                        count_old=count_old,
                        start_new=start_new,
                        count_new=count_new,
                    )
                )
            current_header = line
            current_lines = []
            start_old = int(m.group(1))
            count_old = int(m.group(2)) if m.group(2) is not None else 1
            start_new = int(m.group(3))
            count_new = int(m.group(4)) if m.group(4) is not None else 1
        elif current_header is not None:
            current_lines.append(line)

    if current_header is not None:
        hunks.append(
            Hunk(
                header=current_header,
                lines=current_lines,
                start_old=start_old,
                count_old=count_old,
                start_new=start_new,
                count_new=count_new,
            )
        )

    return hunks


def build_hunk_patch(path: str, hunk: Hunk) -> str:
    """Construct a valid git patch for a single hunk.

    Args:
        path: File path relative to repo root.
        hunk: Hunk to include in the patch.

    Returns:
        Patch string suitable for ``git apply --cached``.
    """
    lines = [
        f"diff --git a/{path} b/{path}",
        f"--- a/{path}",
        f"+++ b/{path}",
        hunk.header,
        *hunk.lines,
        "",
    ]
    return "\n".join(lines)


def build_line_patch(path: str, hunk: Hunk, selected_indices: set[int]) -> str:
    """Construct a patch from selected lines within a hunk.

    Args:
        path: File path relative to repo root.
        hunk: Hunk containing the lines.
        selected_indices: 0-based indices into hunk.lines to include.

    Returns:
        Patch string suitable for ``git apply --cached``.
    """
    out_lines: list[str] = []
    for i, line in enumerate(hunk.lines):
        if line.startswith("+"):
            if i in selected_indices:
                out_lines.append(line)
            # unselected additions: excluded entirely
        elif line.startswith("-"):
            if i in selected_indices:
                out_lines.append(line)
            else:
                # unselected deletions become context
                out_lines.append(" " + line[1:])
        else:
            # context lines always included
            out_lines.append(line)

    old_count = sum(1 for l in out_lines if l.startswith(" ") or l.startswith("-"))
    new_count = sum(1 for l in out_lines if l.startswith(" ") or l.startswith("+"))
    header = f"@@ -{hunk.start_old},{old_count} +{hunk.start_new},{new_count} @@"

    parts = [
        f"diff --git a/{path} b/{path}",
        f"--- a/{path}",
        f"+++ b/{path}",
        header,
        *out_lines,
        "",
    ]
    return "\n".join(parts)
