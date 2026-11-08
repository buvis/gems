# sysup: update herdr-app, herdr-core and user-owned layouts/mods

Status: new. Recorded 2026-11-07.

## Problem

Herdr (desktop terminal/agent app, `~/.config/herdr-app`) has three update
surfaces and sysup covers none of them:

- **herdr-app** is `/Applications/Herdr.app` (symlink `~/.local/bin/herdr-app`),
  not a brew cask. It downloads updates by itself; `herdr-app do app.update`
  restarts into the downloaded one.
- **herdr-core** (`hc`, `~/.local/share/herdr-core/current`) updates through
  `herdr-app do app.update_core`; terminals keep running.
- **Shipped layouts/mods** are replaced whole on every app start, so they
  follow the app. **User clones** (`mod.clone` / `layout.clone`, e.g. `my-tabs`,
  `my-spaces`, `my-new-menu`, `layouts/buvis.json`) and community mods copied
  from herdr.dev/mods are never updated. Clones record
  `cloned_from: {name, version}`; nothing compares it with the running version.

Result: clones silently drift from upstream, and API changes in the rewritten
`gpui-kit.d.ts` / `herdr.d.ts` can break them unnoticed.

## Proposal

New sysup capability `herdr-update` (`capabilities/herdr.py`, registered in
`CAPABILITIES`; `herdr:` entry in `default.yaml`,
`when: { os: darwin, check: herdr-app }`).

Deterministic steps, no agent:

1. `herdr-app do app.check_updates`, then `app.update_core`. Both need a running
   window: skip with a message when `herdr-app status` fails.
2. Optional `with: { restart: false }` (default off): `herdr-app do app.update`
   last. sysup usually runs inside Herdr, so a restart must be opt-in.
3. Snapshot shipped mods and layouts into
   `~/.local/state/sysup/herdr/<version>/` before the update. Herdr keeps only
   the current shipped version, so this is the only baseline for a 3-way merge.
4. For each clone, compare `cloned_from.version` with the running version.
   Equal: nothing to do. Different: drift.
5. `herdr-app check <mod folder>` on every mod after the update; a failure
   fails the step.

Agent step, only on drift:

- Launch an agent (`hc run` or `herdr-app do tab.new --argv`) with old upstream
  (snapshot), new upstream (shipped) and the clone. Task: port upstream changes
  into the clone, run `herdr-app check`, report.
- Scope the agent's writes to `mods/<clone>` and `layouts/<clone>.json`. Clones
  can use `exec` and the network, so the diff is for the user to review.
- Do not bump `cloned_from` until the check passes. Record unresolved drift in
  sysup attention state (`attention.py`) so the next run surfaces it.

## Constraints and risks

- Seatbelt sandbox makes `/Applications` and `~/.local/share/herdr-core`
  read-only; an agent-session run needs warrant. A normal terminal run is fine.
- `~/.config/herdr-app` is not a git repo. Putting it under git (a `.gitignore`
  exists) gives rollback and a reviewable diff; consider it a prerequisite or
  a first step.
- Community mods: re-fetch is manual; out of scope except for the
  `herdr-app check` pass (optionally a symlink-to-checkout convention).
- Unverified: exact output of `app.check_updates` / `app.update_core`, and
  whether `cloned_from` is stored in `mod.json` or elsewhere. Read both before
  specifying.

## Open questions

- Should sysup perform the `app.update` window restart, or stop at "update
  downloaded, restart when ready"?
- Is the agent step part of this PRD, or a follow-up after the deterministic
  update + drift report ships?
