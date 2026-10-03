"""Phase 0 exit criterion -- the payload resolves from a BUILT WHEEL.

The PRD requires ``payload_files`` to find the packaged ``SKILL.md`` through
``importlib.resources`` from an installed wheel, not merely from the source
tree. This proves the data file is actually packaged: hatchling includes files
under a declared package dir, but a packaging-config regression would silently
drop it and the source-tree tests would not notice.

The check builds one wheel, asserts the payload is in the wheel archive, then
unpacks it and resolves the payload through ``importlib.resources`` in a clean
subprocess whose ``cwd`` is OUTSIDE the repo and whose only ``klyreon`` on the
path is the unpacked wheel -- so the source tree cannot satisfy the import.

Skipped automatically when the build toolchain is unavailable.

Opt-in only. Building the wheel compiles the project's maturin Rust extension
*inside the pytest process*; on the CI matrix that corrupts the interpreter and
it segfaults at teardown (exit 139) AFTER every test has passed -- a crash the
warm local toolchain does not reproduce. So this module runs only when
``BUVIS_WHEEL_BUILD_TESTS=1`` is set (locally, or in a dedicated build-proof
job), the same opt-in pattern the snapshot suite uses for its canonical-only
tests. The per-cell unit matrix must never shell out to ``uv build``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.klyreon,
    pytest.mark.skipif(
        os.environ.get("BUVIS_WHEEL_BUILD_TESTS") != "1",
        reason=(
            "in-process `uv build` compiles the maturin Rust extension and "
            "segfaults the CI interpreter at teardown; set BUVIS_WHEEL_BUILD_TESTS=1 "
            "to run this build-proof locally or in a dedicated job"
        ),
    ),
]

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PAYLOAD_ARCHIVE_PATH = "klyreon/assets/payload/claude/skills/klyreon/SKILL.md"


def _uv() -> str | None:
    return shutil.which("uv")


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    uv = _uv()
    if uv is None:
        pytest.skip("uv not available to build a wheel")
    out = tmp_path_factory.mktemp("wheel")
    env = {**os.environ, "BUVIS_SKIP_FRONTEND": "1"}
    proc = subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(out)],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"wheel build unavailable in this environment: {proc.stderr[-500:]}")
    wheels = list(out.glob("*.whl"))
    if not wheels:
        pytest.skip("no wheel produced")
    return wheels[0]


def test_payload_is_packaged_in_the_wheel(built_wheel: Path) -> None:
    """The SKILL.md data file must actually be inside the wheel archive."""
    with zipfile.ZipFile(built_wheel) as whl:
        names = set(whl.namelist())
    assert _PAYLOAD_ARCHIVE_PATH in names, (
        f"payload missing from wheel; present klyreon/assets/* entries: "
        f"{sorted(n for n in names if n.startswith('klyreon/assets/'))}"
    )


def test_payload_resolves_via_importlib_from_unpacked_wheel(built_wheel: Path, tmp_path: Path) -> None:
    """importlib.resources resolves the payload from the wheel, not the source tree."""
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir()
    with zipfile.ZipFile(built_wheel) as whl:
        whl.extractall(unpacked)

    probe = (
        "from klyreon.assets.registry import payload_files;"
        "f = payload_files('claude');"
        "assert len(f) == 1, f;"
        "payload, handle = f[0];"
        "assert handle.is_file();"
        "text = handle.read_text(encoding='utf-8');"
        "assert 'klyreon-vault' in text, text[:80];"
        "import klyreon; print('WHEEL_OK ' + klyreon.__file__)"
    )
    # Clean env: PYTHONPATH is the unpacked wheel ONLY; cwd outside the repo.
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPATH"] = str(unpacked)
    run = subprocess.run(
        [sys.executable, "-S", "-c", probe],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert run.returncode == 0, f"payload did not resolve from the wheel:\nSTDOUT {run.stdout}\nSTDERR {run.stderr}"
    assert "WHEEL_OK" in run.stdout, run.stdout
    # Prove the resolved klyreon came from the unpacked wheel, not the repo src.
    resolved_file = run.stdout.split("WHEEL_OK ", 1)[1].strip()
    assert str(unpacked) in resolved_file, f"klyreon resolved from {resolved_file}, not the wheel"
