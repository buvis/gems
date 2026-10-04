# Retire the pidash tool from buvis-gems

<!-- tasks; migrated from PRD 00071 flat file -->

## Tasks

### Phase 0: Foundation

- [ ] Re-check the premise, then delete `src/tools/pidash/` and `tests/tools/pidash/` — Acceptance: premise re-check runs first and skips-and-reports if the directory is already absent; otherwise both trees are gone and `uv run pytest` collects green with no missing-marker error.
- [ ] Remove the `pidash` console script, wheel package entry, optional-dependency extra (including from `all`), and pytest marker from `pyproject.toml` — Acceptance: `rg pidash pyproject.toml` returns nothing; `uv sync --all-extras` succeeds; `uv run pytest -m lib` still selects normally.
- [ ] Remove `docs/source/tools/pidash.rst` and its toctree entry — Acceptance: the file is gone, no toctree references it, and `uv run sphinx-build -b html docs/source docs/build/html` completes with no warning about a missing or unreferenced document.
- [ ] Add the CHANGELOG Removed entry naming tracon as successor — Acceptance: `CHANGELOG.md` carries a `**pidash**:` bullet under Removed in `[Unreleased]` that names `tracon` (buvis home repo) and states that no gems-side replacement ships.
