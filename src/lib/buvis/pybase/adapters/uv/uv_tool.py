from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from buvis.pybase.adapters.console.console import console
from buvis.pybase.adapters.uv.uv import UvAdapter


class UvToolManager:
    """Manage and run Python tools via uv.

    Supports development workflows with automatic tool discovery
    and installation from local project sources.
    """

    @staticmethod
    def install_all(scripts_root: Path | None = None) -> None:
        """Install all projects in src/ as uv tools.

        Scans scripts_root/src/ for directories containing pyproject.toml
        and installs each as a uv tool.

        Args:
            scripts_root: Root directory containing src/. Defaults to cwd.
        """
        UvAdapter.ensure_uv()

        if scripts_root is None:
            scripts_root = Path.cwd()

        src_directory = scripts_root / "src"

        if src_directory.exists():
            for project_dir in src_directory.iterdir():
                if project_dir.is_dir() and (project_dir / "pyproject.toml").exists():
                    UvToolManager.install_tool(project_dir)

    @staticmethod
    def install_tool(project_path: Path) -> None:
        """Install a project as a uv tool.

        Uses --force --upgrade to ensure latest version. On failure,
        cleans the tool cache and retries once.

        Args:
            project_path: Directory containing pyproject.toml.
        """
        pkg_name = project_path.name
        console.status(f"Installing {pkg_name} as uv tool...")

        cmd = ["uv", "tool", "install", "--force", "--upgrade", str(project_path)]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            console.success(f"Installed {pkg_name}")
        except subprocess.CalledProcessError:
            # Clean only this tool's cache and retry
            subprocess.run(
                ["uv", "cache", "clean", pkg_name],
                check=False,
                capture_output=True,
            )
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                console.success(f"Installed {pkg_name} (after cache clean)")
            except subprocess.CalledProcessError as e:
                console.failure(f"Failed to install {pkg_name}: {e}")

    @classmethod
    def run(cls, script_path: str, args: list[str] | None = None) -> None:
        """Run a tool from local venv, project source, or installed uv tool.

        Execution priority when BUVIS_DEV_MODE=1:
            1. Local .venv/bin/{tool} if exists
            2. uv run from project source (src/{pkg}/pyproject.toml)
            3. Exit with error if neither found

        Execution priority when BUVIS_DEV_MODE unset:
            1. uv tool run {tool}
            2. Auto-install from local source if tool not found
            3. Exit with error if no source available

        Args:
            script_path: Path to the launcher script (used to derive tool name).
            args: Command arguments. Defaults to sys.argv[1:].

        Note:
            Tool name derived from script stem: my-tool -> pkg my_tool.
        """
        UvAdapter.ensure_uv()

        if args is None:
            args = sys.argv[1:]

        script = Path(script_path).resolve()
        tool_cmd = script.stem
        pkg_name = tool_cmd.replace("-", "_")
        scripts_root = script.parent.parent
        project_dir = scripts_root / "src" / pkg_name

        in_dev_mode = os.environ.get("BUVIS_DEV_MODE") == "1"

        if in_dev_mode:
            venv_bin = project_dir / ".venv" / "bin" / tool_cmd

            if venv_bin.exists():
                result = subprocess.run([str(venv_bin), *args], check=False)
                sys.exit(result.returncode)

            if project_dir.exists() and (project_dir / "pyproject.toml").exists():
                result = subprocess.run(
                    ["uv", "run", "--project", str(project_dir), "-m", pkg_name, *args],
                    check=False,
                )
                sys.exit(result.returncode)

            print(f"No venv or project found at {project_dir}", file=sys.stderr)
            sys.exit(1)

        result = subprocess.run(
            ["uv", "tool", "run", tool_cmd, *args],
            check=False,
        )
        if result.returncode == 0:
            sys.exit(0)

        # Tool not found - try auto-install
        if project_dir.exists() and (project_dir / "pyproject.toml").exists():
            cls.install_tool(project_dir)
            result = subprocess.run(
                ["uv", "tool", "run", tool_cmd, *args],
                check=False,
            )
            sys.exit(result.returncode)

        print(
            f"Tool '{tool_cmd}' not found and no project to install from.",
            file=sys.stderr,
        )
        sys.exit(1)
