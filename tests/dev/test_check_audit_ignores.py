from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_script = Path(__file__).resolve().parents[2] / "dev" / "bin" / "check_audit_ignores.py"
_spec = importlib.util.spec_from_file_location("check_audit_ignores", _script)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["check_audit_ignores"] = _mod
_spec.loader.exec_module(_mod)

load_ignores = _mod.load_ignores
find_stale = _mod.find_stale
main = _mod.main

# One stale CVE (a fix is now available) and one genuinely-unfixable CVE (no fix).
STALE_CVE = "CVE-2000-11111"
UNFIXABLE_CVE = "CVE-2000-22222"

# pip-audit `dependencies` list: the stale package reports a fix_versions,
# the unfixable one reports an empty fix_versions.
AUDIT_DEPS = [
    {"name": "clean-pkg", "version": "1.0.0", "vulns": []},
    {
        "name": "stalepkg",
        "version": "1.0.0",
        "vulns": [{"id": STALE_CVE, "fix_versions": ["1.1.0"], "aliases": []}],
    },
    {
        "name": "unfixablepkg",
        "version": "2.0.0",
        "vulns": [{"id": UNFIXABLE_CVE, "fix_versions": [], "aliases": []}],
    },
]

IGNORES = [
    {
        "cve": STALE_CVE,
        "package": "stalepkg",
        "reason": "was unfixable when added",
        "date_added": "2026-01-01",
    },
    {
        "cve": UNFIXABLE_CVE,
        "package": "unfixablepkg",
        "reason": "no fix released upstream",
        "date_added": "2026-01-01",
    },
]

VALID_CONFIG = """\
[[ignore]]
cve = "CVE-2000-22222"
package = "unfixablepkg"
reason = "no fix released upstream"
date_added = "2026-01-01"
"""


class TestFindStale:
    def test_flags_stale_but_not_unfixable(self):
        errors = find_stale(IGNORES, AUDIT_DEPS)
        assert len(errors) == 1
        assert STALE_CVE in errors[0]
        assert "1.1.0" in errors[0]
        assert UNFIXABLE_CVE not in "".join(errors)

    def test_unfixable_alone_passes(self):
        unfixable_only = [e for e in IGNORES if e["cve"] == UNFIXABLE_CVE]
        assert find_stale(unfixable_only, AUDIT_DEPS) == []

    def test_no_ignores_passes(self):
        assert find_stale([], AUDIT_DEPS) == []

    def test_cve_not_present_in_audit_passes(self):
        gone = [{"cve": "CVE-2000-99999", "package": "p", "reason": "r", "date_added": "2026-01-01"}]
        assert find_stale(gone, AUDIT_DEPS) == []

    def test_alias_match_counts_as_fixable(self):
        deps = [
            {
                "name": "aliaspkg",
                "version": "1.0",
                "vulns": [{"id": "GHSA-xxxx", "fix_versions": ["2.0"], "aliases": [STALE_CVE]}],
            },
        ]
        errors = find_stale([IGNORES[0]], deps)
        assert len(errors) == 1
        assert STALE_CVE in errors[0]


class TestLoadIgnores:
    def test_valid_config(self, tmp_path):
        cfg = tmp_path / "ignores.toml"
        cfg.write_text(VALID_CONFIG)
        entries = load_ignores(cfg)
        assert len(entries) == 1
        assert entries[0]["cve"] == UNFIXABLE_CVE

    def test_empty_list_config(self, tmp_path):
        cfg = tmp_path / "ignores.toml"
        cfg.write_text("ignore = []\n")
        assert load_ignores(cfg) == []

    def test_missing_file_is_empty(self, tmp_path):
        assert load_ignores(tmp_path / "nope.toml") == []

    def test_missing_field_rejected(self, tmp_path):
        cfg = tmp_path / "ignores.toml"
        cfg.write_text(
            '[[ignore]]\ncve = "CVE-2000-33333"\npackage = "p"\nreason = "r"\n',
        )
        with pytest.raises(ValueError, match="date_added"):
            load_ignores(cfg)

    def test_empty_field_rejected(self, tmp_path):
        cfg = tmp_path / "ignores.toml"
        cfg.write_text(
            '[[ignore]]\ncve = "CVE-2000-33333"\npackage = ""\nreason = "r"\ndate_added = "2026-01-01"\n',
        )
        with pytest.raises(ValueError, match="package"):
            load_ignores(cfg)


class TestMainPrintFlags:
    def test_print_flags_from_config(self, tmp_path, monkeypatch, capsys):
        cfg = tmp_path / "ignores.toml"
        cfg.write_text(VALID_CONFIG)
        monkeypatch.setattr(_mod, "_default_config_path", lambda: cfg)
        rc = main(["--print-ignore-flags"])
        assert rc == 0
        out = capsys.readouterr().out.strip()
        assert out == f"--ignore-vuln {UNFIXABLE_CVE}"

    def test_print_flags_empty_config(self, tmp_path, monkeypatch, capsys):
        cfg = tmp_path / "ignores.toml"
        cfg.write_text("ignore = []\n")
        monkeypatch.setattr(_mod, "_default_config_path", lambda: cfg)
        rc = main(["--print-ignore-flags"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == ""

    def test_no_ignores_default_mode_passes_without_pip_audit(self, tmp_path, monkeypatch, capsys):
        cfg = tmp_path / "ignores.toml"
        cfg.write_text("ignore = []\n")
        monkeypatch.setattr(_mod, "_default_config_path", lambda: cfg)

        def _boom() -> list[dict]:
            raise AssertionError("pip-audit must not run when there are no ignores")

        monkeypatch.setattr(_mod, "_run_pip_audit", _boom)
        rc = main([])
        assert rc == 0
        assert "nothing to guard" in capsys.readouterr().out

    def test_stale_entry_fails_default_mode(self, tmp_path, monkeypatch, capsys):
        cfg = tmp_path / "ignores.toml"
        cfg.write_text(
            '[[ignore]]\ncve = "CVE-2000-11111"\npackage = "stalepkg"\n'
            'reason = "was unfixable"\ndate_added = "2026-01-01"\n',
        )
        monkeypatch.setattr(_mod, "_default_config_path", lambda: cfg)
        monkeypatch.setattr(_mod, "_run_pip_audit", lambda: AUDIT_DEPS)
        rc = main([])
        assert rc == 1
        assert "Stale pip-audit suppressions" in capsys.readouterr().out

    def test_invalid_config_fails(self, tmp_path, monkeypatch, capsys):
        cfg = tmp_path / "ignores.toml"
        cfg.write_text('[[ignore]]\ncve = "CVE-2000-33333"\n')
        monkeypatch.setattr(_mod, "_default_config_path", lambda: cfg)
        rc = main([])
        assert rc == 1
        assert "Invalid audit ignore config" in capsys.readouterr().out
