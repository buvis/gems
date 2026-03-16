from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_script = Path(__file__).resolve().parents[2] / "dev" / "bin" / "check_tool_wiring.py"
_spec = importlib.util.spec_from_file_location("check_tool_wiring", _script)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["check_tool_wiring"] = _mod
_spec.loader.exec_module(_mod)

check = _mod.check

MINIMAL_PYPROJECT = """\
[project.scripts]
alpha = "alpha.cli:cli"
bravo = "bravo.cli:cli"

[tool.hatch.build.targets.wheel]
packages = [
  "src/lib/buvis",
  "src/tools/alpha",
  "src/tools/bravo",
]
"""


def _make_tool(root: Path, snake: str) -> None:
    d = root / "src" / "tools" / snake
    d.mkdir(parents=True, exist_ok=True)
    (d / "__init__.py").touch()


@pytest.fixture
def wired_repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text(MINIMAL_PYPROJECT)
    _make_tool(tmp_path, "alpha")
    _make_tool(tmp_path, "bravo")
    return tmp_path


class TestCheckToolWiring:
    def test_all_wired_passes(self, wired_repo):
        assert check(wired_repo) == []

    def test_missing_scripts_entry(self, wired_repo):
        _make_tool(wired_repo, "charlie")
        errors = check(wired_repo)
        assert any("project.scripts" in e and "charlie" in e for e in errors)

    def test_missing_packages_entry(self, wired_repo):
        _make_tool(wired_repo, "charlie")
        errors = check(wired_repo)
        assert any("package" in e and "src/tools/charlie" in e for e in errors)

    def test_error_includes_exact_line_to_add(self, wired_repo):
        _make_tool(wired_repo, "my_tool")
        errors = check(wired_repo)
        assert any('my-tool = "my_tool.cli:cli"' in e for e in errors)
        assert any('"src/tools/my_tool"' in e for e in errors)

    def test_extra_pyproject_entry_no_error(self, wired_repo):
        """Extra entries in pyproject without matching dirs are OK."""
        text = MINIMAL_PYPROJECT.replace(
            "[project.scripts]",
            '[project.scripts]\norphan = "orphan.cli:cli"',
        )
        (wired_repo / "pyproject.toml").write_text(text)
        assert check(wired_repo) == []

    def test_pycache_ignored(self, wired_repo):
        pycache = wired_repo / "src" / "tools" / "__pycache__"
        pycache.mkdir(parents=True)
        assert check(wired_repo) == []

    def test_dir_without_init_ignored(self, wired_repo):
        bare = wired_repo / "src" / "tools" / "bare_dir"
        bare.mkdir(parents=True)
        assert check(wired_repo) == []

    def test_no_pyproject(self, tmp_path):
        errors = check(tmp_path)
        assert any("pyproject.toml not found" in e for e in errors)
