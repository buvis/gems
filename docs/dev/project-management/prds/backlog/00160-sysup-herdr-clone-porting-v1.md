---
catchup: force
eligibility: test -f docs/dev/project-management/prds/done/00156-sysup-herdr-clone-audit-v1.md && test -f docs/dev/project-management/prds/done/00157-sysup-herdr-bridge-v1.md && test -f docs/dev/project-management/prds/done/00158-sysup-herdr-snapshots-v1.md
default_model: opus
model_tier_rationale: Three-way tree semantics, review-bound mutations, crash recovery and provenance updates require design judgment.
---

# sysup reviewed Herdr clone ports

Source: `docs/dev/project-management/intake/processed/00157-sysup-herdr-update-orchestration/discovery.md` and sibling decisions.md.
Depends on PRDs 00156 (audit), 00157 (commands) and 00158 (store/lock).
No dependency on update orchestration; current snapshots may be captured explicitly.

## Overview

### Problem Statement
Personal Herdr clones need upstream changes without losing local edits.
A version label and a passing initial-render check are insufficient authority
to replace executable personal code. Prepare reviewable candidates and apply
only exact reviewed content with recoverable replacement and honest provenance.

### Target Users
The solo developer maintaining personal mods/layouts with their existing editor or agent launcher.

### Success Metrics
Preparation never changes live bytes. Unknown ancestry never becomes an
invented merge base. Tests refuse stale, unreviewed, unvalidated or escaping
candidates, and inject interruption at every replacement/provenance boundary.
Ordinary sysup runs launch no agent and apply no candidate.

## Functional Decomposition

### Capability: Attended candidate preparation
Separate historical evidence, comparison inputs and editable output.

#### Feature: Three-way workspace
- **Description**: Prepare one personal mod/layout port outside its live home.
- **Inputs**: Kind/name, accepted baseline from PRD 00158, selected new source snapshot with the
  same source identity, current local clone.
- **Outputs**: Private bounded workspace, operation manifest, immutable raw old/new/local inputs,
  transformed comparison inputs, editable candidate, conflict report and agent-neutral task naming
  the exact editable directory.
- **Behavior**: Under the home lock, validate all identities/digests and pin inputs before
  publication. A destination is eligible only when it is absent from installed.json for its kind,
  has a valid cloned_from and has an accepted baseline; this refuses shipped and community mods
  without reading hmod records. Refuse shipped/community-owned destinations, unknown ancestry, changed source
  identity, absent required source snapshots and invalid metadata; explain how baseline adoption
  enables future ports even when the original parent is gone. Never infer a base from a tag.
  Preserve raw bytes.
  Reproduce documented clone transformations on comparison copies: mod asset prefixes/self-overlay
  names map source name to clone name; layout JSON and a mod's mod.json are compared structurally
  with cloned_from treated as provenance, not user content.
  Exact Herdr 0.1.16 clone rules (upstream file src/mods.rs, function clone_mod_at, commit 034f8b85, read
  2026-11-17), with FROM the source name and TO the clone name: every file whose whole content is
  valid UTF-8 gets these plain substring replacements, in this order, with no regex, no word
  boundary and no extension filter: `mods/FROM/` to `mods/TO/`; `"mods/FROM"` to `"mods/TO"`;
  `'mods/FROM'` to `'mods/TO'`; then, for each key `mod`, `"mod"`, `'mod'`, each of no space or one
  space after the colon, and each quote `"` or `'`: `KEY:` + space + quoted FROM to the same text
  with TO (for example `mod: "tabs"` to `mod: "my-tabs"`). Other files are copied unchanged, hidden
  files included; file names do not change. mod.json is then written again as pretty JSON with
  `cloned_from: {name: FROM, version: APP_VERSION}`. Preserve the local cloned_from field; acceptance lives in the
  ledger. Layout click-state files remain outside the port. For each path: identical sides win;
  local==old selects new; new==old selects local; two different text edits use three-way merge;
  differing binary changes, delete/edit and type conflicts require explicit resolution. Treat
  absence distinctly from empty content. Preserve file modes and additions/deletions. Report
  unresolved paths; never fabricate automatic resolutions. Candidate source is never executed by
  preparation.

#### Feature: Review and validation record
- **Description**: Bind review and validation evidence to exact candidate content.
- **Inputs**: Workspace ID, current candidate; explicit review/validation action with expected
  digest, reviewer rationale and evidence references.
- **Outputs**: Complete local-to-candidate diff including deletions/binary changes, digest-bound
  review record, static validation report and external-validation record.
- **Behavior**: Recheck immutable inputs and paths; reject symlinks, special files, traversal,
  altered raw inputs and unregistered files outside the candidate. Hash all candidate content/modes;
  enforce PRD 00158 accounting on import. Static validation checks JSON object/manifest shape,
  required main.js for mods, layout structure (one JSON object; cloned_from, when present, has the
  PRD 00156 shape; no deeper layout schema in v1) and unresolved conflict records/markers. Every
  recorded conflict requires an explicit resolution; a marker scan alone is insufficient. No agent
  or arbitrary validation command is launched. The operator uses their existing authorized isolated
  runtime to check a mod and test visual/async behavior; layouts require isolated visual validation.
  Record kind, candidate digest, tool/app version, outcome, evidence-file hash and operator
  attestation. For mods require both isolated check success and visual/async attestation; for
  layouts require visual/layout attestation plus static success. Label external records
  operator-attested, never machine-enforced isolation. Any candidate edit invalidates review and
  validation. Do not load candidates into the live window. Build/CI tests simulate all runtime
  attestations.

### Capability: Recoverable application
Apply explicit reviewed content without silently overwriting subsequent edits.

#### Feature: Apply, recovery and rollback
- **Description**: Replace one selected clone and advance accepted provenance.
- **Inputs**: Explicit apply action with workspace ID and expected reviewed digest; complete
  successful validation records; unchanged prepared live digest.
- **Outputs**: Operation journal, retained rollback input, final clone and accepted baseline, or
  recoverable diagnostic with no false completion.
- **Behavior**: Hold the home lock; refuse unresolved recovery journals before new mutations.
  Recheck live/source/candidate identities, review, validation and budget. Require the operator to
  stop concurrent editing. Stage the complete output on the destination filesystem, durably journal
  paths/digests and old provenance, then rename old asset to a confined unique backup and staged
  asset into place. For a layout replace only its JSON file; for a mod replace its directory. Never
  write live files one by one or overwrite an existing backup. Staging and backup are dot-prefixed
  siblings in the same parent directory as the asset, so each rename stays on one filesystem and
  the PRD 00156 inventory ignores them; count their bytes against the PRD 00158 budget. Fsync
  appropriate files/directories at durability boundaries. The library `atomic_write_*` helpers do
  not fsync the parent directory: journal and ledger publication use a helper local to
  `sysup/herdr/` (temporary file, fsync file, `os.replace`, fsync directory) with injectable rename
  and fsync, so tests can interrupt each boundary. Publish new accepted provenance only after installed bytes verify
  against reviewed digest. Journal recovery chooses forward completion only when installed/new and
  required inputs match; otherwise restore verified old bytes/provenance. Unexpected edits or
  ambiguous filesystem state stop for manual recovery. Recovery is idempotent; no deletion of the
  only valid copy. Retain complete rollback bytes and old provenance as pinned store references.
  Explicit rollback requires live digest equal to applied digest, restores old bytes/provenance
  through the same journal, and refuses subsequent edits. No force-overwrite option in v1. Report
  that Herdr may observe a brief missing path during directory renames; do not claim atomic
  cross-application replacement.

### Capability: Workflow and audit integration
Keep unresolved work visible without using metadata edits to silence it.

#### Feature: Shared commands and meaningful audit
- **Description**: Expose sysup herdr port prepare, review, validate, apply, recover and rollback
  through CommandHerdr.
- **Inputs**: Explicit operation IDs/digests; existing attention/audit lifecycle.
- **Outputs**: CommandResult and updated read-only audit findings.
- **Behavior**: All interfaces call the same services. No automatic agent launch or application from
  normal sysup. Extend PRD 00156 audit to consult accepted baseline records without executing code.
  The audit finds the store from the resolved Herdr home and XDG_STATE_HOME only; it needs no budget
  or config context and works whether or not PRD 00159 is done. Rule:
  suppress a raw version-only mismatch only when current source content matches accepted source and
  live clone content matches its last reviewed/applied digest. Otherwise retain the warning and
  describe accepted baseline separately. Missing/corrupt ledger inputs must not produce all-clear.
  Unresolved ancestry remains visible without an accepted record. Preserve hmod ownership and
  existing mixed-result attention behavior.

## Structural Decomposition

### Repository Structure

```text
src/tools/sysup/herdr/port.py                   # prepare/review/validation services
src/tools/sysup/herdr/apply.py                  # journal/apply/recover/rollback
src/tools/sysup/herdr/store.py                  # extend references from 00158
src/tools/sysup/commands/herdr.py               # extend shared facade from 00157
src/tools/sysup/capabilities/herdr.py           # extend audit from 00156
src/tools/sysup/cli.py                          # lazy port command adapters
tests/tools/sysup/test_herdr_port.py            # tree merges and review records
tests/tools/sysup/test_herdr_apply.py           # interruption/recovery matrix
tests/tools/sysup/test_herdr_commands.py        # shared facade/CLI parity
tests/tools/sysup/test_herdr.py                 # accepted-baseline audit
docs/source/tools/sysup.rst                     # ordered attended workflow
CHANGELOG.md                                   # unreleased entry
```

### Module: Port preparation
- **Maps to capability**: Attended candidate preparation
- **Responsibility**: Produce confined candidates and digest-bound review/validation.
- **Exports**: HerdrPortService.
- New symbols: `HerdrPortService`, `src/tools/sysup/herdr/port.py`, `tests/tools/sysup/test_herdr_port.py`.

### Module: Application
- **Maps to capability**: Recoverable application
- **Responsibility**: Journal safe replacement, provenance, recovery and rollback.
- **Exports**: HerdrApplyService.
- New symbols: `HerdrApplyService`, `src/tools/sysup/herdr/apply.py`, `tests/tools/sysup/test_herdr_apply.py`.

### Module: Workflow adapters
- **Maps to capability**: Workflow and audit integration
- **Responsibility**: Share operations and explain accepted baselines in audit.
- **Exports**: Existing CommandHerdr and HerdrCloneAudit from prerequisite PRDs.
- New symbols: `src/tools/sysup/herdr/store.py`, `src/tools/sysup/commands/herdr.py`, `src/tools/sysup/capabilities/herdr.py`, `tests/tools/sysup/test_herdr_commands.py`, `tests/tools/sysup/test_herdr.py` (created by prerequisite PRDs).

## Dependency Graph

### Foundation Layer (Phase 0)
- **Port preparation**: Depends on [PRD 00158 store/lock/baseline, PRD 00157 facade].

### Core Layer (Phase 1)
- **Application**: Depends on [Port preparation, PRD 00158 references].

### Integration Layer (Phase 2)
- **Workflow adapters**: Depends on [Application, Port preparation, PRD 00156 audit].

## Implementation Phases

### Phase 0: Foundation
**Goal**: Prepare reviewable output without touching live clones.

**Tasks**:
- [ ] Implement comparison transformations and three-way workspace preparation (depends on: PRDs 00157, 00158). Acceptance: `uv run pytest tests/tools/sysup/test_herdr_port.py` covers mod/layout transformations, additions/deletions, binary and delete/edit conflicts, missing ancestry and byte-identical live inputs.
- [ ] Implement review, static validation and external-attestation records (depends on: previous task). Acceptance: the same focused tests reject changed candidates, incomplete conflict resolution, altered immutable inputs and absent/wrong-digest evidence; no executable candidate code runs.

**Exit Criteria**: Every applicable candidate has exact reviewed and validated content.

### Phase 1: Core
**Goal**: Make every replacement boundary recoverable.

**Tasks**:
- [ ] Implement staged apply, durable journal, provenance commit and rollback (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/sysup/test_herdr_apply.py` injects exceptions/interruption before and after every rename, fsync and ledger publication; recovery preserves one verified complete version and rollback refuses later edits.

**Exit Criteria**: No partial installation is marked accepted; recovery is idempotent.

### Phase 2: Integration
**Goal**: Expose the attended workflow and keep audit honest.

**Tasks**:
- [ ] Extend facade/CLI and read-only audit (depends on: Phase 1, PRD 00156). Acceptance: `uv run pytest tests/tools/sysup/test_herdr_commands.py tests/tools/sysup/test_herdr.py` proves parity, explicit mutation gates and baseline-aware warnings.
- [ ] Document prepare → isolated validation → review → apply → optional rollback in safe execution order; include unknown-ancestry adoption and external-editor limits; add changelog (depends on: previous task). Acceptance: `uv run sphinx-build -b html docs/source docs/build/html` succeeds.

**Exit Criteria**: `uv run pytest` and `uv run mypy src/lib/ src/tools/` pass with normal platform snapshot skips; no human or live Herdr is required during implementation tests.

## Test Strategy

### Critical Scenarios
- **Happy path**: Accepted old source, new source and unchanged live input → reviewable candidate, explicit verified application, accepted new baseline.
- **Integrity**: Unknown ancestry, wrong home/source, conflicts, changed inputs or missing attestations → refusal without live changes.
- **Recovery**: Kill/failure at each journal boundary → complete verified old/new state or explicit unresolved recovery; never false success.
- **Rollback**: Untouched applied clone → old content/provenance restored; later user edit → refusal.
- **Audit**: Accepted unchanged content avoids version-only noise; changed source/clone or corrupt record retains attention.

## Risks

- **External validation trust**: Operator attestations are explicit trust inputs; sysup cannot prove another process was isolated or visually correct.
- **Renaming behavior**: Pin transformation fixtures to inspected Herdr behavior; changed upstream semantics require review rather than guessed rewrites.
- **Hand-written merge**: A custom diff3 is a defect source. Reuse `git merge-file -p --diff3 LOCAL OLD NEW` without a shell; add no new dependency (no merge library is installed). Missing git fails preparation with a diagnostic.
- **Shared test files**: `test_herdr_commands.py` and `test_herdr.py` already hold the tests of PRDs 00156 to 00158. A file that nears 800 lines may be split into siblings (for example `test_herdr_port_commands.py`); the acceptance command then names each file.
- **Concurrent/live reload**: The home lock coordinates sysup only; stop editors during apply and document the brief rename gap.
