# sysup: update herdr-app, herdr-core and user-owned layouts/mods

Status: processed, specced as PRD 00156 (clone audit); remaining orchestration and porting retained in intake 00157. Recorded 2026-11-07.

## Processing outcome (2026-11-15)

The shipped hmod updater owns community mods. PRD
`../../../prds/backlog/00156-sysup-herdr-clone-audit-v1.md` adds a read-only
personal-clone audit with persistent attention. It has not been implemented.
See `discovery.md`, `evidence.md`, and `review.md` beside this file.

App/core orchestration, opt-in restart, snapshots and supervised porting remain
in `../00157-sysup-herdr-update-orchestration/idea.md`. Audit-first is an
explicit reversible planning assumption; the scope question received no answer
before drafting. The original proposal below is preserved as historical input,
not the final implementation contract.

## Reassessment (2026-11-15)

Former intake number: 00118. Renumbered to 00156 because 00118 is already
used by the completed, unrelated `00118-bim-create-scripting-contract-v1`
PRD. 00156 was checked free across this working tree and all local and
remote-tracking branch refs.

- **Shipped:** commit `a087e05e`, present on master and this worktree, adds
  `herdr-mods` to `src/tools/sysup/default.yaml`. It runs the existing hmod
  shim with `update --all` on macOS after mise, skipping when the shim or a
  running Herdr window is absent. hmod owns candidate selection and checks;
  sysup does not implement the original clone-porting proposal.
- **Verified:** `tests/tools/sysup/test_default_config.py` tests that wiring,
  ordering and skip guards. It passed in the targeted 93-test verification
  alongside muc reporting. This is configuration coverage, not a live Herdr
  update or verification of hmod's internal behavior.
- **Still absent from sysup:** app update checks, core updates, optional app
  restart, upstream snapshots, clone-version drift detection, agent-assisted
  clone/layout porting and persistent attention reporting. There is no
  `herdr-update` capability in the registry, including on
  `feature/config-local-layer-braid`.
- **Next discovery scope:** reconcile the proposal below with hmod's current
  ownership before specifying another updater. Keep app restart opt-in and
  settle whether clone-porting belongs in a separate follow-up. Reverify
  current Herdr commands and clone metadata; this check did not operate the
  app or read machine-local clone contents.

At reassessment time the remaining work was unspecced. The processing outcome
above now records the audit spec and the retained follow-up.

## Problem

Herdr (desktop terminal/agent app, `~/.config/herdr-app`) has three update
surfaces. At intake time sysup covered none; the mod-update subset now ships
as described above:

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
