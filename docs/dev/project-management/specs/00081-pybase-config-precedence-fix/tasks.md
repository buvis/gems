# pybase config: fix inverted precedence in the config resolver

<!-- tasks; migrated from PRD 00081 flat file -->

## Tasks

### Phase 0: Fix + test
- [ ] Add `find_config_files_ranked` (or equivalent) returning discovered files
      low-to-high priority — Acceptance: unit test asserts the order for a
      two-dir, three-stem fixture.
- [ ] Replace the resolver's `reversed()` with the ranked order — Acceptance: the
      empirical case yields the tool-specific value; a cross-dir case yields the
      `$BUVIS_CONFIG_DIR` value.
- [ ] Regression test: a single file per key resolves identically to before.
