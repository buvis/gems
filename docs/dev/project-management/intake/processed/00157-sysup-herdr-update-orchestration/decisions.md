# Contract decisions for 00157

These are reversible engineering decisions under standing authorization, not
additional user answers. The user explicitly ruled out an upstream dependency
and approved the isolated runtime experiment. The corrected native lifecycle
test passed; RESULTS.md in the spike records the exact evidence and limitations.

## Ownership and decomposition

Keep four buildable slices: read-only bridge and client; update orchestration;
snapshot/provenance storage; attended port preparation and application. The
first implementation PRD keeps 00157. Assign 00158 to snapshots, 00159 to update
orchestration and 00160 to ports after the repository-wide collision scan.

Herdr owns update/download execution, hmod owns community mods, and sysup owns
orchestration and personal-clone workflow. No private Herdr socket protocol,
updater replacement, or upstream cooperation is required.

## Bridge and update control

- The bridge samples state only. It does not launch programs, fetch URLs,
  modify clones or start updates. Check mode performs no side effects.
- Each probe carries a new random request nonce. A response is useful only for
  that request, from the selected home, within the caller's bounded wait.
  Previously persisted state never authorizes an update or restart.
- Missing bridge, unsupported schema, malformed data and timeouts mean
  unavailable observation, not a healthy or completed update.
- Installation copies owned assets only and never overwrites an edited or
  unrelated mod. Loading is an explicit setup step in a personal layout; the
  installed-file check alone does not enable update orchestration.
- Update orchestration is an opt-in sysup entry. Restart stays false by default.
  Missing or unloaded observation on an enabled entry produces attention.
- Serialize sysup operations per canonical Herdr home with an OS-held lock;
  interruption releases it. Never use a stale lockfile as proof of ownership.
- Never replace a package-managed core. Do not start a second observed core
  update while one is running. Capture the offered target before dispatch.
- Completion requires a fresh state sample: no reported error, no running
  operation, and the expected installed target. An unexpected different version
  is reported for review rather than called success without a defined comparator.
- The check's seconds-resolution timestamp needs an explicit freshness rule:
  dispatch only after the previous successful timestamp is older than the
  current wall-clock second, then require a newer successful timestamp with
  checking false. Bound clock anomalies with the same monotonic deadline.
- Restart requires observed readiness and enabled restart policy. Reacquire the
  bridge after restart and verify the running app version matches the captured
  target. Lost connectivity alone is not successful restart evidence.
- Do not retry a mutating action automatically after a lost response. Observe
  its outcome or leave attention, avoiding duplicate updates/restarts.

## Historical baseline acceptance

- Capture actual source bytes with SHA-256 content identity, canonical home
  identity, asset kind/name, capture time and observed version basis.
- Release-tag contents are source candidates, not attestations of what a
  particular clone copied. Preserve raw evidence separately from the transformed
  comparison tree used for asset-prefix and self-overlay renames.
- Unknown ancestry stops automatic three-way preparation. No empty-base merge,
  guessed parent traversal, or metadata-only acceptance.
- Resolve an old unknown clone by an attended review/port, then explicitly
  adopt a chosen current source snapshot as its future baseline. Record this
  as user-adopted provenance, not recovered historical ancestry. Bind adoption
  to the reviewed clone digest and source snapshot digest.
- Do not rewrite cloned_from simply because the versions differ or a check passes.
  A provenance ledger holds accepted baseline identity, so a later audit can
  distinguish a reviewed baseline from a raw release-version mismatch.

## Snapshot retention

- Store immutable blobs/manifests under the existing XDG sysup state root,
  separated by a digest of canonical Herdr home. Use private directory access.
- Bound each home's store to 1 GiB by default; permit configuration through
  buvis-sysup.yaml. Count candidate and rollback bytes as well as source blobs.
- Estimate required bytes before publication; exceeding the cap fails without
  starting an update or discarding earlier data. Temporary staging is bounded
  by the admitted operation and cleaned on failure.
- Do not automatically delete historical snapshots. An explicit garbage-
  collection action first reports unreferenced data; deletion requires an
  explicit apply flag and a fresh reference scan under the home lock.
- Accepted baselines, pending candidates and rollback records pin their inputs.
  Corrupt references prevent garbage collection. Retention never silently
  makes a pending port or rollback impossible.
- Snapshot only confined regular files and directories. Reject symlinks,
  special files and path traversal; omit Git's internal directory. Do not copy
  the whole Herdr home, terminal state, socket, or unrelated shared state.

## Attended porting

- Ordinary sysup execution starts no agent. An explicit preparation action
  creates a private candidate workspace, immutable old/new/local inputs, a
  manifest, and an agent-neutral task describing the exact allowed candidate.
- The user may work in that candidate with their existing authorized agent
  launcher. sysup does not introduce another agent launcher or pretend that
  prompt instructions enforce a process sandbox. Its import/application boundary
  rejects escaped paths, symlinks and changes to immutable inputs.
- Preparation never changes the live clone. Unknown ancestry produces a useful
  diagnostic instead of an invented merge. The candidate may contain conflicts;
  application refuses unresolved conflict state.
- The review artifact covers additions, edits and deletions, identifies binary
  changes, and includes the exact candidate digest. Static validation and an
  isolated mod check are distinct from attended visual/async validation.
- Applying is an explicit attended action bound to the reviewed candidate
  digest and a validation record for that digest. Tests simulate those runtime
  approvals; the implementation PRD requires no human midway through its build.
- External isolated-check and visual/async records are operator-attested and
  digest-bound. sysup validates their identity and static content, launches no
  validation shell command, and never labels another process's isolation as
  machine-enforced. This keeps the existing launcher boundary explicit.
- Recheck the live clone digest before application; refuse changed inputs.
  Instruct the operator to stop concurrent editing during application. A
  filesystem digest check cannot guarantee exclusion of unrelated external
  editors; do not claim a cross-process filesystem transaction.
- Stage complete output first, preserve a complete rollback copy, and journal
  directory replacement so interruption can recover either state. Never write
  a mod's files one by one directly into the active directory.
- Advance accepted provenance only after successful application. Interruption
  cannot turn an incomplete installation into an accepted baseline. Rollback
  refuses to overwrite subsequent user edits without a separate explicit choice.

## Final experimental disposition

The native test demonstrated persisted fresh replies, reload after restart,
failure without the layout block and recovery after restoring the block.
Actual version-changing update installation remains outside the spike; production
state-machine tests must cover action completion and failure independently.

No blocking questions remain. Production engineering defaults are five-second
probes, a ten-second home-lock wait, a 120-second operation deadline, and a
1 MiB shared-state read limit. These are chosen limits, not measured guarantees.
The store budget is configured as herdr.budget_bytes in buvis-sysup.yaml;
both standalone commands and the runner must honor the selected config context.
