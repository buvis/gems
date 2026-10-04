# sysup: configurable, dotfiles-shareable system updaters

<!-- design; migrated from PRD 00079 flat file -->

## Implementation

### Module: sysup.config
- **Location**: `src/tools/sysup/config.py` (new)
- **Responsibility**: load + validate the keyed map from the merged config,
  resolve applicability (`when`), order entries.
- **Exports**: the Pydantic models (`SysupCommand`, `RunSpec`, `UseSpec`,
  `WhenSpec`), a loader that returns ordered applicable entries.

### Module: sysup.capabilities
- **Location**: `src/tools/sysup/capabilities/` (new)
- **Responsibility**: the closed registry of built-in capabilities; each owns its
  guard/probe/priming logic (relocated from today's command classes) and yields
  `StepResult`s.
- **Exports**: `CAPABILITIES` registry, capability callables.

### Module: sysup.runner
- **Location**: `src/tools/sysup/runner.py` (new)
- **Responsibility**: execute ordered entries — argv sequences for `run`, the
  registered callable for `use` — with `when`/`interactive`/`timeout`/
  `continue_on_error` semantics and `shutil.which` resolution. Runs `prime:`
  first. Returns `CommandResult` + `StepResult`s.

### Module: sysup.cli
- **Location**: `src/tools/sysup/cli.py`
- **Responsibility**: single `sysup` entry point (no subcommands); `--only` /
  `--tag` options; render `StepResult`s via `console`. Keeps `buvis_options`.

### Default config
- **Location**: packaged with the tool (e.g. `src/tools/sysup/default.yaml` or an
  embedded dict), loaded as the base layer.

### Dependencies
- Uses the existing pybase config loader + `console` + `StepResult`. No new
  third-party deps.

## Provenance

Requirements elicited in a dashboard session on 2026-09-26. Four foundational
decisions confirmed by the user:
1. Composition model → **keyed map, deep-merged**.
2. Entry shape → **argv list with a `steps:` array per entry** (no shell).
3. Invocation → **`sysup` runs all applicable; `--tag`/`--only` filter**;
   `when` replaces the `sys.platform` subcommands.
4. Defaults → **ship a bundled default reproducing today's behaviour**.
Plus the smart-step model: **the conditional/stateful updaters ship as named
built-in capabilities (code) that config opts into by name with inputs**, rather
than living in config. Grounded against `src/tools/sysup/commands/**` and the
pybase config loader as they stood on that date.

## Follow-ups

- **Revisit the keyed-map composition model (decision #1) once 00080 lands.**
  Decision #1 chose a keyed map (deep-merged) for list-valued settings because
  the pybase config loader's `_deep_merge` replaced lists wholesale, giving no
  clean cross-layer append/remove. PRD **00080** (pybase config directive merge)
  adds `key+` (append, dedup) / `key-` (remove) list directives to `_deep_merge`,
  which removes that constraint. Once 00080 is merged, sysup's keyed-map
  workaround can be reconsidered in favour of plain lists composed with the new
  directives. Not a v1 blocker — sysup ships on the keyed map; this is a
  post-00080 simplification.

---

<!-- folded from architecture/decisions/00079-sysup-configurable-updaters-v1-design.md -->

# Design: sysup — configurable, dotfiles-shareable system updaters

Implements PRD `dev/local/prds/backlog/00079-sysup-configurable-updaters-v1.md`.

## Assumptions (stated per the task's step 3)

- **Design filename** follows the observed convention
  `NNNNN-<slug>-vN-design.md` in `dev/local/designs/` (matching
  `00053-dot-git-ops-unification-v1-design.md`), so this is
  `00079-sysup-configurable-updaters-v1-design.md`.
- **Config filename** is `buvis-sysup.yaml`, the tool-specific slot the loader
  already searches (`_get_candidate_files` appends `buvis-{tool_name}.yaml`),
  loaded with `tool_name="sysup"`. Confirmed against `loader.py`.
- **Machine-local overrides are a SHARED-LIBRARY feature, not a sysup one.**
  sysup is not special: any gem whose config is shared via dotfiles may need a
  per-machine layer. So the `.local.yaml` override candidate is added once to the
  shared loader (`_get_candidate_files`) and every gem gets it for free. This
  design depends on that loader change but does not own it — see the dedicated
  section below and the blast-radius note in Module placement.
- **Bundled default lives in-tree** as `src/tools/sysup/default.yaml`, loaded via
  `importlib.resources` and injected as the lowest-priority layer. Chosen over an
  embedded Python dict so the default is authored in the same YAML schema users
  write and can be diffed/copied — no second serialization format to maintain.
- **"Preserve existing behavior"** governs the capability internals: the helm
  guard, mason probe, sudo priming, and per-interpreter pip are relocated
  **verbatim** (byte-for-byte logic), not reworked. The only behavior change in
  scope is the CLI surface (subcommands → one command + filters), which the PRD
  explicitly asks for.
- **Pydantic** is the schema validator (matches `SysupSettings(GlobalSettings)`,
  already Pydantic; PRD names it). No new dependency.

## Architecture fit

sysup today is a Click **group** (`cli.py`) with four subcommands, each a hand-
written command class:

- `commands/mac/mac.py::CommandMac` — brew argv sequence, `npm-check` (interactive),
  delegates to `CommandPip`, `uv`, helm (guarded), mise (last); primes sudo with a
  background refresher released in `finally`; `sys.platform != "darwin"` guard in
  the CLI.
- `commands/pip/pip.py::CommandPip` — per-interpreter outdated-package upgrade.
- `commands/nvim/nvim.py::CommandNvim` — lazy sync, mason (Lua probe, 600 s
  timeout, `mason.log` tail, ANSI-strip + sentinel parse), treesitter; re-resolves
  `nvim` before each step.
- `commands/wsl/wsl.py::CommandWsl` — apt update/upgrade/autoremove, snap refresh;
  `sys.platform != "linux"` guard in the CLI.

Every step already shells out via argv (`subprocess.run([bin, ...])`) and reports
through `StepResult`. Nothing is configurable; the applicability logic is the two
`sys.platform` guards in `cli.py`.

This design replaces the hardcoded groups with a **data-driven runner over a
keyed-map config**, reusing the repo's existing config stack rather than adding a
merge layer. The shape mirrors the accepted seam in
`dev/local/specs/all-interface-architecture.md` (thin CLI over a core that returns
`CommandResult`) and the pattern in `00053`'s `DotGitService`: presentation stays
in `cli.py`, policy/logic moves behind an importable unit (`runner` + a closed
`capabilities` registry) that never imports Click.

The pivot is the split between **data** and **code**:

- Simple updaters (brew, uv, mise, lazy, treesitter, apt, snap) are pure config:
  a `run` entry holding argv `steps:`.
- Irreducibly-stateful updaters (helm empty-repo guard, mason probe, sudo
  priming, per-interpreter pip discovery) are **built-in capabilities** — code
  sysup owns and tests, referenced from config by name (`use:` + optional
  `with:`). This honors the repo's "if code can answer, code answers" rule: the
  guards stay deterministic Python, never a shell string.

## Config structure & merge semantics

### Why a keyed map, not a list

The loader's `_deep_merge` (`loader.py:52`) recurses into nested **dicts** but for
any non-dict value does `target[k] = v` — **wholesale replace**. A list is a
non-dict value, so `_deep_merge` replaces a list layer entirely; it never
appends. Therefore a shared base of updaters plus a machine layer that *adds or
tweaks* one entry only composes correctly if the updater collection is a **dict
keyed by name** (`commands: {brew: {...}, apt: {...}}`), where the machine layer's
`commands.<newkey>` adds and `commands.<existingkey>.<field>` overrides — both
via the existing dict recursion, **zero new merge code**. This is the single
load-bearing reason the PRD chose the keyed map, and the design must not
reintroduce a top-level list anywhere in the merged path.

### Layering order

`merge_configs(*configs)` (`loader.py`) `_deep_merge`s left-to-right, "in order of
increasing priority" (later wins). `find_config_files(tool_name="sysup")` returns
paths **highest-to-lowest** priority across `$BUVIS_CONFIG_DIR` →
`~/.config/buvis` → cwd, each location contributing (with the loader change
below) `config.yaml` → `config.local.yaml` → `buvis.yaml` → `buvis.local.yaml` →
`buvis-sysup.yaml` → `buvis-sysup.local.yaml`. So the loader in `sysup.config`
must:

1. Build the layer list as: **bundled `default.yaml` first (lowest)**, then the
   user files sorted into **explicit increasing-priority order** (see the caution
   below — do NOT use `reversed(find_config_files(...))`).
2. `merge_configs(default_dict, *user_dicts_low_to_high)`.

> **CAUTION — `find_config_files` is NOT monotonically ranked; a blind
> `reversed()` inverts precedence (fixed after design review, Finding 1).**
> `find_config_files` builds candidates as `for base in dirs: [config, buvis,
> buvis-<tool>]` where `dirs` is **highest-priority-first**
> (`$BUVIS_CONFIG_DIR` → `~/.config/buvis` → cwd) but the stems within each dir
> are appended **lowest-first** (`config` < `buvis` < `buvis-<tool>`). The flat
> result is therefore *mixed order* — dirs descending, stems ascending — not a
> single ranking, despite the method's docstring claiming "highest to lowest
> priority" (that docstring is inaccurate; **do not trust it — read the loop**,
> Finding 2). `reversed()` of that mixed list would make `~/.config/buvis` beat
> `$BUVIS_CONFIG_DIR` and `config.yaml` beat `buvis-sysup.yaml` — the exact
> inversion of intended precedence.
>
> `load_config` must instead assign each returned path an explicit
> `(dir_rank, stem_rank)` key and sort **ascending** (lowest priority first)
> before merging, where `dir_rank` follows `get_config_dirs()` order (cwd lowest)
> and `stem_rank` is `config < config.local < buvis < buvis.local <
> buvis-<tool> < buvis-<tool>.local`. Feed `merge_configs(default, *sorted)` so
> later (higher-priority) layers win. This priority computation is part of
> `sysup.config.load_config` and is covered by its own test (Test strategy). It
> does not require changing `find_config_files` itself — only not misreading its
> output as pre-ranked.

The bundled default is thus just the base dict; every user/dotfiles/machine layer
deep-merges on top by key. A machine that wants to *drop* a default entry sets
`commands.<key>.enabled: false` (envelope field) rather than trying to delete a
key — deep-merge cannot express deletion, so disablement is a value, not an
absence. **This `enabled` field is added to the PRD's envelope by this design;
adopted 2026-09-26 (see Decisions log).**

### Machine-local overrides — a shared-library mechanism for ALL gems

**Problem the PRD's config alone doesn't solve.** The whole config stack under
`~/.config/buvis/` is itself managed by `dot` and shared across machines. `dot`
tracks files **individually via a bare-repo work-tree**
(`git --git-dir=$DOTFILES_ROOT/.buvis/ --work-tree=$DOTFILES_ROOT`, confirmed in
`src/tools/dot/git/service.py:32`) — a file is shared **only once you
`dot add` it.** So `buvis-sysup.yaml` in that directory is the shared layer, and
there is no obvious home for config that must exist on **one** machine only. That
is the gap raised in elicitation.

**Decision (Option B, generalized).** Teach the shared loader
(`_get_candidate_files`) to also look for a sibling **`*.local.yaml`** next to
each config candidate it already emits, at **higher priority** than its shared
twin. The local file lives in the *same* `~/.config/buvis/` directory but is
**simply never `dot add`ed**, so it stays machine-local while the shared file
syncs. This is not a sysup feature — it applies to `config.yaml`,
`buvis.yaml`, and every `buvis-<tool>.yaml`, so **every gem** gains per-machine
overrides for free the moment the loader lands it. sysup is merely the first
consumer.

Candidate order per location becomes (lowest → highest priority within a dir):

```
config.yaml            config.local.yaml
buvis.yaml             buvis.local.yaml
buvis-<tool>.yaml      buvis-<tool>.local.yaml   # e.g. buvis-sysup.local.yaml
```

Each `.local.yaml` sits immediately after its shared twin, so a machine-local
value wins over the shared value for the same key, and the keyed-map deep-merge
adds machine-only keys. Nothing about sysup's own loader changes except that it
now receives more layers from `find_config_files` — it already merges whatever it
is handed. The `.local.yaml` files should be added to `dot`'s ignore set (or
simply documented as "never add these") so they are not accidentally tracked.

**Loader change (owned by this design's Phase 0, but library-scoped):**

```python
# src/lib/buvis/pybase/configuration/loader.py :: _get_candidate_files
for base in paths:
    for stem in ("config", "buvis", *( [f"buvis-{tool_name}"] if tool_name else [] )):
        candidates.append(base / f"{stem}.yaml")
        candidates.append(base / f"{stem}.local.yaml")   # NEW: machine-local twin, higher priority
```

This preserves the existing shared-file order and only *inserts* the `.local`
twins; no shared-file precedence changes, so it is backward compatible for every
gem already using the loader. Covered by the loader's own tests (Test strategy).

**Consequence the user flagged — local config is not in git.** Because
`.local.yaml` is deliberately untracked, it is **not** protected by the dotfiles
repo the way shared config is. Anything a machine keeps only in `.local.yaml`
(and, more broadly, any gem's machine-local state) needs a separate backup story.
That is out of scope here but is tracked as a new gem idea in
`dev/local/discovery/00080-bkp-gem.md`, whose founding use case is exactly "back
up the machine-local buvis config the dotfiles repo doesn't cover."

### Env substitution & literals

`load_yaml` already does `${VAR}` / `${VAR:-default}` substitution and `$${VAR}`
escaping to a literal `${VAR}`. A `steps:` arg that must reach the tool literally
(rare) uses `$${VAR}`. No shell means this is the *only* expansion surface —
preserved from today, not widened.

### Schema (Pydantic models in `sysup.config`)

```yaml
# buvis-sysup.yaml (or bundled src/tools/sysup/default.yaml — same schema)
commands:
  brew:
    order: 10
    enabled: true                       # default true; false disables a merged entry
    when: { os: darwin, check: brew }
    steps:                              # RunSpec: list of argv arrays, early-abort
      - [brew, update]
      - [brew, upgrade]
      - [brew, cleanup]

  npm-check:
    order: 20
    when: { check: npm-check }
    interactive: true                   # inherit stdio (StepResult message = exit code only)
    steps: [[npm-check, -gu]]

  python-packages:
    order: 30
    use: pip-outdated                   # UseSpec: named capability, no inputs

  helm:
    order: 40
    when: { check: helm }
    use: helm-repo-update

  nvim:
    order: 50
    when: { check: nvim }
    use: nvim-mason
    with: { timeout: 600 }              # capability inputs

  apt:
    order: 10
    when: { os: linux, check: apt }
    steps:
      - [sudo, apt, update]
      - [sudo, apt, upgrade, -y]
      - [sudo, apt, autoremove, -y]

prime:                                  # session capabilities run before commands
  - sudo
```

```python
# src/tools/sysup/config.py  — interfaces & contracts
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["WhenSpec", "SysupCommand", "SysupConfig", "load_config", "applicable_commands"]


class WhenSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    os: Literal["darwin", "linux", "win32"] | None = None   # matched against sys.platform
    check: str | None = None                                # binary; shutil.which at run time


class SysupCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)  # mirror SysupSettings; alias `with`
    order: int = 100
    enabled: bool = True
    when: WhenSpec = WhenSpec()
    interactive: bool = False
    timeout: int | None = None
    continue_on_error: bool = False
    tags: tuple[str, ...] = ()
    steps: tuple[tuple[str, ...], ...] | None = None        # RunSpec
    use: str | None = None                                  # UseSpec: capability name
    with_: dict[str, object] = Field(default_factory=dict, alias="with")  # YAML `with`
    # model_config MUST set populate_by_name=True (or accept alias-only) so the
    # YAML key `with` populates `with_` without tripping extra="forbid"
    # (fixed after review, Finding 8).

    @model_validator(mode="after")
    def _exactly_one_kind(self) -> "SysupCommand":
        if bool(self.steps) == bool(self.use):
            raise ValueError("entry must have exactly one of `steps` or `use`")
        return self


class SysupConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    commands: dict[str, SysupCommand] = {}
    prime: tuple[str, ...] = ()


def load_config(config_dir: str | None = None) -> SysupConfig: ...
    # merge bundled default (lowest) + user files sorted by explicit
    # (dir_rank, stem_rank) ASCENDING (NOT reversed(find_config_files) — that list
    # is mixed-order, see Layering order caution) via merge_configs, then
    # SysupConfig.model_validate(merged). Capability-name / with-input validation
    # happens here against the registry (unknown name / unknown input -> ValueError).

def applicable_commands(cfg: SysupConfig) -> list[tuple[str, SysupCommand]]: ...
    # filter enabled + when.os matches sys.platform + when.check resolves via shutil.which;
    # sort by (order, name). `check` misses are reported by the runner, not dropped silently.
```

Validation failures (`extra="forbid"` on an unknown key, both/neither
`steps`/`use`, an unknown `use:` name, an unknown `with:` input) surface as a
`FatalError` the CLI catches → `console.panic` with a clear message. Never a
stack trace (repo invariant).

## CLI surface

`cli.py` collapses from a `@click.group` with four subcommands to a **single
`@click.command`**, keeping `@buvis_options(settings_class=SysupSettings)`:

```
sysup                     # run every applicable entry (order asc)
sysup --only brew,apt     # run only these keys (comma list or repeated)
sysup --tag python        # run only entries carrying this tag
sysup --list              # print the resolved plan for this host
sysup --dry-run           # show what would run, run nothing
```

The two `sys.platform` guards move out of the CLI entirely — a `mac`-only entry
carries `when.os: darwin`, so on Linux it is filtered by `applicable_commands`
and reported as skipped, exactly reproducing today's "mac command is only
available on macOS" outcome without a subcommand. `--only` on a key whose `when`
doesn't match this host reports the skip (an explicit request gets an explicit
reason), rather than silently running it.

Data flow:

```
sysup (cli.py handler)
  -> load_config()                     # merged + validated SysupConfig, or FatalError
  -> applicable_commands(cfg)          # filtered + ordered [(name, cmd), ...]
  -> apply --only / --tag filters
  -> Runner(cfg).run(selected)         # runs prime[] first, then entries
       -> yields StepResult per step
  -> _report_step(step) via console    # unchanged reporting helpers
```

`_report_step` / `_report_steps` are kept verbatim from today's `cli.py`.

## Module placement

**New:**
- `src/tools/sysup/config.py` — Pydantic models + `load_config` + `applicable_commands` (above).
- `src/tools/sysup/runner.py` — `Runner`: executes `run` (argv sequence, early-abort) and `use` (registry callable) entries with `interactive`/`timeout`/`continue_on_error`; runs `prime` capabilities first; re-resolves binaries via `shutil.which` at run time. Yields `StepResult`. **Each `use` capability call is wrapped: an unexpected exception is caught and converted to `StepResult(success=False, message=...)` (a `FatalError` from a capability — e.g. a missing required binary — is re-raised for the CLI to `console.panic`), so a capability raising mid-stream never leaks a traceback (repo "never a stack trace" invariant; Finding 6).**
- `src/tools/sysup/capabilities/__init__.py` — the closed `CAPABILITIES: dict[str, Capability]` registry + a `Capability` protocol (declares accepted `with:` inputs so `load_config` can validate them).
- `src/tools/sysup/capabilities/helm.py` — `helm-repo-update` (relocated `CommandMac._run_helm`).
- `src/tools/sysup/capabilities/nvim_mason.py` — `nvim-mason` (relocated `CommandNvim._update_mason` + `_parse_mason_result` + `_read_mason_log_tail` + the module-level Lua/ANSI constants). Input: `timeout` (default 600, today's `MASON_TIMEOUT`).
- `src/tools/sysup/capabilities/pip.py` — `pip-outdated` (relocated `CommandPip`).
- `src/tools/sysup/capabilities/sudo.py` — `sudo-prime` (relocated `CommandMac._prime_sudo`). Today's `CommandMac.execute` already releases the refresher in `try/finally` (`mac.py:19–24`), which runs on `BaseException` — so this is not a bug to fix but a property to PRESERVE: because priming moves to session level, the runner must wrap the **whole run** (all entries) in `try/finally` so a Ctrl-C between entries still releases the thread (repo claim/lifecycle invariant; Finding 3).
- `src/tools/sysup/default.yaml` — bundled base config reproducing today's behavior.

**Edited (SHARED LIBRARY — cross-cutting, lands in Phase 0):**
- `src/lib/buvis/pybase/configuration/loader.py` — `_get_candidate_files` also
  emits a `*.local.yaml` twin (higher priority) beside each shared candidate, so
  every gem gains machine-local overrides (see "Machine-local overrides"). Blast
  radius: **every gem that uses the config loader**, but additive-only — no
  shared-file precedence changes, so no existing gem's behavior changes unless it
  gains a `.local.yaml` file. This is why it is called out as its own task, not
  folded silently into sysup's config module. **Coordinate with PRD 00081**
  (pybase config precedence fix): 00081 adds a ranked-order helper to
  `ConfigurationLoader` that returns discovered files low-to-high; `load_config`
  here should reuse it rather than re-deriving the `(dir_rank, stem_rank)` sort.
  If 00081 lands first, this design's explicit-sort note becomes "call the helper."

**Edited:**
- `src/tools/sysup/cli.py` — group→command; add `--only`/`--tag` (+ `--list`/`--dry-run` if in scope); keep reporting helpers and `buvis_options`.
- `src/tools/sysup/__init__.py` / `__main__.py` — entry point still `cli`, now a command not a group (no `__init__` export churn expected; verify).

**Deleted (superseded by config + capabilities):**
- `src/tools/sysup/commands/mac/`, `pip/`, `nvim/`, `wsl/` — their argv sequences become `default.yaml` entries; their smart bits become capabilities. `commands/step_result.py::StepResult` **stays** (moved up to `sysup/step_result.py` or kept in place and imported by the runner) — it is the shared result type, still used everywhere.

## Reuse inventory

- `buvis.pybase.configuration.loader` — `merge_configs`, `_deep_merge`, `find_config_files`, `get_config_dirs`, `load_yaml` (with `${VAR}`/`$${VAR}`): the entire merge + substitution + safe-path/world-writable stack, reused as-is. No new merge logic.
- `StepResult` (`commands/step_result.py`) — reused unchanged as the runner's yield type.
- `CommandResult` / `FatalError` (`pybase/result.py`) — `FatalError` for missing config/deps caught by the CLI; `CommandResult` is the runner's aggregate return if a single object is preferred over a `StepResult` stream (design keeps the streaming `Iterator[StepResult]` that `CommandNvim.execute` already uses, so progress reports arrive live).
- `console` (`pybase.adapters`) — `success`/`failure`/`info`/`panic`, via the existing `_report_step`.
- `buvis_options` + `SysupSettings` (`GlobalSettings`, `extra="forbid"`) — kept on the single command; `Pydantic` reused for the config models with the same `extra="forbid"` posture.
- Verbatim logic bodies relocated (not rewritten): `_run_helm`, `_prime_sudo`, the mason probe trio + Lua/ANSI constants, `CommandPip`. Their existing tests move with them (Test strategy).
- `shutil.which` re-resolution pattern (`CommandNvim._resolve_nvim`, `CommandMac._run_optional`) — generalized into the runner's per-step resolution.

## Alternatives considered

1. **List of commands with an explicit `extra:`/append list for the machine layer.**
   Rejected (and rejected by the user in elicitation): needs custom append-merge
   code because `_deep_merge` replaces lists wholesale, contradicting the repo's
   "no abstractions you don't need" rule. The keyed map gets add + per-field
   override for free from the existing dict recursion.
2. **Shell string per entry** instead of argv `steps:`. Rejected: injection
   surface + doubles expansion (shell *and* loader `${VAR}`), and still can't
   express the helm/mason logic without a capability — so it buys risk without
   removing the special cases. Argv matches how every current step already runs.
3. **User-supplied Python capabilities (plugin loading).** Deferred to a later
   version (PRD out-of-scope). v1's registry is closed; unknown `use:` is a config
   error, which keeps the trust surface small and the validation total.
4. **Keep the four subcommands as thin aliases** (`sysup mac` → `--tag mac`).
   Rejected: the PRD asks to remove them and let `when` decide applicability;
   aliases would keep the host-awareness split between config and CLI. A one-line
   migration note in docs covers muscle memory instead.
5. **Embed the default config as a Python dict** rather than `default.yaml`.
   Rejected: a dict is a second authoring format for the same schema; a bundled
   YAML is copy-pasteable as a user's starting config and diffs against it.

## Risks & edge cases

- **List-replace merge is a footgun if any collection sneaks in as a list.** The
  whole "add one machine entry" story breaks silently if `commands` is ever a
  list at any layer, because `_deep_merge` would replace the base wholesale. The
  Pydantic model types `commands` as a `dict`, so a list at any layer fails
  validation loudly — this is the guardrail. Test: a machine layer adding one key
  preserves all base keys (Test strategy).
- **Deep-merge cannot delete.** Disabling a bundled default entry must be a value
  (`enabled: false`), not key removal — `applicable_commands` filters it out.
  Adopted (Decisions log): without it a machine could only override fields, never
  turn an entry off ("share the base but skip helm on this box").
- **`sudo-prime` lifecycle release.** Today's `_prime_sudo` returns a `stop`
  callback the caller invokes in `finally`. The runner must call it in `finally`
  *and* survive `KeyboardInterrupt`/`BaseException` (Ctrl-C mid-run must not leak
  the refresher thread) — the repo's claim/lifecycle invariant. The current
  `CommandMac.execute` uses `try/finally` (good); the runner must preserve that
  around the *whole* run, since priming is now session-level, not per-entry.
- **`mise` must run last.** Today enforced by call order inside `CommandMac`. Now
  enforced by `order:` in `default.yaml` (mise gets the highest order among mac
  entries). The comment explaining *why* (deletes tool dirs the inherited PATH
  points at) moves into `default.yaml` as a YAML comment so it isn't lost. A user
  reordering it is their choice; the default preserves it.
- **Binary re-resolution timing.** `when.check` is evaluated at
  `applicable_commands` time (start of run) but the runner must re-`which` each
  binary immediately before spawning it — a concurrent `mise upgrade` earlier in
  the same run can move a later binary (the exact reason `CommandNvim` re-resolves
  `nvim` before every step). The runner resolves per-step, not once.
- **Interactive entries produce no captured output.** `interactive: true` inherits
  stdio (today's `npm-check` path); its `StepResult.message` can only be the exit
  code, matching `_run_optional_interactive`. The runner must not try to capture
  an interactive step's output.
- **`continue_on_error` semantics vs today's default.** Today a failed step aborts
  its command group but the CLI still runs the next subcommand. The runner's
  default (`continue_on_error: false`) aborts the *entry* (its remaining `steps`)
  but proceeds to the next entry — matching per-command isolation. Only
  `continue_on_error: true` continues within an entry after a failed step.
- **Empty / absent config.** No user file + bundled default = today's behavior.
  A user file that sets `commands: {}` explicitly does **NOT** wipe the default:
  `_deep_merge` recurses when both sides are dicts (`loader.py:56`), and `commands`
  is a dict on both layers, so an empty `{}` source contributes no keys and the
  base entries survive (corrected after review, Finding 4 — an earlier draft
  wrongly said it "would wipe the default"). To actually run nothing, a user sets
  `enabled: false` on the entries; this asymmetry (can disable, cannot delete by
  omission) is intended and must be documented.
- **`--dry-run` must suppress side-effecting prime and interactive steps
  (Finding 5).** `prime: [sudo]` runs a real `sudo -v` plus a background refresher
  thread *before* any entry (`mac.py:20`); an `interactive` entry inherits stdio.
  Under `--dry-run` the runner walks the resolved plan and reports what *would*
  run but must NOT prime sudo, must NOT spawn the refresher, and must NOT
  `subprocess.run` any step (interactive or not). Dry-run is plan-resolution +
  reporting only; the test asserts zero `subprocess.run` and no refresher thread.
- **`win32`** appears in `WhenSpec.os` for completeness (sys.platform), but no
  bundled Windows entries exist; a WSL user runs under `linux`. Not a regression —
  today has no Windows path either.

## Test strategy outline

- **`tests/lib/pybase/configuration/` (shared loader)**: extend the existing
  loader tests — `_get_candidate_files` now emits a `.local.yaml` twin after each
  shared candidate at higher priority; a `buvis-<tool>.local.yaml` present in the
  same dir overrides its shared twin and adds machine-only keys; **no shared-file
  ordering regresses** when no `.local.yaml` exists (backward-compat for every
  existing gem). This is a library test, run under the `lib` marker, not `sysup`.
- **`tests/tools/sysup/test_config.py` — priority-ordering regression (Finding 1
  guard)**: with files in BOTH `$BUVIS_CONFIG_DIR` and `~/.config/buvis`, assert
  the resolved value follows intended precedence — `$BUVIS_CONFIG_DIR` beats
  `~/.config/buvis`, and within a dir `buvis-sysup.local.yaml` > `buvis-sysup.yaml`
  > `buvis.yaml` > `config.yaml`. This test fails if anyone reintroduces a blind
  `reversed(find_config_files(...))`, which would invert precedence.
- **`tests/tools/sysup/test_config.py`** (new): valid config validates; unknown
  top-level/entry key raises (`extra="forbid"`); both-`steps`-and-`use` and
  neither raise; unknown `use:` name and unknown `with:` input raise; `${VAR}` and
  `$${VAR}` behave. **Merge test**: base default + a machine layer adding one key
  and overriding one field of another yields the union with all base keys intact
  (locks in the keyed-map decision — a regression here means someone reintroduced
  a list). Layering-order test: a higher-priority layer's field wins.
- **`tests/tools/sysup/test_applicable.py`** (new): a `when.os: darwin` entry is
  filtered out on `linux` and reported skipped (reproduces the old
  "only available on macOS" guard); a missing `when.check` binary is reported
  skipped; ordering is `(order, name)`.
- **`tests/tools/sysup/test_runner.py`** (new): `run` entry aborts on first failed
  step (brew early-abort); `continue_on_error: true` keeps going; `interactive`
  entry inherits stdio and reports exit code only; `prime` runs before commands;
  the sudo refresher's `stop` is called in `finally` even when a step raises
  `KeyboardInterrupt`; per-step `shutil.which` is called per step, not once. A
  `use` capability that raises an unexpected exception becomes a failed
  `StepResult` (no traceback escapes the runner); one that raises `FatalError`
  propagates to the CLI for `console.panic` (Finding 6).
- **Relocated capability tests** (move existing `tests/tools/sysup/test_mac.py` /
  `test_nvim.py` / `test_pip.py` / `test_wsl.py` content): the helm empty-repo
  guard (`repo list -o json` == `[]` → skip), the mason probe (FAIL/DONE/
  INCONCLUSIVE parsing, timeout → `mason.log` tail, ANSI strip), per-interpreter
  pip, sudo priming — each asserted against the same mocked-subprocess fixtures
  they use today, re-pointed at the capability callable. Behavior assertions
  unchanged (this is the "preserve existing behavior" gate).
- **`tests/tools/sysup/test_cli.py`** (new/rewritten): `sysup` runs all applicable
  (mock the runner, assert selection); `--only brew,apt` and `--tag python` narrow
  correctly; `--only <mac-key>` on linux reports the skip; a config `FatalError`
  becomes `console.panic`, not a traceback. `--list` prints the resolved plan
  (name, order, kind, applicability) and runs nothing; `--dry-run` walks the plan
  through the runner without spawning any subprocess (assert no `subprocess.run`).
- **`tests/tools/sysup/test_default_config.py`** (new): load the bundled
  `default.yaml`, `applicable_commands` on a simulated darwin host = the same set
  and order as today's `sysup mac` (brew→npm-check→pip→uv→helm→mise); on linux =
  today's `sysup wsl` (apt→snap). This is the migration-equivalence proof.
- **No `console.panic`/`sys.exit` inside `config.py`/`runner.py`/capabilities**
  (repo invariant) — a grep-style test or review check; the CLI layer is the only
  place that panics.

## Decisions log

- **`enabled: false` envelope field — ADOPTED** (2026-09-26, user). Deep-merge
  cannot delete a key, so disabling a shared/bundled default entry on one machine
  is expressed as a value (`enabled: false`) that `applicable_commands` filters
  out, not as key removal. The field is part of the `SysupCommand` envelope
  (already shown in the schema), defaulting to `true`. A machine-local
  `.local.yaml` can therefore turn a shared entry off for that host alone.
- **`--list` and `--dry-run` — BOTH IN SCOPE this pass** (2026-09-26, user).
  Built alongside the core rather than deferred. `--list` prints the resolved
  plan for this host (name, order, kind, applicability) via `applicable_commands`;
  `--dry-run` walks the same plan through the runner without spawning. Both are
  in the CLI surface and the Test strategy below (no longer "nice-to-have").

## Review log

**Blind-lens review pass, 2026-09-26** (fresh-context subagent, read-only,
verified against real source; author independently re-confirmed Finding 1 against
`loader.py` before applying). 9 findings, all resolved in this revision:

- **CRITICAL 1 — `reversed(find_config_files(...))` inverts precedence.** CONFIRMED
  (independently). `find_config_files` output is mixed-order (dirs descending,
  stems ascending), not monotonic. FIXED: Layering-order section now mandates an
  explicit `(dir_rank, stem_rank)` ascending sort in `load_config`, never
  `reversed()`; `load_config` comment corrected; priority-ordering regression test
  added.
- **HIGH 2 — loader docstring is inaccurate ("highest to lowest").** CONFIRMED.
  FIXED: caution added telling implementers to read the loop, not trust the
  docstring.
- **HIGH 3 — sudo "release on BaseException" mischaracterized current code.**
  CONFIRMED (accuracy). FIXED: current `try/finally` is now described as a property
  to PRESERVE; real requirement is the runner wrapping the whole run in
  `try/finally`.
- **MEDIUM 4 — `commands: {}` "would wipe the default" contradiction.** CONFIRMED.
  FIXED: bullet corrected — `{}` does not wipe; disablement is via `enabled: false`.
- **MEDIUM 5 — `--dry-run` prime/interactive side-effects underspecified.** GAP.
  FIXED: new Risks bullet — dry-run suppresses sudo priming, the refresher thread,
  and all `subprocess.run`; test asserts zero spawns.
- **MEDIUM 6 — capability-raise surfacing unspecified.** GAP. FIXED: runner wraps
  each `use` call, unexpected raise → failed `StepResult`, `FatalError` →
  CLI panic; test added.
- **MEDIUM 7 — `.local.yaml` twin additive-only.** CONFIRMED additive; local-wins
  ordering was contingent on Finding 1, now resolved by the explicit sort.
- **LOW 8 — `with_` Pydantic alias not wired.** CONFIRMED. FIXED: `Field(alias="with")`
  + `populate_by_name=True` + `Field` import.
- **LOW 9 — mutable defaults.** Non-issue under Pydantic v2 (per-instance copy);
  no change.

Reviewer verdict: sound with these fixes; Findings 1–2, 6, 8 were load-bearing and
are now applied. Design is ready for task breakdown / Phase 0.

**Implementation note, 2026-09-26 (Phases 0.2–3.3 landed).** One deviation from
the design as written: `default.yaml` is loaded via
`Path(__file__).with_name("default.yaml")`, NOT
`importlib.resources.files("sysup")` as the Module-placement section specified.
Reason: under pytest's `--import-mode=importlib` the `sysup` name is a namespace
shared with the test package, so `importlib.resources.files("sysup")` resolved to
the test directory. The `Path(__file__)` form is the same wheel-safe pattern `bim`
already uses for its bundled yaml, and `default.yaml` is tracked + packaged by
hatchling (bim precedent). Verified: `pytest -m sysup` 117 passed, `pytest -m lib`
1443 passed, `mypy src/tools/sysup` clean, `sysup --dry-run` reproduces today's
mac order.
