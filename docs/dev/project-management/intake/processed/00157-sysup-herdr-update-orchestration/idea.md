# sysup: Herdr update completion and clone porting

Status: processed, specced as PRDs 00157, 00158, 00159 and 00160. Recorded 2026-11-15.

Discovery and pinned upstream evidence are in `discovery.md` and `evidence.md`.
The isolated bridge lifecycle test passed. All five discovery review lenses are
resolved; see review.md. These are implementation specs, not shipped features.

User constraint: "I have no way of influencing upstream". Upstream changes
cannot be a delivery dependency. Pursue a local read-only bridge; the disposable
prototype is at `../../../spikes/herdr-update-bridge/`.

Split from intake 00156. This preserves the original remaining work after its
clone-audit slice became PRD 00156; none of this follow-up is implemented.
Source: `../00156-sysup-herdr-update/idea.md` and its sibling
`evidence.md` and `discovery.md`.

## Specified intent

- Trigger app update checks and core updates from sysup where useful beyond
  Herdr's existing automatic downloads and post-app-upgrade core update.
- Offer an explicitly opt-in app restart, default off, with readiness and
  completion evidence. Keep package-managed cores under their package manager.
- Preserve trustworthy upstream mod/layout snapshots before replacement.
- Support a reviewed three-way port of personal clones using old upstream,
  new upstream and the personal copy; constrain writes to selected copies.
- Validate the result before advancing provenance. Keep unresolved work visible
  through sysup attention. Preserve rollback and local modifications.

## Evidence and constraints preserved in the specs

- Herdr 0.1.16 CLI help has update actions but status contains no update state.
  The generated in-mod updates API exposes it; no stable CLI completion query
  or synchronous action response was verified. A successful dispatch must not
  be called an installed update. Do not assume check-then-update is synchronous.
- hmod deliberately owns community-mod updates and excludes personal clones.
  Extend ownership coherently rather than adding a competing community updater.
- Clone metadata can point at a missing personal parent. A present-day snapshot
  cannot recover a missing historical merge base, and app-version equality
  cannot establish source-content equality.
- Herdr mod checks execute initialization and can have effects. A passing check
  covers initial rendering only, not deferred UI behavior or layout validity.
- App restarts may replace shipped assets outside sysup. A pre-update snapshot
  inside sysup alone is not a guarantee that every prior version was captured.

## PRD map

- [00157 — observation bridge](../../../prds/backlog/00157-sysup-herdr-bridge-v1.md): explicit installation/loading and fresh bounded samples.
- [00158 — snapshots and provenance](../../../prds/backlog/00158-sysup-herdr-snapshots-v1.md): immutable content, explicit adoption, bounded retention and home lock.
- [00159 — observable updates](../../../prds/backlog/00159-sysup-herdr-updates-v1.md): opt-in orchestration, restart off by default, verified targets and preserved sources.
- [00160 — reviewed clone ports](../../../prds/backlog/00160-sysup-herdr-clone-porting-v1.md): candidates, digest-bound review/validation, recoverable apply and rollback.

Build dependencies: 00157 → 00158 → 00159; 00160 depends on 00156, 00157 and
00158, independently of 00159. Unresolved questions: none blocking specification.
