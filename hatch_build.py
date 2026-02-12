"""Custom hatch build hook to compile the Rust extension module.

Compiles src/rust/ into buvis.pybase.zettel._core using maturin and places
the shared library where hatchling will pick it up for the wheel.
"""

from __future__ import annotations

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

        root = Path(self.root)
        manifest = root / "src" / "rust" / "Cargo.toml"
        dest_dir = root / "src" / "lib" / "buvis" / "pybase" / "zettel"

        with tempfile.TemporaryDirectory() as tmpdir:
            # Build with maturin into a temp dir
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
            subprocess.run(cmd, check=True, cwd=str(root))  # noqa: S603

            # Extract the _core extension from the maturin wheel
            wheels = list(Path(tmpdir).glob("*.whl"))
            if not wheels:
                msg = "maturin produced no wheel"
                raise RuntimeError(msg)

            with zipfile.ZipFile(wheels[0]) as whl:
                for name in whl.namelist():
                    # The extension will be at buvis/pybase/zettel/_core.cpython-XXX.so
                    if "_core" in name and (name.endswith(".so") or name.endswith(".pyd")):
                        data = whl.read(name)
                        dest = dest_dir / Path(name).name
                        dest.write_bytes(data)
                        break
