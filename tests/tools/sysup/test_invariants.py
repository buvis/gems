from __future__ import annotations

from pathlib import Path

import pytest

_SYSUP_ROOT = Path(__file__).resolve().parents[3] / "src" / "tools" / "sysup"

# The CLI layer (cli.py) is the only place allowed to render/panic. config.py,
# runner.py and every capability must return/yield StepResult or raise
# FatalError — never call console.panic or sys.exit (repo Invariants section).
_LIBRARY_FILES = [
    _SYSUP_ROOT / "config.py",
    _SYSUP_ROOT / "runner.py",
    *sorted((_SYSUP_ROOT / "capabilities").glob("*.py")),
]


class TestLibraryLayerInvariants:
    @pytest.mark.parametrize("path", _LIBRARY_FILES, ids=lambda p: p.name)
    def test_no_panic_or_sys_exit(self, path: Path) -> None:
        source = path.read_text(encoding="utf-8")
        assert "console.panic" not in source, f"{path.name} must not call console.panic"
        assert "sys.exit" not in source, f"{path.name} must not call sys.exit"

    def test_files_exist(self) -> None:
        assert len(_LIBRARY_FILES) >= 6
        for path in _LIBRARY_FILES:
            assert path.is_file()
