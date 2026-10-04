# pybase: propagate the selected --config / --config-dir to tool config loaders

<!-- tasks; migrated from PRD 00084 flat file -->

## Tasks

### Phase 0: library — publish + accept the selection
- [ ] `buvis_options` wrapper stores `config_dir` / `config_path` on `ctx.obj` —
      Acceptance: a probe command reads both back from its context after invocation.
- [ ] `find_config_files_ranked` (or helper) accepts an explicit `config_path`
      appended as highest-priority layer — Acceptance: unit test asserts layer
      order with and without an explicit file; existing callers unaffected.

### Phase 1: tool threading
- [ ] `backup/config.py::load_config` gains `config_path`; `backup/cli.py` threads
      `ctx.obj` selection in and drops the deferral comment — Acceptance:
      `backup --config <fixture>` runs the fixture's plan (asserted via `--list`
      or a dry-run), not the default plan.
- [ ] (nice-to-have) same threading for sysup — Acceptance: `sysup --config
      <fixture>` runs the fixture's plan.
