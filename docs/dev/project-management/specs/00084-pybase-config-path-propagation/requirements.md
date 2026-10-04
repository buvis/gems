# pybase: propagate the selected --config / --config-dir to tool config loaders

<!-- requirements; migrated from PRD 00084 flat file -->

## Problem

Every gem's CLI inherits `--config FILE` and `--config-dir DIRECTORY` from the
shared `buvis_options` decorator. Today those two options are **half-wired**: the
`buvis_options` wrapper consumes them to resolve the tool's *settings* object
(`ConfigResolver.resolve(..., config_dir=..., config_path=...)`), but it then
invokes the wrapped callback **without** forwarding either value, and does not
store them in the Click context. The callback therefore cannot learn which config
the user selected.

Tools that load their own YAML config (sysup, backup) call
`ConfigurationLoader.find_config_files_ranked(tool, config_dir=None)` with no
argument threaded through from the CLI, so they **independently re-discover** the
default config locations and ignore the user's `--config` / `--config-dir`
entirely. The result is a silent split:

```
backup --config /path/to/other.yaml
  -> BackupSettings is resolved from /path/to/other.yaml   (buvis_options)
  -> the backup PLAN is loaded from the default locations  (load_config)
```

so the flag appears to work (settings honour it) while the tool runs a completely
different backup/updater plan. This was surfaced by Copilot review on PR #179
(finding on `src/tools/backup/cli.py`), and deferred there because fixing it
correctly is a change to the **shared** `buvis_options` / Click-context contract
that every tool depends on — not something to smuggle into one gem's PR.

Verified against the code on 2026-09-27:
- `src/lib/buvis/pybase/configuration/click_integration.py` — the
  `buvis_options` wrapper receives `config` and `config_dir`, passes them to
  `ConfigResolver.resolve(...)`, stores only the resulting **settings** in
  `ctx.obj[settings_class]` / `ctx.obj["settings"]`, then `ctx.invoke(f, ...)`
  **without** the raw `config` / `config_dir` values.
- `find_config_files_ranked(tool_name, *, config_dir=None)` already accepts a
  `config_dir` override but has **no** single-explicit-file parameter.
- `backup/config.py::load_config(config_dir=None)` and the analogous sysup path
  call `find_config_files_ranked` with `config_dir` never threaded from the CLI.

## Solution

Make the resolved config selection reachable by each tool's own config loader,
and teach the loaders to honour it — an explicit **directory** and an explicit
**file**.

1. **Publish the selection into the Click context.** In the `buvis_options`
   wrapper, after resolving settings, store the raw selection on `ctx.obj` under
   stable keys (e.g. `ctx.obj["config_dir"]` and `ctx.obj["config_path"]`,
   `None` when unset). This is additive — existing `ctx.obj[settings_class]` /
   `ctx.obj["settings"]` are untouched — so no current reader breaks.

2. **Accept an explicit config file in the loader.** Add a
   `config_path: Path | None` parameter to
   `ConfigurationLoader.find_config_files_ranked` (and/or a small helper) so an
   explicit `--config FILE` is appended as the **highest-priority** layer on top
   of the ranked directory search, matching the documented precedence
   (CLI > env > YAML > defaults). `config_dir` already exists.

3. **Thread it through each tool's `load_config`.** `backup/config.py::load_config`
   (and the sysup equivalent) gain `config_path` alongside the existing
   `config_dir`, and each tool's `cli.py` reads `ctx.obj["config_dir"]` /
   `ctx.obj["config_path"]` and passes them in. After this, `backup --config X`
   loads the plan from X, not the default locations.

> **Blast radius:** step 1 touches `click_integration.py`, which backs
> `buvis_options` for **every** gem. It is purely additive (new `ctx.obj` keys),
> but it is shared code — hence its own PRD with its own tests rather than an
> inline change in one tool's PR. Steps 2–3 are per-tool and can land tool by
> tool once step 1 is in.

## Requirements

### Must have

- `buvis_options` stores the resolved `--config` / `--config-dir` selection on
  `ctx.obj` under stable, documented keys (`None` when unset); existing keys are
  unchanged.
- `ConfigurationLoader` can incorporate an explicit config **file** as the
  highest-priority layer, in addition to the existing `config_dir` override,
  preserving the documented precedence (an explicit file wins over discovered
  files; a discovered `*.local.yaml` still outranks its shared twin among
  discovered files).
- `backup/config.py::load_config` honours both an explicit file and directory,
  and `backup/cli.py` threads the context selection into it, so
  `backup --config FILE` runs the plan from FILE and `backup --config-dir DIR`
  runs the plan discovered under DIR.
- The library stays interface-agnostic: no Click import at module import time in
  the loader, no output outside the console adapter (HOLDS invariant).

### Nice to have

- Apply the same threading to **sysup** (the other config-driven runner with the
  identical latent split), so the fix is consistent across the toolkit.
- A one-line note in `docs/source/configuration.rst` that `--config` selects both
  the settings source and the tool's config plan.

### Out of scope

- Any change to `ConfigResolver`'s settings-resolution behaviour (it already
  honours `--config` / `--config-dir` for settings — only the *tool plan* path is
  broken).
- Reworking the precedence order itself (CLI > env > YAML > defaults stays as
  documented).
- Tools that do not load their own YAML plan (they have no split to fix).

## Success Criteria

- `backup --config /path/to/file.yaml` loads its backup **plan** from that file,
  not from the default locations; `--config-dir` likewise.
- The settings object and the tool plan are resolved from the **same** config
  selection — the silent split is closed.
- The change to `buvis_options` is additive; every existing tool and test still
  works unchanged.
- The library remains interface-agnostic (no import-time Click dependency in the
  loader; no output outside the console adapter).
