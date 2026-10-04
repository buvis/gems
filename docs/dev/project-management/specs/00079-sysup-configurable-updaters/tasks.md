# sysup: configurable, dotfiles-shareable system updaters

<!-- tasks; migrated from PRD 00079 flat file -->

## Tasks

### Phase 0: Schema + loader
- [ ] Pydantic models for the keyed map, `run`/`use` entries, and envelope —
      Acceptance: valid config loads; unknown keys, both/neither `steps`/`use`,
      unknown capability names and unknown `with:` inputs raise clear config
      errors surfaced through `console`.
- [ ] Applicability + ordering: filter by `when` (os + `check` via `shutil.which`
      at run time), sort by `order` — Acceptance: a mac-only entry is skipped and
      reported on linux; entries run ascending.

### Phase 1: Capabilities
- [ ] Relocate helm empty-repo guard, mason Lua probe (timeout + log tail),
      per-interpreter pip, and sudo priming into the capability registry —
      Acceptance: each reproduces its current behaviour under its existing tests,
      re-pointed at the capability; sudo refresher releases on `BaseException`.

### Phase 2: Runner + CLI
- [ ] Runner executes `run` (argv early-abort) and `use` entries with
      interactive/timeout/continue_on_error; runs `prime:` first — Acceptance:
      brew aborts on first failure; npm-check inherits stdio; a `continue_on_error`
      entry keeps going.
- [ ] Single `sysup` entry point with `--only`/`--tag`; remove the four
      subcommands and `sys.platform` guards — Acceptance: `sysup` runs all
      applicable; `--tag python` runs only tagged entries.

### Phase 3: Defaults + migration
- [ ] Bundled default reproducing mac/pip/nvim/uv/helm/mise + wsl/apt/snap —
      Acceptance: on macOS with no user config, `sysup` runs the same steps as
      today's `sysup mac`; on linux, as `sysup wsl`.
- [ ] Docs: `buvis-sysup.yaml` schema, capability catalogue, dotfiles-share +
      machine-override example, migration note (subcommands removed) — Acceptance:
      a user can copy the example and add one machine-specific entry.
