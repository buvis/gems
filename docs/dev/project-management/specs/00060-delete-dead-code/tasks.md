# Delete dead code: uv adapter, hello_world, configuration/examples

<!-- tasks; migrated from PRD 00060 flat file -->

## Tasks

### Phase 0: Foundation
- [ ] Delete `adapters/uv/` + tests + docs + `__init__` exports (no deps) — Acceptance: `rg -i "UvAdapter|UvToolManager|adapters.uv"` returns nothing outside history; tests green.

### Phase 1: Core
- [ ] Delete `hello_world` tool + tests + docs; remove all `pyproject.toml`/README references; repoint completions examples (depends on: Phase 0) — Acceptance: wheel builds; `hello-world` no longer a console script; scaffold still works.
- [ ] Delete `configuration/examples/` + tests (depends on: Phase 0) — Acceptance: `pytest` green; nothing imports the examples.
