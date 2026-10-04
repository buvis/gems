# Delete dead code: uv adapter, hello_world, configuration/examples

<!-- requirements; migrated from PRD 00060 flat file -->

## Problem

Three chunks of the codebase are dead weight kept alive only by their own tests, docs, and packaging — ~1,240 LOC total:

1. **`adapters/uv` (UvAdapter, UvToolManager)** — 220 LOC + 383 LOC tests. Zero production consumers repo-wide (only its own lazy export in `adapters/__init__.py`, docs, and tests). The updater subsystem superseded it. (Confirmed 2026-07-10: no out-of-repo consumers of the published wheel.)
2. **`hello_world` tool** — ~440 LOC (tool + tests + docs). `dev/bin/scaffold.py` generates new tools from **inline string templates**, not from hello_world, so it is a second, already-diverged copy of the tool shape, shipped to PyPI with an extra, a console script, and a docs page.
3. **`configuration/examples/` (MusicSettings, PhotoSettings)** — 68 LOC + 114 LOC tests, consumed only by their own tests; muc/puc have real settings.

## Solution

Delete all three, plus their tests, docs entries, and packaging references. (Out-of-repo uv-adapter consumers: confirmed none, 2026-07-10.)

## Requirements

### Must have
- Remove `src/lib/buvis/pybase/adapters/uv/` and its tests; drop the lazy exports in `adapters/__init__.py` and the `docs/source/adapters.rst` section; prune `test_adapters_init.py` references.
- Remove `src/tools/hello_world/` and its tests + `docs/source/tools/hello-world.rst`; drop it from `pyproject.toml` (packages list, `[project.scripts]`, extras, markers), `README.md`, and repoint any `docs/source/completions.rst` example to another tool.
- Remove `src/lib/buvis/pybase/configuration/examples/` and its tests.
- `uv sync`, `mypy src/lib src/tools`, and `pytest` all green after removal; the wheel still builds.
- CHANGELOG entry under Removed in the same commit (user-visible: the `hello-world` console script goes away) — the global changelog rule makes this mandatory, not optional.

### Nice to have
- None.

## Success Criteria

- ~1,240 LOC of test-backed dead weight removed; build + type-check + tests green.
- CHANGELOG notes the removed `hello-world` command.
