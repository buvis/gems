# sysup: configurable, dotfiles-shareable system updaters

<!-- requirements; migrated from PRD 00079 flat file -->

## Problem

`sysup` today is four hardcoded Python command groups — `mac`, `pip`, `nvim`,
`wsl` (`src/tools/sysup/commands/**`) — each a class whose update steps are baked
into `subprocess.run` calls. Adding, removing, or reordering an updater means
editing Python and shipping a release. Nothing is user-configurable, and there
is no way to share an updater set across machines or add a machine-specific one.

The repo already has the substrate to fix this: the buvis config stack
(`~/.config/buvis/config.yaml` + `buvis.yaml` + per-tool `buvis-<tool>.yaml`,
`$BUVIS_CONFIG_DIR` override) does **deep-merge with later-overrides-earlier
precedence**, `${VAR}` / `${VAR:-default}` substitution, and safe-path /
world-writable checks. sysup should define its updaters *in that config* rather
than in code — shareable via dotfiles, with a machine-local layer merging on top.

But the current commands encode real, hard-won operational knowledge that a flat
"list of shell commands" cannot express:

- `brew` runs `update` → `upgrade` → `cleanup` as an argv sequence with
  early-abort on the first failure.
- `npm-check -gu` is **interactive** (inherits stdio); the others capture output.
- `helm` **guards**: parse `helm repo list -o json`, skip cleanly when no repos
  are configured, otherwise `helm repo update`.
- `nvim mason` drives a multi-line Lua probe (registers a
  `package:install:failed` listener, runs `MasonToolsUpdateSync`, prints
  sentinels), strips ANSI, parses `mason FAIL <name>` / `mason DONE`, honours a
  600 s timeout, and tails `mason.log` on failure.
- `sudo -v` is **primed up front** with a background refresher thread, released
  in `finally`, so brew casks don't prompt mid-run.
- `mise upgrade` **must run last** — it deletes replaced tool-version dirs the
  inherited PATH still points at.
- Every binary is re-resolved via `shutil.which()` before use (a concurrent
  `mise upgrade` can move a version-pinned binary).

A pure-data config cannot hold conditional/stateful logic like the helm guard or
the mason probe. So the redesign must separate *what is data* from *what is code*.

## Solution

Model the updater set as a **flat keyed map** in `buvis-sysup.yaml`, deep-merged
across the config stack so dotfiles ship a shared base and a machine-local file
overrides or adds entries **by key** (no list-append gymnastics — the existing
loader's dict deep-merge does exactly this). Each entry is one of two kinds:

1. **`run` entry** — an ordered list of **argv arrays** (`steps:`), executed in
   sequence with early-abort. No shell; the only expansion is the loader's
   `${VAR}`. This covers brew, uv, mise, lazy, treesitter, apt, snap.
2. **`use` entry** — invokes a **named built-in capability** that sysup owns and
   tests, with optional `with:` inputs. The conditional/stateful machinery
   (helm empty-repo guard, mason probe, per-interpreter pip discovery, sudo
   priming) lives in Python; config just opts in and supplies inputs. This keeps
   deterministic logic as deterministic code rather than flattening it into
   shell.

Invocation: **`sysup` with no argument runs every applicable entry** (in
`order`), where applicability is decided by each entry's `when` (OS guard +
`check` binary must exist) — replacing the hardcoded `sys.platform` subcommands.
`--only <name,…>` and `--tag <t>` filter. The four platform subcommands are
removed.

Backward compatibility: sysup ships a **bundled default config** reproducing
today's mac/pip/nvim/uv/helm/mise + wsl/apt/snap behaviour, host-selected via
`when`. With zero user config, `sysup` does what `sysup mac` / `sysup wsl` do
now. User/dotfiles config deep-merges on top, so a machine tweaks one field or
adds entries without redefining the base. Upgrade is a no-op regression-wise.

## Config schema

```yaml
# buvis-sysup.yaml — flat keyed map, deep-merged across the config stack
commands:
  brew:
    order: 10
    when: { os: darwin, check: brew }   # os guard + binary must exist
    steps:                              # run entry: argv arrays, early-abort
      - [brew, update]
      - [brew, upgrade]
      - [brew, cleanup]
    # optional envelope fields (all entries): interactive, timeout,
    # continue_on_error, tags

  npm-check:
    order: 20
    when: { check: npm-check }
    interactive: true                   # inherit stdio, don't capture
    steps: [[npm-check, -gu]]

  helm:
    order: 40
    when: { check: helm }
    use: helm-repo-update               # use entry: named capability, no with:

  nvim-mason:
    order: 60
    when: { check: nvim }
    use: nvim-mason
    with: { timeout: 600 }              # capability inputs

  python-packages:
    order: 30
    use: pip-outdated                   # per-interpreter pip discovery in code

  apt:
    order: 10
    when: { os: linux, check: apt }
    steps:
      - [sudo, apt, update]
      - [sudo, apt, upgrade, -y]
      - [sudo, apt, autoremove, -y]

# session-level: sudo priming (a capability that runs first when present)
prime:
  - sudo
```

### Per-entry envelope (both kinds)

| Field | Meaning |
|-------|---------|
| `order` | integer; entries run ascending. Encodes constraints like mise-last. |
| `when.os` | `darwin` / `linux` (etc.); entry skipped on non-matching host. Optional. |
| `when.check` | binary name; entry skipped (reported) if `shutil.which` misses it. Optional. |
| `interactive` | inherit stdio instead of capturing. Default false. |
| `timeout` | seconds; None = no timeout. |
| `continue_on_error` | if true, a failed step does not abort the entry / run. Default false (abort entry, continue to next entry — matching today's per-command isolation). |
| `tags` | list of strings for `--tag` filtering. |
| exactly one of `steps` / `use` | `steps`: list of argv arrays. `use`: capability name (+ optional `with:`). |

## Built-in capabilities (v1)

Code-owned, tested, referenced by name from config:

- `helm-repo-update` — the empty-repo JSON guard, then `helm repo update`.
- `nvim-mason` — the Lua probe + sentinel parse + timeout + `mason.log` tail
  (input: `timeout`).
- `pip-outdated` — per-interpreter outdated-package discovery and upgrade
  (today's `CommandPip`).
- `sudo-prime` — cache credentials up front with a background refresher, released
  in `finally` / on `BaseException` (per the claim/lifecycle-release invariant).
  Modelled as a session `prime:` concern, not a per-entry `sudo: true`; literal
  per-command sudo (like `sudo apt`) stays in `steps:`.

The registry is small and closed in v1 (no user-supplied Python). Each capability
declares its accepted `with:` inputs; unknown inputs are a config error.

## Requirements

### Must have

- `buvis-sysup.yaml` in the existing config stack defines a flat keyed map of
  updater entries; the config loader's deep-merge composes base + machine layers
  by key with later-overrides-earlier precedence. No new merge code.
- Two entry kinds: `run` (argv `steps:`, early-abort, no shell) and `use` (named
  built-in capability + optional `with:` inputs). Exactly one per entry.
- Common envelope on every entry: `order`, `when` (`os` + `check`),
  `interactive`, `timeout`, `continue_on_error`, `tags`.
- `sysup` (no arg) runs every entry whose `when` matches this host, in `order`.
  `--only <name,…>` and `--tag <t>` filter. The `mac`/`pip`/`nvim`/`wsl`
  subcommands and their `sys.platform` guards are removed.
- Bundled default config reproduces today's mac + wsl behaviour, host-selected
  via `when`; `sysup` with no user config behaves as `sysup mac` / `sysup wsl`
  do now. User config deep-merges on top.
- Built-in capabilities `helm-repo-update`, `nvim-mason`, `pip-outdated`,
  `sudo-prime` preserve today's guard/probe/priming behaviour exactly, including
  the mason timeout + `mason.log` tail and the `finally`-released sudo refresher.
- Binaries resolved via `shutil.which` at run time (not config-parse time).
- Commands return `CommandResult`; the CLI renders via `console` — no
  `console.panic` / `sys.exit` inside command classes (repo invariant). A
  skipped `when` and a failed step are reported, not raised.
- Config schema validated on load (Pydantic, matching `SysupSettings`
  `extra="forbid"`): unknown top-level keys, both-or-neither `steps`/`use`,
  unknown capability names, and unknown `with:` inputs are surfaced as clear
  config errors through `console`, never a stack trace.

### Nice to have

- `sysup list` — print resolved entries for this host (name, order, kind,
  applicability) so a user can see what a shared config does on this box.
- `sysup --dry-run` — show what would run without running it.
- `when` beyond os/check (e.g. `arch`, an arbitrary `check` predicate command).

### Out of scope (v1)

- User-supplied Python capabilities / plugin loading.
- Parallel step execution.
- Per-entry `shell: true`. If a genuine pipeline surfaces, add it as a capability
  rather than reopening the shell-injection surface.

## Success Criteria

- With zero user config, `sysup` on macOS and on linux reproduces today's
  behaviour exactly (same steps, same order, same guards).
- A shared `buvis-sysup.yaml` in dotfiles plus a machine-local override file
  produces the union — machine entries added, one shared entry's field
  overridden — with no code change and no list-append syntax.
- Adding, removing, or reordering a simple updater is a config edit, not a
  release. The four smart behaviours remain code, opted into by name.
- Full suite green; no `console.panic`/`sys.exit` inside command/runner classes.
