"""Validate that every tool under src/tools/ is wired in pyproject.toml."""
from __future__ import annotations

import re
import sys
from pathlib import Path


def _to_kebab(snake: str) -> str:
    return snake.replace("_", "-")


def _find_tool_dirs(root: Path) -> list[str]:
    """Return sorted snake_case names of tool directories."""
    tools_dir = root / "src" / "tools"
    if not tools_dir.is_dir():
        return []
    return sorted(
        d.name
        for d in tools_dir.iterdir()
        if d.is_dir() and (d / "__init__.py").exists()
    )


def _parse_scripts(text: str) -> set[str]:
    """Extract keys from [project.scripts] section."""
    keys: set[str] = set()
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[project.scripts]":
            in_section = True
            continue
        if in_section:
            if stripped.startswith("[") and stripped.endswith("]"):
                break
            m = re.match(r'^(\S+)\s*=', stripped)
            if m:
                keys.add(m.group(1))
    return keys


def _parse_packages(text: str) -> set[str]:
    """Extract paths from [tool.hatch.build.targets.wheel] packages list."""
    paths: set[str] = set()
    in_packages = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("packages"):
            in_packages = True
            continue
        if in_packages:
            if stripped == "]":
                break
            m = re.match(r'^"([^"]+)"', stripped)
            if m:
                paths.add(m.group(1))
    return paths


def check(root: Path) -> list[str]:
    """Return list of error messages. Empty means all OK."""
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return ["pyproject.toml not found"]

    text = pyproject.read_text()
    scripts = _parse_scripts(text)
    packages = _parse_packages(text)
    tool_dirs = _find_tool_dirs(root)

    errors: list[str] = []
    for snake in tool_dirs:
        kebab = _to_kebab(snake)
        expected_script_key = kebab
        expected_package = f"src/tools/{snake}"

        if expected_script_key not in scripts:
            errors.append(
                f'Missing [project.scripts] entry: {kebab} = "{snake}.cli:cli"'
            )
        if expected_package not in packages:
            errors.append(
                f'Missing [tool.hatch.build.targets.wheel] package: "src/tools/{snake}"'
            )

    return errors


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    errors = check(root)
    if errors:
        print("Tool wiring errors in pyproject.toml:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("All tools correctly wired in pyproject.toml")


if __name__ == "__main__":
    main()
