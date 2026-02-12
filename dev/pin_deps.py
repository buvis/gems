#!/usr/bin/env python3
"""Pin or unpin dependencies in pyproject.toml using resolved versions from uv.lock."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


def _normalize(name: str) -> str:
    """Normalize package name: lowercase, underscores to hyphens."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_lockfile(lock_path: Path) -> dict[str, str]:
    """Parse uv.lock into {normalized_name: version} map."""
    with open(lock_path, "rb") as f:
        data = tomllib.load(f)
    return {_normalize(pkg["name"]): pkg["version"] for pkg in data.get("package", [])}


def _find_editable_requires(lock_path: Path) -> dict[str, str]:
    """Find original specifiers from the editable package's metadata in uv.lock."""
    with open(lock_path, "rb") as f:
        data = tomllib.load(f)

    for pkg in data.get("package", []):
        src = pkg.get("source", {})
        if src.get("editable") == ".":
            meta = pkg.get("metadata", {})
            requires = meta.get("requires-dist", [])
            result = {}
            for req in requires:
                name = req["name"]
                spec = req.get("specifier", "")
                result[_normalize(name)] = f"{name}{spec}"
            return result
    return {}


def _replace_deps_in_bracket(text: str, replacer: callable) -> str:
    """Apply replacer to each quoted dep string inside a [...] block."""
    return re.sub(
        r'"([a-zA-Z0-9_.-]+(?:[><=!~][^"]*)?)"',
        replacer,
        text,
    )


def _transform_deps_block(content: str, replacer: callable) -> str:
    """Find dependencies = [...] and optional-dependencies blocks, apply replacer to each dep."""

    # Main dependencies = [...]
    content = re.sub(
        r"(?<=dependencies\s=\s)\[.*?\]",
        lambda m: _replace_deps_in_bracket(m.group(0), replacer),
        content,
        flags=re.DOTALL,
    )

    # Optional-dependencies section: each `name = [...]` line
    opt_pattern = re.compile(
        r"(\[project\.optional-dependencies\]\n)(.*?)(?=\n\[)",
        re.DOTALL,
    )
    opt_match = opt_pattern.search(content)
    if opt_match:
        header = opt_match.group(1)
        body = opt_match.group(2)
        transformed_body = re.sub(
            r"(?<==\s)\[.*?\]",
            lambda m: _replace_deps_in_bracket(m.group(0), replacer),
            body,
        )
        content = content[:opt_match.start()] + header + transformed_body + content[opt_match.end():]

    return content


def pin(pkg_dir: Path) -> None:
    """Pin deps in pyproject.toml to versions resolved in uv.lock."""
    lock_path = pkg_dir / "uv.lock"
    pyproject_path = pkg_dir / "pyproject.toml"

    if not lock_path.exists():
        print(f"No uv.lock in {pkg_dir}", file=sys.stderr)
        sys.exit(1)

    versions = _parse_lockfile(lock_path)
    content = pyproject_path.read_text()

    def pin_dep(m: re.Match) -> str:
        dep_str = m.group(1)
        name_match = re.match(r"^([a-zA-Z0-9_.-]+)", dep_str)
        if not name_match:
            return m.group(0)
        name = name_match.group(1)
        normalized = _normalize(name)
        if normalized in versions:
            return f'"{name}=={versions[normalized]}"'
        return m.group(0)

    content = _transform_deps_block(content, pin_dep)
    pyproject_path.write_text(content)
    print(f"Pinned deps in {pkg_dir.name}/pyproject.toml")


def unpin(pkg_dir: Path) -> None:
    """Restore original version specifiers from uv.lock metadata."""
    lock_path = pkg_dir / "uv.lock"
    pyproject_path = pkg_dir / "pyproject.toml"

    if not lock_path.exists():
        print(f"No uv.lock in {pkg_dir}", file=sys.stderr)
        sys.exit(1)

    originals = _find_editable_requires(lock_path)
    if not originals:
        print(f"No editable package found in {pkg_dir}/uv.lock", file=sys.stderr)
        sys.exit(1)

    content = pyproject_path.read_text()

    def restore_dep(m: re.Match) -> str:
        dep_str = m.group(1)
        name_match = re.match(r"^([a-zA-Z0-9_.-]+)", dep_str)
        if not name_match:
            return m.group(0)
        normalized = _normalize(name_match.group(1))
        if normalized in originals:
            return f'"{originals[normalized]}"'
        return m.group(0)

    content = _transform_deps_block(content, restore_dep)
    pyproject_path.write_text(content)
    print(f"Unpinned deps in {pkg_dir.name}/pyproject.toml")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: pin_deps.py <pkg_dir> [--unpin]", file=sys.stderr)
        sys.exit(1)

    pkg_dir = Path(sys.argv[1])
    if not pkg_dir.is_absolute():
        pkg_dir = Path(__file__).parent.parent / pkg_dir

    if "--unpin" in sys.argv:
        unpin(pkg_dir)
    else:
        pin(pkg_dir)
