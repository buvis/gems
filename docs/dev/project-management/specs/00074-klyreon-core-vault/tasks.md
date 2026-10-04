# klyreon A: gem scaffold, spec engine, vault contract, git layer

<!-- tasks; migrated from PRD 00074 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: A real gem, plus the vocabulary and shape of the format in code.

**Tasks**:
- [ ] Scaffold `klyreon`, wire console script, wheel package, pytest marker, docs stub, CHANGELOG (no deps) - Acceptance: `uv run klyreon --help` exits 0; `dev/bin/check_tool_wiring.py` passes; `pytest -m klyreon` collects.
- [ ] `KlyreonSettings` with the nine settings above (no deps) - Acceptance: env-prefix and `--config` override tests pass; defaults match this PRD.
- [ ] `spec/enums.py` and `spec/model.py`: the closed vocabularies and typed documents (no deps) - Acceptance: every enum matches the spec tables (6.1, 6.2, 7.1, 7.2, 7.3, 7.6, 8) exactly, asserted by a test that lists the members.
- [ ] Write spec section 3.3 defining auxiliary files (`wiki/mocs/`, `wiki/trails/`): required `id`, `title`, `created`, `kind` (`moc` or `trail`), H1 matches `title`, no `type` field because they are neither species (no deps) - Acceptance: the spec's "internal format is deliberately not specified" sentence in 3.1 is replaced by a pointer to 3.3.

**Exit Criteria**: The package imports on a core-only install; enums and models are tested against the spec.

### Phase 1: Core
**Goal**: The format is readable, writable, and checkable; the vault is findable and commitable.

**Tasks**:
- [ ] `spec/parser.py` + `spec/writer.py`: YAML loader with the sexagesimal resolver stripped and string `id`; H1 split; unknown-field preservation; serialization through `atomic_write` (depends on: Phase 0) - Acceptance: round-trip test over the valid fixture corpus is byte-stable; a fixture carrying `aliases` and `cssclasses` keeps both; a fixture with `id: 20260411145300` unquoted parses as the string `"20260411145300"`.
- [ ] `spec/validator.py`: file-level rules (depends on: Phase 0) - Acceptance: one invalid fixture per rule listed in the File-level validation feature, each producing exactly its own error and no other.
- [ ] `spec/validator.py`: vault-level rules including the transitive-cycle check (depends on: parser) - Acceptance: fixtures for dangling `sources`/`links.to`/`mocs`/`doubts[].target.to`, a `links.to` pointing at a source document, a three-hop `broader-than` cycle, a colon-prefixed tag, an orphan concept zettel, an oversized body, a stale review.
- [ ] `vault/config.py` + `vault/paths.py`: root discovery and path confinement (depends on: Phase 0) - Acceptance: `$KLYREON_ROOT` wins over the config file; relative root, missing root directory, missing config, `..` segment, and an escaping absolute path each fail loudly with a distinct message.
- [ ] `vault/ids.py`: collision-bumped ID allocation (depends on: Phase 0) - Acceptance: allocating ten IDs inside one frozen second yields ten consecutive unique 14-digit IDs, and each matches the `created` value written with it.
- [ ] `vault/git.py` + `vault/state.py`: scoped commit, autonomy gate, authorship, staleness state (depends on: Phase 0) - Acceptance: on a temp repo, a commit of two paths leaves a third file's uncommitted edit modified and unstaged; the commit author is the configured identity; `is_git_vault` is false for a plain directory and `require_git_for_autonomy` returns a failing `CommandResult` there; `is_human_authored` is true after a commit by another identity.

**Exit Criteria**: A hand-built fixture vault parses, validates, and commits; no bare `Path.write_text` outside `spec/writer.py` (asserted by a grep test).

### Phase 2: Integration
**Goal**: The five commands a user can run today.

**Tasks**:
- [ ] `klyreon init` with idempotence, `--force`, voice starter, and the non-git warning (depends on: Phase 1) - Acceptance: init then validate on a temp dir is clean; a second init reports everything as existing and changes no mtime; init in a non-git dir warns and still succeeds; init never runs `git init` (asserted by a subprocess spy).
- [ ] `klyreon new` and `klyreon validate` wired through the CLI with `console.report_result` (depends on: Phase 1) - Acceptance: `new --type note --concept-type thesis` produces a file that validates; `validate` exits 1 on the invalid corpus and 0 on the valid one; `--json` output parses.
- [ ] `klyreon export-claims` with the JSON contract and the in-vault write refusal (depends on: Phase 1) - Acceptance: schema test over the 200-zettel fixture; a rejected zettel's claim is present and labelled; `--out` inside the root fails with a clear message.
- [ ] `klyreon status` plus the CLI-group staleness warning (depends on: Phase 1) - Acceptance: counts match the fixture vault; absent state warns; `last_maintain` older than the window warns; a fresh one does not.
- [ ] Docs page, CHANGELOG Added entry, mypy strict, ruff, coverage (depends on: Phase 1) - Acceptance: all gems gates green in CI.

**Exit Criteria**: Every Success Metric holds on the fixture corpus and on a real vault created by `init`.
