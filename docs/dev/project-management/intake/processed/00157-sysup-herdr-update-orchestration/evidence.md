# Evidence: Herdr update orchestration and clone porting

Inspected 2026-11-15. Initial evidence came from read-only local inspection and
upstream GitHub API reads. A later isolated native experiment passed; see the
experiment supplement below. No version-changing update or agent launch occurred.

## Versioned sources

- Installed binary: `herdr-app 0.1.16`.
- Upstream v0.1.16 resolves to commit
  `034f8b85f7e6bb71f8ff55cb4a80c548b2578c0f`.
- Upstream v0.1.13 resolves to commit
  `93b097f6e29fcb2d90a30dea2f03ce4e5dee7981`.
- Upstream master resolved during inspection to
  `8e1208deeff2a24441a192974e648c6fa0c5053c`; its CLI/status implementation
  still exposes no update-state query. Recheck before implementation.

## Update completion is not a CLI contract

[control.rs at v0.1.16](https://github.com/herdrdev/herdr-app/blob/034f8b85f7e6bb71f8ff55cb4a80c548b2578c0f/src/control.rs#L72)
implements commands, status, ls, do, feedback and shot. The client returns
nonzero when the reply contains an error field. A zero exit code does not
independently establish that an asynchronous action finished.

[window.rs control handler](https://github.com/herdrdev/herdr-app/blob/034f8b85f7e6bb71f8ff55cb4a80c548b2578c0f/src/window.rs#L3922)
returns window state and errors for status. It exposes no update-state request,
including through the socket; bypassing the CLI does not reveal a hidden query.

[update.rs](https://github.com/herdrdev/herdr-app/blob/034f8b85f7e6bb71f8ff55cb4a80c548b2578c0f/src/update.rs#L131)
has an internal status object with app version/readiness, core version/manager/
readiness/updating/error, successful-check time, and checking flags. check_now
wakes a background checker. update_core starts a thread and returns; managed
cores and already-running updates return without starting another update.

[window.rs update dispatch](https://github.com/herdrdev/herdr-app/blob/034f8b85f7e6bb71f8ff55cb4a80c548b2578c0f/src/window.rs#L3539)
can reject core update as already current. App update calls apply, which can
reject absent readiness, then drains documents, relaunches, and quits. A caller
must distinguish accepted action, completed update, and lost connection.

The generated local herdr.d.ts exposes the internal state through updates().
It also offers appHome(), checking(), nextCommand(), setShared(), and atomic
compare-before-write writeTextFile(). The later isolated experiment exercised
the read-only nextCommand/setShared/updates bridge and its restart persistence.

[window.rs command routing](https://github.com/herdrdev/herdr-app/blob/034f8b85f7e6bb71f8ff55cb4a80c548b2578c0f/src/window.rs#L2910)
delivers a custom mod command only to an already-loaded mod. Installing files
alone does not make a headless query service. A bridge needs an explicit loading
and lifetime strategy, including after app restart and layout changes.

## Shipped source is recoverable; clone ancestry is not always provable

[build.rs](https://github.com/herdrdev/herdr-app/blob/034f8b85f7e6bb71f8ff55cb4a80c548b2578c0f/build.rs#L36)
embeds default mods from defaults/mods. The window embeds layouts from
defaults/layouts. Pinned upstream commits can provide historical shipped
content without maintaining a complete mirror of every installed release.

[mods.rs clone implementation](https://github.com/herdrdev/herdr-app/blob/034f8b85f7e6bb71f8ff55cb4a80c548b2578c0f/src/mods.rs#L223)
copies the actual source directory, rewrites asset prefixes and self-overlay
names in UTF-8 files, then adds cloned_from with the running binary version.
It does not attest that the copied source equals the shipped release. The
v0.1.13 implementation uses the same transformations. Raw upstream files are
therefore not directly the renamed clone's three-way merge base.

[window.rs clone_layout](https://github.com/herdrdev/herdr-app/blob/034f8b85f7e6bb71f8ff55cb4a80c548b2578c0f/src/window.rs#L250)
parses and serializes the source layout, replaces cloned_from, and copies its
layout click-state file. Mod references remain unchanged. Layout state and
source JSON are distinct inputs, and source-file formatting need not survive.

The prior local inspection found buvis.json pointing to absent my-main at
version 0.1.13. No release tag can recreate that missing personal parent from
its name. It must remain unresolved unless a trustworthy historical copy or
an explicitly accepted replacement baseline is supplied.

## Persistence and ownership

Herdr replaces shipped mods/layouts at startup; edited shipped content is
rescued under an edited name. installed.json records hashes, not historical
bytes or a complete ancestry ledger. A snapshot taken only before a sysup-
requested restart cannot cover restarts or updates initiated elsewhere.

The existing hmod integration remains the owner of community mods. Personal
clone merges must preserve its boundaries. sysup's Capability/StepResult seam
and atomic attention storage are reusable; no porting command or update-state
bridge currently exists in gems.

Mod checks execute initialization, and their initial-render result is not
proof of later UI behavior. Candidate code should not be loaded automatically
into the user's live window merely to produce a successful update report.

## Experiment supplement

The corrected prototype passed its exact-source mocked harness, native checker
(also with the check-mode guard removed to exercise init(props, cx)), and the
approved isolated lifecycle run. That run used signed copies of Herdr 0.1.16
and hc 0.1.21, a private home/session, denied IP networking and restricted writes.
It proved fresh persisted replies, actual quit/relaunch recovery, failure without
the bridge's layout block and recovery after restoring it. The private core
stopped with exit 0. No live configuration or installed application was changed.

See `../../../spikes/herdr-update-bridge/RESULTS.md` for the initial prototype
failures, warrant IDs and proof limits. Its state sample had checked=null and
checking=true; successful network checking or version-changing installation is
not among the experiment's findings.
