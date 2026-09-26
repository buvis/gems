from __future__ import annotations

from pathlib import Path

import pytest

_BACKUP_ROOT = Path(__file__).resolve().parents[3] / "src" / "tools" / "backup"

# The CLI layer (cli.py) is the only place allowed to render/panic. config.py,
# runner.py, every capability, and shared/ must return/yield StepResult or raise
# FatalError — never call console.panic or sys.exit (repo Invariants section).
_LIBRARY_FILES = [
    _BACKUP_ROOT / "config.py",
    _BACKUP_ROOT / "runner.py",
    *sorted((_BACKUP_ROOT / "capabilities").glob("*.py")),
    *sorted((_BACKUP_ROOT / "shared").glob("*.py")),
]


class TestLibraryLayerInvariants:
    @pytest.mark.parametrize("path", _LIBRARY_FILES, ids=lambda p: p.name)
    def test_no_panic_or_sys_exit(self, path: Path) -> None:
        source = path.read_text(encoding="utf-8")
        assert "console.panic" not in source, f"{path.name} must not call console.panic"
        assert "sys.exit" not in source, f"{path.name} must not call sys.exit"
        assert "print(" not in source, f"{path.name} must not call print"
        assert "click.echo" not in source, f"{path.name} must not call click.echo"

    def test_files_exist(self) -> None:
        assert len(_LIBRARY_FILES) >= 5
        for path in _LIBRARY_FILES:
            assert path.is_file()
