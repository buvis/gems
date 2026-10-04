# bkp — a backup gem for buvis-gems

**Status:** idea / not scheduled. Captured 2026-09-26 from the sysup 00079
design discussion. Author has "been thinking about it for a while."

## Why now

PRD 00079 (sysup configurable updaters) introduces **machine-local config** that
is deliberately **not tracked in git** — the `*.local.yaml` layer that lives
beside the dotfiles-shared `buvis-*.yaml` but is never `dot add`ed (see
`dev/local/designs/00079-sysup-configurable-updaters-v1-design.md`, "Config
structure & merge semantics"). This is generalized across **all** gems via the
shared config loader, so from 00079 onward every gem can have per-machine config
that exists on exactly one machine and nowhere else.

That is the gap this gem fills: **anything intentionally outside version control
still needs a recovery story.** Dotfiles are backed up by being in git; local
overrides, secrets, and machine state are not. Today there is no buvis-owned way
to back them up.

## Problem

Data that matters but is not in the dotfiles repo has no owned backup path:

- Machine-local config: the new `~/.config/buvis/*.local.yaml` layer (untracked
  by design).
- Secrets material outside the git-secret encrypted set.
- Application state that isn't config: e.g. `fctracker` data, `readerctl` /
  `outlookctl` caches or tokens, anything a gem writes under `~/.local/state`
  or a data dir.
- Arbitrary user-declared paths worth protecting on this host.

## Sketch (to be designed, not decided)

A `bkp` CLI gem under `src/tools/bkp/`, following the standard tool layout
(cli.py + settings.py + commands/), that:

- Reads a **backup manifest** — itself a `buvis-bkp.yaml` in the shared config
  stack, so *what to back up* is shareable via dotfiles while *where backups go*
  (target/credentials) is a `buvis-bkp.local.yaml` machine-local override. Eats
  its own dog food re: the 00079 local-layer mechanism.
- Backs up a declared set of paths/globs, with the **machine-local buvis config
  included by default** (that is the founding use case).
- Delegates the actual store to an existing, trusted engine rather than
  reimplementing dedup/encryption — candidates to evaluate: **restic**, **borg**,
  **rclone**, or plain **tar + age**. Pick one in design; do not hand-roll.
- Uses `pybase.filesystem.atomic_write` for any state/index it keeps (repo
  atomic-persistence invariant, PRD 00041).
- All-interface rule: a `bkp` action must be drivable from CLI/TUI/API/WebUI via
  one command class returning `CommandResult`, like every other gem.

## Open questions for the design pass

- Backup engine choice (restic vs borg vs rclone vs tar+age) — security,
  cross-platform (mac + WSL/Linux, matching sysup's targets), and dependency
  weight.
- Encryption at rest for secrets in the backup set — reuse git-secret's key, or
  the engine's own encryption?
- Scheduling: is `bkp` invoke-only (user/cron runs it), or does it own a
  schedule? Likely invoke-only; scheduling is the host's job (cron/launchd).
- Restore UX and verify/dry-run — a backup you can't test-restore is not a
  backup.
- Relationship to `sysup`: is "back up local config" a `sysup` capability
  (`use: bkp`) or strictly its own gem invoked separately? Leaning separate gem,
  because backup targets/credentials are a different trust surface than updaters.

## Convention notes

- Scaffold with `dev/bin/scaffold.py` when it graduates from idea to build (adds
  the tool skeleton + registers the pytest marker + the `[bkp]` extra).
- Next PRD number when scheduled: check `dev/local/prds/backlog/` for the current
  max at that time (00079 is taken by sysup as of this note).
