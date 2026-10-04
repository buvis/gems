# pybase config: directive-tagged list merge (append / remove)

<!-- tasks; migrated from PRD 00080 flat file -->

## Tasks

### Phase 0: Merge grammar + tests
- [ ] Add `key+` / `key-` directive handling to `_deep_merge` with append-dedup,
      remove, same-layer +then-, and directive stripping — Acceptance: the
      three-layer excludes example resolves to
      `[node_modules, __pycache__, .terraform, .gradle, .cache]`.
- [ ] Non-list base is a clear loader error — Acceptance: `excludes+` over a
      scalar `excludes` raises the loader's error type, not a bare exception.
- [ ] Regression: every plain-key list still replaces; a fixture from an existing
      tool config resolves unchanged — Acceptance: existing loader/resolver tests
      stay green with no edits.

### Phase 1: Typo guard (nice to have)
- [ ] `merge_configs(known_keys=...)` warns on a directive targeting an unknown
      key — Acceptance: `exclude+` (missing the `s`) with `known_keys={"excludes"}`
      logs a warning; omitting `known_keys` stays silent.

### Phase 2: Docs + follow-up note
- [ ] Document the directive grammar on the config schema page with the excludes
      example and the plain-key reset escape hatch.
- [ ] File the sysup follow-up: once this lands, sysup MAY revisit its keyed-map
      workaround (00079) — it can keep the map (still valid) or, if a list shape
      reads better for any of its list-valued fields, use `+`/`-`. Not required;
      captured so the decision isn't lost.
