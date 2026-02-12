import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


class UvAdapter:
    """uv package manager integration.

    Provides auto-installation of uv and PATH configuration for
    cross-platform Python tooling.
    """

    @staticmethod
    def ensure_uv() -> None:
        """Ensure uv is installed and available in PATH.

        If uv is not found, automatically installs it using:
        - Windows: PowerShell installer from astral.sh
        - Unix: curl installer from astral.sh

        Updates PATH to include common uv installation directories:
        - ~/.cargo/bin
        - ~/.local/bin (Unix)
        - ~/AppData/Local/uv (Windows)

        Exits with code 1 if installation fails.
        """
        if shutil.which("uv"):
            return

        print("uv not found. Installing...", file=sys.stderr)
        system = platform.system()
        try:
            if system == "Windows":
                subprocess.check_call(
                    [
                        "powershell",
                        "-ExecutionPolicy",
                        "ByPass",
                        "-c",
                        "irm https://astral.sh/uv/install.ps1 | iex",
                    ],
                )
                user_profile = Path(os.environ.get("USERPROFILE", ""))
                possible_paths = [
                    user_profile / ".cargo" / "bin",
                    user_profile / "AppData" / "Local" / "uv",
                ]
            else:
                subprocess.check_call(  # noqa: S602 - trusted installer
                    "curl -LsSf https://astral.sh/uv/install.sh | sh",
                    shell=True,
                )
                home = Path(os.environ.get("HOME", ""))
                possible_paths = [
                    home / ".cargo" / "bin",
                    home / ".local" / "bin",
                ]

            for p in possible_paths:
                if p.exists():
                    os.environ["PATH"] += os.pathsep + str(p)

        except subprocess.CalledProcessError as e:
            print(f"Failed to install uv: {e}", file=sys.stderr)
            sys.exit(1)
