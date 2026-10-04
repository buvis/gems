# pidash hooks: lock, fsync, and preserve order

<!-- tasks; migrated from PRD 00049 flat file -->

## Tasks

### Phase 0: Foundation
- [ ] Add a flock-based `with_state_lock` context manager around the RMW in the state-mutating hooks (depends on: 00041) — Acceptance: a test with two interleaved read-modify-write cycles leaves both task updates present (no lost update).

### Phase 1: Core
- [ ] fsync-before-replace in `save_settings` (#111); repoint pidash atomic-write copies to `pybase.filesystem` (depends on: 00041) — Acceptance: settings write is durable; `rg` finds no second atomic-write copy in pidash.
- [ ] Preserve existing hook-array order incl. non-dict entries in install (#112) — Acceptance: install-order regression test passes.
- [ ] Add `@click.pass_context` to the `hooks` subgroup (#113); extract the shared row-rendering helper used by `hooks_status` and `_render_status_failure`, closing #114 as not-reproducible — Acceptance: rows render via one helper; subcommands receive context.
