# klyreon D: autonomous maintenance, report-only pruning, scheduler

<!-- requirements; migrated from PRD 00077 flat file -->

## Overview

### Problem Statement
Ingest makes the vault bigger. Only maintenance makes it richer: promoting material that earned promotion, moving assent when corroboration arrives, catching the structural rot that a growing graph accumulates, and naming the fleeting notes that never earned survival. Without it a klyreon vault becomes the archive the whole design exists to avoid. And without a scheduler, maintenance runs when the owner remembers, which is the trigger discovery Q7 explicitly rejected.

### Target Users
The vault owner, and cron or launchd on their behalf. This PRD closes the autonomy loop: after it lands, a source dropped into `sources/` becomes committed, cross-linked, promoted knowledge with no human in the path.

### Success Metrics
- Discovery criterion 3: with pruning at its default, a maintain run over backdated fixtures deletes nothing and lists exactly the expected candidates in its trail and in `status`; with `pruning_enabled: true`, the same run removes them, cleans inbound references, and the vault validates clean afterwards.
- Discovery criterion 4: a scheduled run over a mixed corpus completes with zero human input, `klyreon validate` stays clean, no run hangs, and `status` shows both mean links per zettel and the `literature`+`evergreen` count higher at the end than at the start. The fixture corpus is seeded so at least one claim reaches its second corroboration inside the window.
- An interrupted maintain run leaves a `validate`-clean vault, and the re-run completes the remainder without redoing what already landed.
- `klyreon schedule install` then `schedule status` reports the artifact present, loaded, and matching its recorded hash, on macOS and on Linux.
- MOC member blocks match the vault after a sweep: every zettel anchoring to a MOC is listed, every stale member is gone, and human prose around the block is untouched.
- Running maintain twice in a row makes no change on the second pass.
- gems gates green: `pytest -m klyreon`, ≥50% tool coverage, mypy strict, ruff, docs, CHANGELOG.

## Functional Decomposition

### Capability: Maintenance sweep
The idempotent, cron-safe pass over the whole vault.

#### Feature: maintain command
- **Description**: `klyreon maintain` runs lint, promotion, assent transitions, and prune detection in one pass.
- **Inputs**: The vault; `--dry-run`.
- **Outputs**: `CommandResult`; one trail file; `last_maintain` written to `$XDG_STATE_HOME/klyreon/state.json`; exit 1 when lint found errors.
- **Behavior**: Refuses in a non-git vault through PRD A's autonomy gate. Takes PRD B's vault lock, released in `finally`. Order: lint the whole vault, then apply transitions, then reconcile MOC membership, then detect prune candidates, then write and commit the trail. Idempotent by construction: every rule is a function of vault state, so a second run finds nothing to do. `--dry-run` reports every transition and candidate and writes nothing, not even the trail.

#### Feature: Lint
- **Description**: Every mechanical check, reported rather than fixed.
- **Inputs**: The vault.
- **Outputs**: A findings list in the trail, grouped by rule.
- **Behavior**: Calls PRD A's `validate_vault` rather than reimplementing anything: orphaned concept zettels, dangling `sources`/`links.to`/`mocs`/`doubts[].target.to`, legacy colon-prefixed tags, enum violations, stale reviews, cycles in the transitive relations, oversized zettels. Maintain never edits a file to fix a lint finding: the fixes are semantic and belong to a human or to ingest. Findings do not block the transitions below.

#### Feature: Lifecycle promotion
- **Description**: Rule-driven movement through `fleeting`, `literature`, `evergreen`.
- **Inputs**: Each concept zettel's `sources`, `links`, and the `supports` links pointing at it.
- **Outputs**: A new `lifecycle` value and a bumped `updated`.
- **Behavior**: `fleeting` to `literature` when the zettel cites at least one source and carries at least one link in either direction: it earned a place in the graph. `literature` to `evergreen` when at least two distinct source documents back it, counted across its own `sources` plus the `sources` of every zettel that `supports` it. Spec 7.3 also says "rewritten for general use", which no rule can check; that clause is deliberately dropped and the mechanical half kept. Promotion never resets `processed` (spec 7.7): these are rules the owner already set, not new material.

#### Feature: Assent transitions
- **Description**: Rule-driven movement of the Stoic state.
- **Inputs**: Corroborating `supports` links, `disagreement` doubts on or targeting the zettel.
- **Outputs**: A new `assent` value and a bumped `updated`.
- **Behavior**: `tentative` to `accepted` when two or more distinct source documents corroborate it, counted across the `sources` of the zettels that `supports` it and excluding its own (discovery Q19 keeps the threshold at two). An open `disagreement` doubt on the zettel, or one anywhere in the vault whose `target` names it, holds it where it is. Maintain never writes `rejected`: that comes from a supersede at ingest (PRD B) or from the owner. No transition resets `processed`.

#### Feature: MOC membership sync
- **Description**: Reconcile every MOC's member block with the zettels that actually anchor to it (the discovery must-have PRD B hands off).
- **Inputs**: The vault graph; each MOC's `<!-- klyreon:members -->` block as written by PRD B's `ensure_moc`.
- **Outputs**: A rewritten member block per MOC that drifted, one commit per MOC.
- **Behavior**: Membership is a function of the vault, not an append log: a zettel whose `mocs` names this MOC and is missing from the block gets added; a member link whose zettel no longer names this MOC, or no longer exists, gets removed. Only the marked block is rewritten, so human prose around it survives (PRD B's rule). Deterministic, so no LLM call and no `processed` reset, and a second sweep finds nothing to do. A MOC named by a zettel's `mocs` but absent from disk is a lint finding, not a create: `maintain` never authors new MOCs, only ingest does.

#### Feature: Atomic per-zettel transitions
- **Description**: One zettel's change lands whole or not at all.
- **Inputs**: A planned transition or prune.
- **Outputs**: One git commit per zettel.
- **Behavior**: Each zettel's rewrite goes through `atomic_write` and gets its own scoped commit, so an interrupted sweep leaves every applied zettel committed and every unapplied one untouched. A prune is the case that needs the grouping: the file deletion, the removal of every inbound `links` entry and `doubts[].target` reference, and the MOC member removal all land in one commit, so no run ever leaves a dangling reference. The re-run finds the remaining work and finishes it.

### Capability: Pruning
Overload control, off until the owner asks for it.

#### Feature: Prune-candidate detection
- **Description**: Name the fleeting material that never earned survival.
- **Inputs**: Each concept zettel; `prune_window_days` (default 365).
- **Outputs**: A candidate list in the trail and in `status`.
- **Behavior**: A candidate is `lifecycle: fleeting`, with no inbound and no outbound links, no corroboration, `assent` other than `rejected`, an empty `delivered-as`, and an `updated` (or `created` when absent) older than the window. The two exemptions are spec 7.3's: a `rejected` zettel is the record of what was considered and refused, and a zettel carrying `delivered-as` backs work that already shipped. Detection always runs.

#### Feature: Opt-in deletion
- **Description**: Deletion happens only when the owner turns it on.
- **Inputs**: `pruning_enabled` (default false); the candidate list.
- **Outputs**: Deleted files and cleaned inbound references, one commit per prune.
- **Behavior**: Report-only by default (discovery Q19): material stays valuable long after it stops moving, so no machine deletes without explicit consent. With pruning enabled, each candidate is deleted with its inbound cleanup in the same commit; git history is the archive, which is why the autonomy gate's non-git refusal matters most here. `--dry-run` reports the same list either way. The count is visible in `status` on every check, so the backlog stays loud rather than silently growing.

### Capability: Scheduler
The external trigger, since there is no daemon.

#### Feature: schedule install
- **Description**: `klyreon schedule install` writes the platform's scheduler artifact.
- **Inputs**: `--at HH:MM` (default 03:00); the resolved absolute `klyreon` binary path; the installing shell's `PATH`.
- **Outputs**: On macOS `~/Library/LaunchAgents/net.buvis.klyreon.plist` with label `net.buvis.klyreon`, bootstrapped with `launchctl bootstrap gui/<uid>`; on Linux one crontab line marked `# klyreon-managed`. A manifest entry with `kind: schedule`, the artifact path, its hash, the platform, the binary path, and the klyreon version.
- **Behavior**: The scheduled command is `/bin/sh -c '<klyreon> ingest; <klyreon> maintain'`: a semicolon, not `&&`, so a failed source never stops maintenance. Both artifacts carry an explicit `PATH` captured at install time, because klyreon shells out to the operator CLI and neither cron nor launchd inherits a login shell's PATH: this is the trap that silently breaks scheduled runs. Re-runnable: install strips its own marked crontab lines or boots out its own label before writing, so a machine change or a reinstalled binary is one re-run. It never touches the vault, so it works before `init`. An unsupported platform fails with a clear message naming the manual equivalent.

#### Feature: schedule status and uninstall
- **Description**: Show or remove the installed schedule.
- **Inputs**: The manifest entry and the artifact on disk.
- **Outputs**: `schedule status` reports present or absent, hash match, loaded state (`launchctl list` or `crontab -l`), the scheduled time, and when maintenance last ran; `schedule uninstall` removes the artifact and the entry.
- **Behavior**: A hash mismatch means the owner edited the artifact, and status says so instead of silently rewriting it. Uninstall boots out the launchd label or strips the marked crontab lines, removes the file, and drops the manifest entry. A missing artifact with a live manifest entry is reported, not treated as an error.

#### Feature: init offers the schedule
- **Description**: `klyreon init` offers to install the schedule.
- **Inputs**: The interactive answer; `--schedule` / `--no-input`.
- **Outputs**: The schedule install folded into init's report.
- **Behavior**: TTY only, same rule as PRD C's operator offer. With `--no-input` or a non-TTY stdin, init skips it and prints the follow-up command. No autonomous run ever reaches this path.

### Capability: Status completion
The last two numbers the dashboard was missing.

#### Feature: status gains prune candidates and maintenance freshness
- **Description**: Finish `klyreon status` against the discovery requirement.
- **Inputs**: The candidate rule; `last_maintain`.
- **Outputs**: Prune-candidate count (and whether deletion is enabled), plus the last maintenance timestamp and staleness line.
- **Behavior**: Computed on demand from the vault, same as every other number in `status`. No index file and no lint-report file are ever written (discovery Q14).
