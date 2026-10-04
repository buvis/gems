# 00079 sysup — task breakdown

Spec: `dev/local/prds/backlog/00079-sysup-configurable-updaters-v1.md`
Design: `dev/local/designs/00079-sysup-configurable-updaters-v1-design.md`
Depends on: **00081 (config precedence fix) — DONE**, which shipped
`ConfigurationLoader.find_config_files_ranked()`. `sysup.config.load_config`
reuses it directly (no re-derived sort).

Ordering below is dependency-first. Each task names its acceptance check. Marker:
tests under `tests/tools/sysup/` auto-tag `sysup`; the loader test is `lib`.

## Phase 0 — shared loader + config schema

- [x] **0.1 Add `*.local.yaml` twins to `_get_candidate_files`** (shared library).
  DONE 2026-09-26 — twins interleaved in `_get_candidate_files` and
  `find_config_files_ranked`; additive-only. Tests added; full `lib` suite green
  (1443 passed).
- [x] **0.2 `sysup/config.py` — Pydantic models.** `WhenSpec`, `SysupCommand`
  (envelope incl. `enabled`, `order`, `when`, `interactive`, `timeout`,
  `continue_on_error`, `tags`, exactly-one-of `steps`/`use`, `with_` aliased to
  YAML `with` with `populate_by_name=True`), `SysupConfig`.
  *Acceptance:* `test_config.py` — valid config validates; unknown key /
  both-or-neither `steps`+`use` / unknown `use:` / unknown `with:` input raise;
  a `use:`+`with:` entry with YAML key `with` validates (alias works under
  `extra="forbid"`).
- [x] **0.3 `load_config` + `applicable_commands`.** Merge bundled default (lowest)
  + `find_config_files_ranked("sysup")` (low-to-high, from 00081) via
  `merge_configs`; validate; filter by `enabled` + `when.os` (sys.platform) +
  `when.check` (`shutil.which`) and sort `(order, name)`.
  *Acceptance:* `test_config.py` priority-ordering regression (tool-specific and
  `$BUVIS_CONFIG_DIR` win — fails if `reversed()` returns); `test_applicable.py`
  (darwin-only skipped on linux; missing `check` skipped; order correct).

## Phase 1 — capabilities (behavior-preserving relocation)

- [x] **1.0 Move `StepResult` OUT of `commands/` first.** Everything imports
  `from sysup.commands.step_result import StepResult` (mac/pip/wsl/nvim/cli + both
  test files). Since Phase 3 deletes `commands/`, relocate it to
  `sysup/step_result.py` up front and update every importer, so capabilities and
  the runner depend on the surviving path from the start (avoids a mid-refactor
  broken import).
  *Acceptance:* suite green after the move; no import references
  `sysup.commands.step_result` remain (grep clean).
- [x] **1.1 `capabilities/__init__.py`** — closed `CAPABILITIES` registry +
  `Capability` protocol declaring accepted `with:` inputs (so 0.2/0.3 validate).
- [x] **1.2 Relocate `helm-repo-update`** from `CommandMac._run_helm` verbatim.
- [x] **1.3 Relocate `nvim-mason`** from `CommandNvim` (probe trio + Lua/ANSI
  constants + `timeout` input, default 600).
- [x] **1.4 Relocate `pip-outdated`** from `CommandPip`. NOTE: today `CommandMac`
  calls `CommandPip` mid-sequence (`mac.py:45`, lazy import); under the new model
  that in-code delegation DISSOLVES — `pip-outdated` becomes an independent
  `use:` entry ordered between uv and helm in `default.yaml`. Behavior-equivalent,
  but `test_default_config.py` (3.1) must confirm pip still runs in that sequence
  position on darwin.
- [x] **1.5 Relocate `sudo-prime`** from `CommandMac._prime_sudo` (stop-callback).
  *Acceptance (1.2–1.5):* move existing `test_mac/nvim/pip/wsl` assertions to the
  capabilities, re-pointed at the callables; behavior assertions unchanged
  (helm empty-repo skip, mason FAIL/DONE/INCONCLUSIVE + timeout/log-tail/ANSI,
  per-interpreter pip). This is the "preserve existing behavior" gate.

## Phase 2 — runner + CLI

- [x] **2.1 `runner.py`.** Runs `prime` first; executes `run` (argv early-abort)
  and `use` (registry) entries with `interactive`/`timeout`/`continue_on_error`;
  per-step `shutil.which`; wraps whole run in `try/finally` for sudo release
  (survives `BaseException`); wraps each `use` call so an unexpected raise →
  failed `StepResult`, `FatalError` → propagate. Yields `StepResult`.
  *Acceptance:* `test_runner.py` — brew early-abort; `continue_on_error:true`
  continues; interactive inherits stdio (exit-code-only message); prime before
  commands; refresher `stop` called in `finally` on `KeyboardInterrupt`;
  per-step `which`; capability raise → failed StepResult (no traceback).
- [x] **2.2 `cli.py` — single command.** `@click.command` + `buvis_options`;
  `--only`/`--tag`/`--list`/`--dry-run`; keep `_report_step(s)`; drop the four
  subcommands and `sys.platform` guards; `FatalError` → `console.panic`.
  *Acceptance:* **`test_sysup_cli.py`** (existing file — NOT `test_cli.py`) is
  rewritten: its current `isinstance(cli, click.Group)` and `"mac" in cli.commands`
  assertions INVERT under the cutover (now a `@click.command` with no subcommands),
  and its `@patch("sysup.commands.pip.pip.CommandPip")` targets a path that no
  longer exists after Phase 1/3 — retarget to the runner/capabilities. New
  assertions: runs all applicable; `--only`/`--tag` narrow; `--only <mac-key>` on
  linux reports skip; `--list` prints plan, runs nothing; `--dry-run` spawns
  nothing AND does not prime sudo / start the refresher; config `FatalError` →
  panic not traceback.

## Phase 3 — defaults + migration

- [x] **3.1 `default.yaml`.** Reproduce mac (brew→npm-check→pip→uv→helm→mise, mise
  highest `order`, with the "mise deletes tool dirs" comment) + wsl (apt→snap),
  host-selected via `when`.
  *Acceptance:* `test_default_config.py` — darwin plan == today's `sysup mac`
  set/order; linux plan == today's `sysup wsl`.
- [x] **3.2 Delete `commands/{mac,pip,nvim,wsl}/` and rewrite
  `commands/__init__.py`.** Its `__all__` currently re-exports
  `CommandMac/CommandNvim/CommandPip/CommandWsl/StepResult`; after deletion those
  classes are gone (logic lives in capabilities + `default.yaml`). Either empty
  the package or remove `commands/` entirely (`StepResult` already moved out in
  1.0). Grep for any remaining `from sysup.commands.{mac,pip,nvim,wsl}` importer.
- [x] **3.2b Update `manifest.toml`.** Remove the `[tool.commands]` block listing
  `mac/nvim/pip/wsl` (those subcommands no longer exist). Decide whether the new
  single-command surface needs any manifest representation (today `[tool.commands]`
  documents subcommands; with none, the block is dropped, not left stale).
- [x] **3.3 Docs + migration note.** `buvis-sysup.yaml` schema, capability
  catalogue, dotfiles-share + `.local.yaml` machine-override example, subcommands-
  removed note. CHANGELOG entry (user-visible CLI change).

## Cross-cutting acceptance

- Full suite green (`uv run pytest`); `uv run mypy src/lib src/tools`.
- No `console.panic`/`sys.exit` in `config.py`/`runner.py`/capabilities.
- Zero-config `sysup` on mac == old `sysup mac`; on linux == old `sysup wsl`.

## Suggested implementation batching

- Phase 0 is one PR (loader twin + schema + load/applicable) — self-contained,
  no behavior change to existing tools.
- Phase 1 is one PR (capabilities + relocated tests) — pure move, green before
  and after.
- Phases 2–3 land together (runner + CLI + default + deletion) — this is the
  cutover; the four subcommands disappear here, so ship the migration note in the
  same PR.
