# backup: multi-source parallel archiving with progress and no-clobber

Status: processed, specced as PRDs 00107, 00109, 00110, 00111, 00112. Recorded 2026-10-12,
salvaged from the stale `feature/add-local-backup-capabilities` worktree on
2026-10-25 (renumbered from 00092, which PRD 00092 sysup attention layer took).

Inputs only — this file maps a reference shell implementation against the
current `backup` gem to feed a later design pass. No decisions here.

## Source

A standalone POSIX/bash backup script (external, kept anonymous) that a user
runs on a workstation to tar several unrelated source trees into a single
backup directory. It was itself ported from an earlier Windows PowerShell/tar
script. We study it only as a **capability reference** — none of its hardcoded
paths, directory names, or environment details are carried into the gem; those
are the user's and stay out of this repo.

## Why look at it

The current `backup` gem (specs 00082 tar-archive, 00083 phase2 CLI/perf) does
one thing well: archive **one** source tree per instance into a timestamped,
atomic, `chmod 600` `.tar.gz`, with layered `.bkpignore` + global excludes.
The reference script is weaker on archive integrity but richer on **operational
ergonomics for backing up many sources in one run**: bundles, parallelism,
live progress, same-day no-clobber. Those are the concepts worth harvesting.

The two are complementary, not competing — the gem has the stronger engine; the
script has the stronger run-loop. This intake is about what the run-loop layer
could adopt.

## What the reference script does (concept map)

Behaviour abstracted from the script, with identifying specifics stripped:

1. **Multi-source single run.** One invocation archives a *list* of jobs. Each
   job = `label | parent_dir | item(s) | excludes`. The gem already has the
   multi-instance equivalent (`instances:` map + `--only` / `--tag`), so this
   concept is already covered — see mapping below.

2. **Bundled items into one archive.** A single job may name *several* items
   (space-separated) under a shared parent, archived into one tarball (e.g. a
   handful of individual dotfiles bundled as `dotfiles.tar`). The gem's
   `tar-archive` takes exactly one `source` dir — it has **no bundle concept**.

3. **Tolerant item presence.** In a bundle, a missing item is skipped silently;
   a job whose items are *all* absent is skipped (distinct exit code 3, not a
   failure). The gem treats a missing `source` as a **failed** step.

4. **Per-day no-clobber.** Output name embeds the date (`YYYYMMDD-label.tar`);
   if that file already exists the job is skipped unless `--force`. Prevents a
   second same-day run from overwriting the morning's backup. The gem's `out`
   can carry a strftime stamp but has **no skip-if-exists / --force** — it
   always writes (atomically overwriting any same-named file).

5. **`.partial` temp + rename-on-success.** Writes to `OUT.partial`, renames to
   `OUT` only on a clean tar exit; a crash leaves `.partial`, never a corrupt
   `OUT`. The gem already does the stronger version of this (sibling tempfile +
   `fsync` + `chmod 600` + `os.replace`) — concept **already covered, better**.

6. **Bounded parallelism.** Runs N jobs concurrently (`--jobs N`, default 3),
   throttling so it never launches all at once. The gem runs instances
   **strictly sequentially** (the `Runner` loops and yields per step).

7. **Live progress.** A background monitor pre-measures each source's size
   (`du`, minus excluded subpaths) and redraws per-job progress bars
   (`label [====   ] 42% 1.2G/2.8G`) by polling `.partial` size vs. expected.
   `--quiet` silences it for cron. The gem prints only a per-step result line
   at the end — **no progress**, no pre-measure.

8. **Dry-run plan.** `--dry-run` prints a table (label, resolved source,
   target, status: ok / SOURCE MISSING / would SKIP) and writes nothing. The
   gem has `--dry-run` but it *walks* each tree and reports file counts/bytes —
   a heavier, per-instance preview, not a one-line plan table.

9. **Per-job logs + failure accounting.** Each job writes a `.log`; a non-zero
   tar exit fails *that* job, is reported, leaves the `.partial`, and the run
   ends with a count of failed jobs and a non-zero exit. The gem renders every
   step (success and failure) and exits non-zero if any failed — concept
   **covered**, minus the on-disk per-job log file.

10. **Directory-name excludes.** Excludes are matched by directory *name*
    (e.g. `node_modules`, `__pycache__`, `.venv`, build/caches) — explicitly
    *not* gitignore-status, so a gitignored secret like `.env` is intentionally
    KEPT. The gem's exclude model is richer (global basename/relpath globs +
    path-scoped `.bkpignore` with `!unignore`), and likewise ignores
    gitignore status — concept **covered, superset**.

11. **Symlinks preserved.** tar stores links as links. The gem does the same
    (archives the link itself, never follows). **Covered.**

12. **Sandbox / test root.** `--sandbox DIR` repoints the home-like base and
    backup dir under a throwaway dir for safe validation. The gem has no
    equivalent run-level flag (tests drive it via config/tmp paths instead).

## Capability matrix: reference script vs. current `backup` gem

| # | Concept | Reference script | Current gem | Gap? |
|---|---------|------------------|-------------|------|
| 1 | Multi-source in one run | job list | `instances:` + `--only`/`--tag` | covered |
| 2 | Bundle many items → one archive | yes (space-sep items) | one `source` dir only | **GAP** |
| 3 | Tolerant missing item / all-missing skip | skip, exit 3 ≠ fail | missing source = fail | **GAP** |
| 4 | Per-day no-clobber + `--force` | yes | always writes | **GAP** |
| 5 | Atomic write (temp + rename) | `.partial` + mv | tempfile+fsync+chmod+replace | covered (stronger) |
| 6 | Bounded parallelism `--jobs N` | yes (default 3) | sequential only | **GAP** |
| 7 | Live progress bars + pre-measure | yes; `--quiet` to mute | end-of-step line only | **GAP** |
| 8 | Dry-run plan table | one-line-per-job table | per-tree walk w/ counts | partial / different |
| 9 | Per-job log file | `.log` per job | console step result | partial (no file) |
| 10 | Dir-name excludes, keep gitignored secrets | by name | globs + `.bkpignore` | covered (superset) |
| 11 | Symlinks preserved | yes | yes | covered |
| 12 | Sandbox test root flag | `--sandbox DIR` | via config/tmp in tests | **GAP** (minor) |
| 13 | Compression | tar (uncompressed `.tar`) | gzip (`.tar.gz`) | covered (gem stronger) |
| 14 | Per-archive `chmod 600` | no | yes | covered (gem stronger) |

## Candidate concepts to carry into the design pass

Ranked by apparent value, not yet decided:

- **Bundle capability** (#2): a source list → one archive. Either a new
  capability (`tar-bundle`) or extending `tar-archive`'s `source` to accept a
  list under a common parent. Needs #3's presence-tolerance to be useful.
- **Presence tolerance / skip semantics** (#3): distinguish "source absent →
  intentional skip" from "source failed". Affects `StepResult` (a skip is
  neither success-with-archive nor failure) and the CLI exit mapping.
- **No-clobber + `--force`** (#4): skip when the resolved stamped `out` already
  exists; `--force` to overwrite. Must resolve the stamp first.
- **Bounded parallelism** (#6): run N instances concurrently. Interacts with
  progress (#7), per-step ordering of console output, and the all-interface
  rule (the Runner stays the one seam; parallelism lives there).
- **Progress reporting** (#7): pre-measure + live bars. Biggest design surface —
  must route through `console` (no raw writes), degrade for non-TTY/`--quiet`,
  and reconcile with the atomic tempfile name (the gem's temp isn't a
  predictable `.partial`, so size-polling needs a hook).
- **Plan table dry-run** (#8): a lightweight `--list`-style plan distinct from
  the current walk-based `--dry-run`, or a `--plan` mode.
- **Sandbox flag** (#12): minor; mostly a test-ergonomics nicety.

## Explicitly out of scope / already better in the gem

- Atomicity, durability, `chmod 600`, compression — gem already exceeds the
  script. Do not regress these to match the script.
- Exclude model — gem's layered `.bkpignore` + globs is a superset of the
  script's name-list. No change needed.
- The script's hardcoded source set, OneDrive/cloud target, and PARA-style
  folder layout — user-specific, never enters the repo or config defaults.

## Open questions for the design pass

- Bundle vs. multi-instance: does #2 earn a new capability, or is "run many
  single-source instances" (already supported) enough once presence-tolerance
  (#3) lands? What real need is a bundle that N instances can't meet?
- Parallelism + progress together touch console output ordering and the
  all-interface seam — can both be added without breaking the one-command-class
  rule, and how does a parallel run render over API/TUI vs. CLI?
- No-clobber default: skip-if-exists by default (script's behaviour) is safer
  for repeated same-day runs but changes the gem's current always-write
  contract. Default on or off?
- Progress needs the in-flight archive size; the gem's atomic tempfile is
  randomly named — expose a measurable hook, or estimate from the walk's
  pre-counted `total_bytes` only?
- Skip exit semantics: how does an intentional skip map to `CommandResult` /
  CLI exit code without a cron treating a skipped-because-present run as either
  failure or silent success?

## Convention notes

- Any new behaviour must obey the repo invariants: atomic persistence (keep the
  tempfile+fsync+replace path), console-only output (no `print`/raw writes even
  for progress), `CommandResult`/`StepResult` discipline, and the
  all-interface rule (the `Runner` stays the single seam).
- The `backup` tool is CLI-only today (`manifest.toml`: `cli = true`, others
  false); adding progress/parallelism should not quietly assume a TTY.
