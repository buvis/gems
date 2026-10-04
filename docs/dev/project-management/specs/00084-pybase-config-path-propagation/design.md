# pybase: propagate the selected --config / --config-dir to tool config loaders

<!-- design; migrated from PRD 00084 flat file -->

## Implementation

### Library: src/lib/buvis/pybase/configuration/
- **`click_integration.py`** — in the `buvis_options` wrapper, after
  `resolver.resolve(...)`, set `ctx.obj["config_dir"] = config_dir` and
  `ctx.obj["config_path"] = config` (raw values, `None` when unset). Additive.
- **`loader.py`** — add `config_path: Path | None = None` to
  `find_config_files_ranked` (or a thin `resolve_config_layers` helper) so an
  explicit file is appended as the top-priority layer; keep `config_dir`
  behaviour unchanged. Do not break existing callers (default `None` = today's
  behaviour).

### Tools
- **`backup/config.py`** — `load_config(config_dir=None, config_path=None)`
  threads both into the loader; **`backup/cli.py`** reads
  `ctx.obj.get("config_dir")` / `ctx.obj.get("config_path")` and passes them, and
  removes the deferral comment left at `load_config()` on PR #179.
- **`sysup`** (nice-to-have) — the same two-line threading.

### Tests
- **Location**: `tests/lib/pybase/configuration/` for the library change,
  `tests/tools/backup/` for the tool threading.
- Cover: `buvis_options` populates `ctx.obj["config_path"]` / `["config_dir"]`
  from the flags (and leaves them `None` when absent); `find_config_files_ranked`
  places an explicit `config_path` at the top of the returned layer order;
  `backup --config FILE` loads its plan from FILE (a fixture config whose
  instance differs from the default), and `backup --config-dir DIR` loads from
  DIR; no existing `buvis_options` / loader test regresses.

## Provenance

Surfaced by Copilot's round-3 review of PR #179 (the `backup` gem), on
`src/tools/backup/cli.py`: `buvis_options` consumes `--config` / `--config-dir`
but `load_config` re-discovers the default config locations, so
`backup --config FILE` resolves settings from FILE yet runs a different plan.
Deferred from that PR on 2026-09-27 because the correct fix changes the shared
`buvis_options` / Click-context contract in `src/lib/`, affecting every gem — a
cross-cutting library change that warrants its own PRD with its own tests rather
than an inline change in one tool's review round. Grounded against
`click_integration.py`, `loader.py`, and `backup/config.py` as they stood that
day; a deferral comment was left at `backup/config.py::load_config()` pointing
here.
