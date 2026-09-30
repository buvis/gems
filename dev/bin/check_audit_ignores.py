"""Guard against stale pip-audit suppressions.

`dev/audit/pip-audit-ignores.toml` is the single source of truth for every CVE
the dependency-audit step is allowed to ignore. This script has two jobs, both
deterministic (no LLM):

  * ``--print-ignore-flags`` emits the ``--ignore-vuln <CVE>`` arguments the
    lint step passes to pip-audit, generated from the config so there are no
    anonymous inline ignores in the workflow.

  * default mode runs pip-audit against the resolved environment and FAILS when
    any ignored CVE now has a fix available (a suppression gone stale) or when
    an entry is malformed. This is what forces "fix, don't ignore".

The staleness decision (`find_stale`) is a pure function over the parsed
pip-audit JSON and the parsed config, so it is unit-tested without invoking
pip-audit or the network.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import tomllib

_REQUIRED_FIELDS = ("cve", "package", "reason", "date_added")


def load_ignores(config_path: Path) -> list[dict[str, str]]:
    """Parse the ignore audit config into a list of entry dicts.

    Raises ValueError on a malformed entry so a suppression can never be added
    without every justification field.
    """
    if not config_path.is_file():
        return []
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    raw = data.get("ignore", [])
    if not isinstance(raw, list):
        msg = f"'ignore' must be a list of tables, got {type(raw).__name__}"
        raise ValueError(msg)
    entries: list[dict[str, str]] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            msg = f"ignore entry #{i} is not a table"
            raise ValueError(msg)
        missing = [f for f in _REQUIRED_FIELDS if not str(entry.get(f, "")).strip()]
        if missing:
            msg = f"ignore entry #{i} ({entry.get('cve', '?')}) missing/empty fields: {', '.join(missing)}"
            raise ValueError(msg)
        entries.append({f: str(entry[f]).strip() for f in _REQUIRED_FIELDS})
    return entries


def _fix_versions_by_cve(audit_deps: list[dict]) -> dict[str, list[str]]:
    """Map every vuln id in the audit output to its reported fix_versions."""
    fixes: dict[str, list[str]] = {}
    for dep in audit_deps:
        for vuln in dep.get("vulns", []) or []:
            ids = [vuln.get("id", "")]
            ids.extend(vuln.get("aliases", []) or [])
            fversions = [v for v in (vuln.get("fix_versions", []) or []) if v]
            for vid in ids:
                if vid:
                    fixes[vid] = fversions
    return fixes


def find_stale(
    ignores: list[dict[str, str]],
    audit_deps: list[dict],
) -> list[str]:
    """Return an error message per ignored CVE that now has a fix available.

    Pure: takes the parsed ignore entries and the parsed pip-audit
    ``dependencies`` list, returns human-readable errors. Empty means all
    listed suppressions are still genuinely unfixable in the resolved tree.
    """
    fixes = _fix_versions_by_cve(audit_deps)
    errors: list[str] = []
    for entry in ignores:
        cve = entry["cve"]
        fix_versions = fixes.get(cve)
        if fix_versions:
            errors.append(
                f"{cve} ({entry['package']}) is ignored as unfixable "
                f"(reason: {entry['reason']}, added {entry['date_added']}) "
                f"but a fix is now available in the resolved tree: "
                f"{', '.join(fix_versions)}. Upgrade and remove this entry."
            )
    return errors


def _run_pip_audit() -> list[dict]:
    """Run pip-audit against the resolved env and return its dependencies list."""
    proc = subprocess.run(
        ["uv", "run", "pip-audit", "--skip-editable", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if not proc.stdout.strip():
        msg = f"pip-audit produced no JSON output (exit {proc.returncode}): {proc.stderr.strip()}"
        raise RuntimeError(msg)
    payload = json.loads(proc.stdout)
    # pip-audit emits either a bare list or {"dependencies": [...]} depending on version.
    if isinstance(payload, dict):
        return list(payload.get("dependencies", []))
    return list(payload)


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "dev" / "audit" / "pip-audit-ignores.toml"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    config_path = _default_config_path()

    try:
        ignores = load_ignores(config_path)
    except (ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"Invalid audit ignore config ({config_path}): {exc}")
        return 1

    if "--print-ignore-flags" in argv:
        # Emit the flags the lint step feeds to pip-audit, from the config only.
        flags: list[str] = []
        for entry in ignores:
            flags.extend(["--ignore-vuln", entry["cve"]])
        print(" ".join(flags))
        return 0

    if not ignores:
        print("No pip-audit ignores configured — nothing to guard.")
        return 0

    try:
        audit_deps = _run_pip_audit()
    except (RuntimeError, json.JSONDecodeError, FileNotFoundError) as exc:
        print(f"Could not run pip-audit to check ignore staleness: {exc}")
        return 1

    stale = find_stale(ignores, audit_deps)
    if stale:
        print("Stale pip-audit suppressions (a fix is now available):")
        for e in stale:
            print(f"  - {e}")
        return 1

    print(f"All {len(ignores)} pip-audit ignore(s) still unfixable in the resolved tree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
