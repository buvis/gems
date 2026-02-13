"""Custom hatch build hook to compile the Rust extension and frontend.

Compiles src/rust/ into buvis.pybase.zettel._core using maturin and places
the shared library where hatchling will pick it up for the wheel.
Optionally builds the SvelteKit frontend for bim serve.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class RustBuildHook(BuildHookInterface):
    PLUGIN_NAME = "rust-ext"

    def initialize(self, version: str, build_data: dict) -> None:
        if self.target_name != "wheel":
            return

        self._build_rust()
        self._build_frontend()

    def _build_rust(self) -> None:
        root = Path(self.root)
        manifest = root / "src" / "rust" / "Cargo.toml"
        dest_dir = root / "src" / "lib" / "buvis" / "pybase" / "zettel"

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                sys.executable,
                "-m",
                "maturin",
                "build",
                "--manifest-path",
                str(manifest),
                "--interpreter",
                sys.executable,
                "--out",
                tmpdir,
                "--release",
                "--strip",
            ]
            subprocess.run(cmd, check=True, cwd=str(self.root))  # noqa: S603

            wheels = list(Path(tmpdir).glob("*.whl"))
            if not wheels:
                msg = "maturin produced no wheel"
                raise RuntimeError(msg)

            with zipfile.ZipFile(wheels[0]) as whl:
                for name in whl.namelist():
                    if "_core" in name and (name.endswith(".so") or name.endswith(".pyd")):
                        data = whl.read(name)
                        dest = dest_dir / Path(name).name
                        dest.write_bytes(data)
                        break

    def _build_frontend(self) -> None:
        root = Path(self.root)
        frontend_dir = root / "src" / "tools" / "bim" / "commands" / "serve" / "frontend"
        static_dir = root / "src" / "tools" / "bim" / "commands" / "serve" / "static"

        if not frontend_dir.is_dir() or not (frontend_dir / "package.json").is_file():
            return

        npm = shutil.which("npm")
        if not npm:
            return

        subprocess.run([npm, "ci"], check=True, cwd=str(frontend_dir))  # noqa: S603
        subprocess.run([npm, "run", "build"], check=True, cwd=str(frontend_dir))  # noqa: S603

        build_dir = frontend_dir / "build"
        if build_dir.is_dir():
            if static_dir.exists():
                shutil.rmtree(static_dir)
            shutil.copytree(build_dir, static_dir)
