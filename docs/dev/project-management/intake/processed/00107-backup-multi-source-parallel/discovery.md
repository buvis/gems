# Discovery: backup multi-source operations

## Classification

Depth: comprehensive | Date: 2026-10-12 | Status: processed, specced as PRDs 00107, 00109, 00110, 00111, 00112

Source: `idea.md` beside this file. Renumbered from 00092 on 2026-10-25 when
salvaged from the stale `feature/add-local-backup-capabilities` worktree.

## Problem

Backup already runs multiple configured instances, but runs them sequentially
without live progress. Each archive accepts one source directory, and repeated
runs replace an existing output. Intake 00107 explores a more flexible run loop
while preserving the existing archive integrity guarantees.

## Requirements

### Must have

- Safer repeated runs: no-clobber, explicit skip reasons, and tolerant missing bundle items.
- Faster, visible runs: bounded parallelism and live progress.
- Run at most three archive instances concurrently by default; `--jobs N`
  overrides the limit, with `--jobs 1` providing sequential execution.
- Configured `(order, name)` determines launch priority, not a completion barrier.
  Fill available worker slots from that order. An individual archive failure
  does not stop unrelated jobs; report all outcomes and fail the overall run.
- On Ctrl-C, stop launching jobs, cancel active work, clean up temporary files,
  and return nonzero. Preserve already completed archives and prior outputs for
  jobs cancelled before publication. Never publish an incomplete archive.
- Live progress shows each archive's phase and elapsed time, with percentage
  only when processed input is reliably measurable for the selected engine.
  Otherwise show activity without a percentage. Nonterminal output and
  `--quiet` suppress live redraws while retaining final results.
- Flexible archive contents: selected files/directories bundled into one archive.
- Bundles select items under one common base directory and preserve their paths
  relative to that base in the archive. Unrelated locations can use separate
  backup instances; arbitrary source-to-member mappings are outside this scope.
- Bundle item presence is tolerant by default: report missing selected items,
  archive those that exist, and explicitly skip the archive when none exist.
- A missing source root fails that instance, for both whole-tree archives and
  bundles. Item-level tolerance applies only within an existing source root.
- Skip an existing resolved output by default and report the reason. `--force`
  permits atomic replacement. Protection is based on the resolved output path,
  not a separate daily ledger; date-only naming provides one archive per day.
- Intentional skips are successful run outcomes: exit 0 when every selected
  instance is archived or intentionally skipped, including an all-skipped run.
  Summarize archived/skipped/failed counts and skip reasons; actual failures
  produce a nonzero exit code.
- Add a read-only `--plan` preview showing sources, resolved outputs, and expected
  run/skip/failure status without walking entire source trees. Retain the existing
  detailed, walk-based `--dry-run`. A plan is a point-in-time preview, not a
  guarantee against later filesystem changes or read failures.

### Out of scope

- Persistent per-archive log files.
- A dedicated sandbox flag; alternate paths remain available through configuration.
- Arbitrary source-to-member mappings within bundles.

## Constraints

- Preserve atomic publication, durability, private archive permissions, compression,
  symlink preservation, and the existing exclude model.
- Keep execution shared through the Runner; route CLI output through console.
- Do not import the reference script's personal paths or source sets.
- Progress must not equate compressed output size with input bytes processed.
- Missing-item tolerance must not swallow permission errors, read failures, or
  files disappearing after selection. These are archive failures.
- No-clobber must hold at publication time, including across simultaneous runs;
  an existence check followed by unconditional replacement is insufficient.
- Bundle member selection must stay under the configured base, preserve links
  as links, and never follow a selected path through an intermediate symlink
  outside that base. Member names must be safe relative archive paths.

## Codebase Context

- `src/tools/backup/runner.py`: sequential instance execution; converts expected
  execution failures into structured `StepResult` outcomes.
- `src/tools/backup/step_result.py`: boolean success and optional archive metadata;
  no explicit skip status or progress event contract.
- `src/tools/backup/capabilities/tar_archive.py`: single-directory selection,
  pre-walk with byte totals, Python/system-tar engines, atomic output replacement.
- `src/tools/backup/config.py`: validated instance map, sorted by order/name.
- `src/tools/backup/cli.py`: selection, overrides, list/dry-run, final result rendering.
- `tests/tools/backup/`: existing CLI, config, archive, exclude, and invariant tests.
- `src/tools/backup/manifest.toml`: CLI is currently the only shipped interface.
  Progress and execution contracts must remain usable without a terminal.
- Both archive writers currently publish using `os.replace`; both need the same
  no-clobber policy. Python writing cleans up on `BaseException`; system-tar
  uses blocking `subprocess.run` and a cleanup `finally`. Concurrent cancellation
  needs explicit worker/process lifecycle handling, not just future cancellation.

## Approach

**Chosen direction**: extend the existing backup engine and shared Runner with
the three agreed capability groups. Keep file selection and exclusion rules
shared across the Python and system-tar engines. Render progress in the CLI
adapter from structured execution events rather than emitting from workers.

**Why**: multi-instance configuration, archive safety, and exclusion behavior
already exist. The missing capabilities belong in that execution path.

**Rejected alternatives**:

- Replace the engine with the reference shell script: loses existing guarantees.
- Arbitrary source-to-member mappings: user chose common-parent bundles.
- Strict order barriers: user chose launch priority.
- Mandatory percentages for both engines: user chose best available reporting.

**Proposed implementation choices, subject to review**:

- Extend `tar-archive` with an optional list of literal relative `items` under
  `source`. Omission retains whole-tree behavior and its source-name prefix;
  bundles use base-relative member names. Reject an explicitly empty list,
  absolute paths, and parent traversal; deduplicate overlapping selections.
- Apply existing exclusions relative to the bundle base, including applicable
  ancestor `.bkpignore` rules within that base. Explicit selection does not
  override exclusions.
- Resolve output stamps once per run. Reject duplicate resolved destinations
  within a selected plan before writing, even with `--force`; use race-safe
  publication for collisions between separate invocations.
- `--force` applies to the selected instances' output replacement only; it does
  not bypass source validation, exclusions, or path safety.
- Validate source roots before reporting an existing-output skip, so no-clobber
  cannot hide the missing-root failure selected in Q6.
- Implement in dependency order: bundle selection and outcome semantics;
  no-clobber and plan preview; concurrent execution/cancellation and progress.
  All remain in the agreed scope; this is not permission to ship a reduced scope.

## Success Criteria

- A bundle with two selected items archives only their allowed contents at
  base-relative paths; both engines preserve links and empty directories.
  Existing whole-tree configurations retain their archive member layout.
- One absent selected item is reported while present items are archived;
  all selected items absent produces a skip and no archive. A missing root,
  unreadable input, or read failure produces failure and a nonzero run exit.
- Repeating a run with the same resolved output preserves its bytes and reports
  a skip. `--force` replaces it only after a complete archive is ready. Concurrent
  unforced publishers cannot overwrite each other's completed output.
- Five ready jobs never exceed three active jobs by default; `--jobs 1` is
  sequential. Launch priority follows `(order, name)` without completion barriers.
  One failed job does not prevent unrelated jobs from finishing.
- Ctrl-C with queued and active jobs stops new launches, cancels writers and
  child processes, cleans their temporary files, and leaves no incomplete final
  archive. Completed archives survive; interrupted execution returns nonzero.
- An all-skipped run exits 0; mixed archived/skipped/failed outcomes have accurate
  counts and reasons, with any failure producing a nonzero exit.
- Terminal progress includes phase and elapsed time; any percentage is grounded
  in measured processed input, never compressed output size. Nonterminal and
  quiet runs retain final results without live terminal redraws.
- `--plan` reports expected outcomes without recursive walks or writes and
  uses the same selection/output policy as execution. `--dry-run` retains its
  detailed read-only walk. Actual execution rechecks filesystem conditions.

## Risks

- **Incomplete backup accepted**: tolerant missing items and all-skipped success
  can conceal configuration mistakes. Always report reasons and counts; missing
  roots and I/O failures remain failures.
- **Concurrent output races**: preserve no-clobber at final publication, not
  merely at initial inspection; test competing writers.
- **Cancellation leaks**: cancelling a future does not stop a running writer.
  Test both engines and subprocess cleanup before calling cancellation complete.
- **Disk contention**: three workers may reduce throughput on some storage;
  provide `--jobs 1`, without promising a universal speedup.
- **Compatibility changes**: document default no-clobber and three-worker
  execution; retain prior whole-tree layouts and timestamp templates.
- **Moving source data**: archives are not filesystem snapshots. Progress totals
  may become stale; detected read failures must not become successful skips.

## Open Questions

- Review the proposed `items` schema, overlap handling, and exclusion semantics
  before promoting them from implementation proposals to PRD requirements.
- Specify structured progress/cancellation contracts and CLI flag combinations
  during design; no requirement to implement additional UI applications is inferred.
- Decide whether the proposed implementation stages form one PRD or a sequenced
  set; all agreed capabilities must remain covered.

## Discovery Log

### Q1: Which outcome matters most for the first version?

Options: safer repeated runs; faster, visible runs; flexible archive contents;
or all three, potentially delivered in stages.

**Answer**: "all three". All three capability groups are in scope; staging is
not yet decided.

### Q2: Should a bundle select items under one common parent or combine unrelated paths?

**Answer**: Option 1, confirmed after explaining the restore layout. A base of
`~` with selected `.config/tool` and `.toolrc` produces those relative archive
members and excludes unrelated home contents. Separate archives handle unrelated
locations. The illustrated `source`/`items` syntax is not yet a schema decision.

### Q3: If a selected item is missing, how should backup behave?

**Answer**: Option 2: tolerant by default. Archive whatever exists and report
missing items; skip the archive if none exist. This accepts the tradeoff that a
mistyped item may be reported as missing rather than fail the archive. This
decision concerns absent items, not permission errors or read failures.

### Q4: When the resolved output file already exists, should backup skip it by default?

**Answer**: Option 1: skip unless `--force`. Preserve the earlier archive and
report the skip. This deliberately changes the current always-replace default;
existing timestamp templates remain responsible for archive frequency.

### Q5: Should intentional skips count as a successful run for cron/scripts?

**Answer**: Option 1: yes. Exit 0 when everything was archived or intentionally
skipped; summarize archived/skipped/failed counts and reasons. Actual failures
exit nonzero. No distinct skip exit code.

### Q6: If an entire configured source directory is missing, should it also be skipped?

**Answer**: Option 2: fail. A missing source root may signal a disconnected drive
or incorrect path. This narrows Q1's broad reference to optional missing sources:
tolerance covers selected bundle items, not the source root itself.

### Q7: How much parallelism should a normal run use?

**Answer**: Option 2: three concurrent archives by default, overridden with
`--jobs N`. The user considers this a reasonable default. This bounds concurrency
but does not guarantee a speedup on a single disk; `--jobs 1` remains available.

### Q8: How precise does live progress need to be?

**Answer**: Option 1: best available per engine. Show each archive's phase and
elapsed time; show percentage only when processed input can be measured reliably.
Otherwise show activity without percentage. Keep final results and suppress live
redraws for nonterminal output or `--quiet`.

### Q9: Which additional conveniences belong in this version?

**Answer**: Option 1: plan preview only. Add lightweight `--plan` while preserving
detailed `--dry-run`. Persistent per-archive logs and a dedicated sandbox flag
are outside this version's scope.

### Q10: With parallel jobs, should configured order mean launch priority or a strict barrier?

**Answer**: Option 1: launch priority. Fill up to the concurrency limit in order;
a later job may start before an earlier one completes. Individual archive
failures are reported while unrelated jobs continue.

### Q11: When you press Ctrl-C, should active archives stop or finish?

**Answer**: Option 1: stop and clean up. Launch no more jobs, cancel active work,
remove temporary files, and preserve completed archives and existing outputs.
Return nonzero for the interrupted run.

### Consistency check

- Q6 narrows the broad wording in Q1: item absence is tolerated, root absence fails.
- Q5 makes intentional all-skipped runs successful; it does not excuse actual errors.
- Q10 makes order a launch priority, consistent with Q7's concurrent default.
- Q11 preserves prior outputs for cancelled jobs; already completed forced
  replacements remain completed archives, not candidates for rollback.

### Inferred from intake and code (not asked)

- Multi-instance selection already exists; no replacement job-list mechanism is needed.
- Existing integrity and exclude behavior must be preserved.
- Compressed archive growth is not a reliable completion percentage.

## Decisions after discovery (2026-10-29)

These override the answers above; the PRDs follow this section.

- **Q4 replaced**: no no-clobber and no `--force`. An existing resolved output is replaced, but only after the new archive is complete (atomic publication; a failed or skipped run leaves the prior output untouched). Two selected instances resolving to one output are rejected before writing (PRD 00110).
- **Q6 replaced**: a missing source root is a skip (success, reported with its reason), not a failure. A source that exists but is not a directory still fails (PRD 00109).
- **Added gap**: per-instance excludes, because the single global list drops `build`, `dist`, `out`, `target`, `.cache` directories from every tree (PRD 00107).
- **Staging**: one PRD per capability group, in order: 00107 per-instance excludes, 00109 bundle items + skip outcomes + replace-after-complete, 00110 `--plan` + output resolution, 00111 `--jobs` + cancellation, 00112 progress + `--quiet`.

## Late elicitation pass (2026-10-29, superseded)

A second `/elicit-requirements` run on the same day, in a session that had
not yet seen the create-prd pass above, asked three more questions. The
backup code was unchanged since this doc was written (last touch 1c68155f,
2026-09-27), so no other section needed a refresh. Where an answer differs
from the staging above, the staging wins; the user confirmed that after
seeing both.

### Q12: One PRD or a sequenced set?

**Answer**: three sequenced PRDs (bundles + skip semantics; no-clobber +
`--plan`; `--jobs` + progress + cancellation). Superseded by the five-PRD
staging above, which the user kept: it carves per-instance excludes out as
00107 and splits progress (00112) from parallelism (00111); the dependency
order is the same.

### Q13: How is a bundle configured?

**Answer**: optional `items:` on `tar-archive`, literal paths relative to
`source`; omission keeps whole-tree behavior and layout; absolute paths,
`..` and an empty list rejected at load; overlaps deduplicated; global
excludes and `.bkpignore` still apply inside selected items. Rejected: a
separate `tar-bundle` capability (duplicates walk, exclude and engine code)
and glob items (a glob matching nothing is indistinguishable from a typo).
Consistent with PRD 00109.

### Q14: When should the PRDs land?

**Answer**: next autopilot batch, in staging order. Consistent with the five
PRDs sitting in `prds/backlog/`.
