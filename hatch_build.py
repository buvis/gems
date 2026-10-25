"""Custom hatch build hook to compile the Rust extension and frontend.

Compiles src/rust/ into buvis.pybase.zettel._core using maturin and places
the shared library where hatchling will pick it up for the wheel.
Builds the SvelteKit frontends for bim serve and postup serve, except that an
editable install (every ``uv sync``) leaves postup's committed build/ alone and
``BUVIS_SKIP_FRONTEND=1`` skips every frontend build.
"""

from __future__ import annotations

import os
import platform
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
        self._build_frontend(editable=version == "editable")
        build_data["infer_tag"] = True
        build_data["pure_python"] = False

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
            subprocess.run(cmd, check=True, cwd=str(self.root))

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
                        if platform.system() == "Darwin":
                            subprocess.run(
                                ["codesign", "-f", "-s", "-", str(dest)],
                                check=True,
                            )
                        break

    # Each tool that ships a SvelteKit frontend, as
    # (frontend_dir_relpath, static_dir_relpath_or_None):
    #   * bim builds on demand and copies build/ -> a sibling static/ that the
    #     wheel packages (its build/ is gitignored).
    #   * postup COMMITS its build/ and serves it in place (PRD 00065/00067), so
    #     it has no static/ copy — a release rebuild just refreshes build/.
    _FRONTENDS = (
        (
            ("src", "tools", "bim", "commands", "serve", "frontend"),
            ("src", "tools", "bim", "commands", "serve", "static"),
        ),
        (
            ("src", "tools", "postup", "adapters", "web", "frontend"),
            None,
        ),
    )

    def _build_frontend(self, *, editable: bool = False) -> None:
        if os.environ.get("BUVIS_SKIP_FRONTEND"):
            return

        npm = shutil.which("npm")
        if not npm:
            return

        root = Path(self.root)
        for frontend_parts, static_parts in self._FRONTENDS:
            # A frontend served from its committed build/ (postup) is never
            # rebuilt for an editable install: every `uv sync` would refresh
            # tracked files and dirty the tree whenever the npm toolchain drifts.
            # Release wheels still rebuild it.
            if editable and static_parts is None:
                continue
            frontend_dir = root.joinpath(*frontend_parts)
            static_dir = root.joinpath(*static_parts) if static_parts else None
            self._build_one_frontend(npm, frontend_dir, static_dir)

    def _build_one_frontend(self, npm: str, frontend_dir: Path, static_dir: Path | None) -> None:
        if not frontend_dir.is_dir() or not (frontend_dir / "package.json").is_file():
            return

        subprocess.run([npm, "ci"], check=True, cwd=str(frontend_dir))
        subprocess.run([npm, "run", "build"], check=True, cwd=str(frontend_dir))

        build_dir = frontend_dir / "build"
        # ``static_dir is None`` means the build is served in place (postup); a
        # sibling copy is only made for tools that gitignore their build/ (bim).
        if static_dir is not None and build_dir.is_dir():
            if static_dir.exists():
                shutil.rmtree(static_dir)
            shutil.copytree(build_dir, static_dir)
