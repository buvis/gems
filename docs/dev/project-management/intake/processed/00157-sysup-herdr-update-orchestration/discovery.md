# Discovery: Herdr update orchestration and clone porting

## Classification

Depth: comprehensive | Date: 2026-11-15
Source: `idea.md` beside this file; evidence: `evidence.md`.
Clarity: high; scope breadth: high; existing-code impact: medium; complexity:
high. The work spans live application lifecycle, durable source provenance,
and supervised changes to executable personal extensions.

## Problem

PRD 00156 will surface personal-clone drift but cannot resolve it. The remaining
intent is to coordinate app/core updates and safely prepare clone ports without
losing local edits. Herdr owns app downloads, hmod owns community mods, and neither
provides a personal-clone merge workflow. Herdr's current CLI can request updates
but cannot report their eventual completion.

## Requirements

### Must have

- Distinguish requested, running, completed, failed and unobservable updates.
  Never infer installation success from command exit zero alone.
- Keep app restart explicitly opt-in and off by default. Honor core package
  ownership and preserve the user's running terminals.
- Keep sysup's ordinary update pass deterministic. An attended porting action
  may prepare changes, but cannot silently apply generated code or start an
  agent merely because a clone has drifted.
- Record immutable source content and its provenance. Identify home, asset
  kind/name, source identity, observed version, content digest and capture basis.
  Distinguish an observed source snapshot from a verified historical merge base.
- Treat absent personal ancestry as unresolved. A tagged upstream source is
  only a candidate baseline unless its relation to the clone is established.
- Prepare old-source/new-source/local-copy inputs outside the live Herdr home.
  Preserve local additions/deletions and Herdr's clone name transformations.
- Produce a reviewable candidate and diff. Refuse application if the live copy
  changed after preparation, and retain a recoverable pre-application copy.
- Advance provenance only after the chosen validation and approval conditions
  are satisfied. A smoke check alone must not certify layout or async behavior.
- Surface unresolved work through existing sysup attention; do not create a
  competing community-mod updater or silently clear a pending repair.

### Out of scope

- Replacing Herdr's downloader, package-manager updater, hmod, or agent launcher.
- Terminating terminals, forcing permissions, treating a missing merge base as
  an empty tree, or overwriting user clones during unattended sysup runs.
- Automatically putting the entire Herdr home under git, including its state.
- Claiming that pre-restart snapshots cover updates performed outside sysup.

## Constraints

- Herdr 0.1.16 has no supported CLI update-state query; upstream master also
  lacked it at inspection. A socket client does not remove that limitation.
- A bridge mod must already be loaded to receive custom commands. Its loading,
  lifetime and restart behavior are part of the design, not installation trivia.
- Tests and implementation acceptance must run against fixtures/fake processes
  or a dedicated isolated Herdr environment, never the user's active window.
- All mutations use existing atomic persistence patterns and confined paths.
  External agents use the operator's existing authorized launcher. sysup checks
  imported paths/content and does not claim prompt text enforces isolation.
- Gems configuration stays under the buvis config locations. Runtime artifacts
  belong in XDG state/cache paths, scoped by canonical Herdr home.

## Codebase Context

- **Relevant code**: `src/tools/sysup/capabilities/__init__.py`,
  `src/tools/sysup/runner.py`, `src/tools/sysup/step_result.py`,
  `src/tools/sysup/attention.py`, `src/tools/sysup/default.yaml`,
  `src/tools/sysup/cli.py`, `src/lib/buvis/pybase/filesystem/atomic_write.py`.
- **Conventions**: capabilities return result iterators; command classes return
  CommandResult; adapters render; mocked subprocesses and temporary homes test
  lifecycle and persistence. No cross-tool business-logic imports.
- **Integration points**: prospective update adapter, snapshot/port application
  service and CLI adapter. Final files depend on the update integration choice.
- **Similar implementations**: hmod separates inventory, source records, checks,
  backup and updates. Its ownership and first-update consent policy should stay
  intact. PRD 00156 adds an independent read-only personal-clone audit.

## Approach

Keep four dependent slices: read-only bridge/client; observable update control;
provenance and bounded snapshot storage; attended candidate preparation/application. Do not combine
them into one large PRD or move unsolved contracts into an unattended build.

This discovery is an epic split into PRD 00157 (bridge), 00158 (snapshots),
00159 (update orchestration) and 00160 (attended ports). Snapshots precede update
orchestration because preservation must happen before installation dispatch.

The user ruled out relying on upstream influence. The local bridge is selected
under standing decision authority because it preserves the completion requirement.
The alternatives remain documented for comparison, not as a pending question:

1. A small bridge mod exposes updates() state. Recommended for functionality
   with the installed app. The isolated lifecycle/protocol spike passed;
   production setup explicitly owns installation and documents loading.
2. Require a supported upstream CLI extension. Rejected as a delivery dependency:
   the user has no way to influence upstream. If support appears independently,
   it can replace the bridge behind the same observation boundary later.
3. Dispatch only and explicitly report unverified completion. Least machinery,
   but cannot satisfy verified completion or automatic restart as currently stated.

Rejected: immediate check-then-core-update sequence, log/string scraping as proof
of completion, guessed raw-socket endpoints, and unreviewed live clone merges.

For provenance, prefer content-addressed snapshots plus pinned upstream commits
where appropriate. Preserve unknown ancestry rather than implementing a fake
three-way merge. The retention and baseline-acceptance contracts are recorded
in decisions.md.

## Success Criteria

- Fake asynchronous update scenarios cannot become completed on dispatch alone;
  tests distinguish timeout, stale observation, app restart and managed core.
- A closed or unobservable app causes no restart or fabricated success.
- Snapshot tests demonstrate content integrity, per-home separation, bounded
  retention and preservation of all baselines referenced by pending candidates.
- Preparation leaves the live clone byte-identical. Unknown or inconsistent
  ancestry produces an unresolved result, not an automatic merge.
- Application tests refuse changed live input, preserve rollback bytes, and
  leave provenance unchanged on validation, approval or write failure.
- Default sysup execution starts no agent and loads no candidate mod code.

## Risks

- **Bridge lifecycle**: the isolated experiment proved freshness and restart
  recovery; future upstream changes can break the loaded-instance contract.
- **Ancestry ambiguity**: clone metadata is a hint, not a source attestation;
  require observed/pinned evidence or an explicit replacement-baseline decision.
- **Renaming and layout state**: text rewrites and layout serialization make
  bytewise upstream-to-clone comparisons misleading; preserve both raw evidence
  and a documented transformed comparison basis.
- **Concurrent edits**: an agent or the user can change a clone while a candidate
  exists. Application must compare the prepared input digest before writing.
- **Executable validation**: checking a mod can run code. Separate static checks,
  isolated execution and attended visual validation instead of conflating them.
- **Scope growth**: update observation and supervised porting have different
  lifecycles. Split after contracts are decided, not by dropping original intent.

## Discovery Log

- Input already answers problem, hmod ownership, restart default and protection
  of local modifications. Those questions were skipped.
- Read the installed contract and pinned v0.1.16 source; verified the missing
  completion query, asynchronous threads, and already-loaded mod requirement.
- Verified historical v0.1.13 source is available, and clone creation records
  the current app version without verifying the source was shipped content.
- Asked which update integration to target: bridge, upstream extension or
  dispatch-only. The user then stated: "I have no way of influencing upstream".
  This rules out an upstream dependency; the bridge is the agent-selected route,
  not a claim that the user expressly requested its detailed protocol.
- Built a disposable read-only bridge prototype under
  `docs/dev/project-management/spikes/herdr-update-bridge/`. Its harness proves
  nonce freshness, stale reply rejection, check-mode silence, and simulated
  replacement. Herdr 0.1.16's native mod check passes with an isolated app home.
- The native checker fell back from launchd to in-process execution and warned
  that optional gpui-shell storage was denied. No permission was bypassed.
- No agent was launched and no version-changing update was exercised.
- Prepared a native lifecycle runner with copied binaries, private app/core
  state, denied IP networking and restricted writes. The host Seatbelt profile
  blocks nested sandbox creation even for /usr/bin/true. Warrant request
  `6dfead25680c91a6a4405410e7a0a192` was approved. Its bare binary copy failed
  macOS signature validation before any bridge observations. Complete signed
  bundle copies now pass codesign and --version. Approved request
  `c4eb22a215169f9c85428e346437907e` launched the isolated runtime and stopped
  its private core cleanly, but revealed a wrong init argument order in both
  prototype and harness. Correcting init(props, cx) passes the harness and a
  native check with the check-mode guard removed. Request
  `d28570053c8e9b932b5f92e396967d2b` passed the repeated isolated lifecycle
  test: fresh persistence, actual quit/relaunch, absent-block refusal and
  recovery after layout restoration. The private core stopped cleanly.
- `decisions.md` settles baseline adoption, bounded retention and attended
  candidate handling under standing authorization. No new user answer is claimed.

## Open Questions

1. **Resolved:** Use a local bridge; upstream changes cannot be a prerequisite.
2. **Resolved:** Fresh matching nonces and bounded polling prove observation;
   the native test proves persistence and restart recovery. PRD 00159 requires
   exact observed target versions for completion, never successful dispatch alone.
3. **Resolved in decisions.md:** Explicit digest-bound adoption establishes a
   future baseline; it never claims recovered historical ancestry.
4. **Resolved in decisions.md:** Preparation produces an agent-neutral candidate;
   the existing launcher is external. Explicit application binds reviewed and
   validated content to its digest and preserves rollback.
5. **Resolved in decisions.md:** A 1 GiB per-home budget, protected references,
   and explicit collection bound storage without automatic historical deletion.

Unresolved questions: none blocking these four specs. Actual update installation
and arbitrary candidate correctness were not proved by the transport experiment.
