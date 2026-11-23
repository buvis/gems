---
design: skip
model_tier_rationale: docs-only change, one sentence replaced with exact text, checked by rg
---
# `bim.rst` still says a failed command exits 0 "matching the rest of the bim CLI"

Source: agoge run 2026-11-23, finding 21 of 21 (LOW, confirmed, lane wendy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

A sentence in `docs/source/tools/bim.rst` describes the exit codes from before the console exit-code change. It sits in the `--strict` option of `bim doc ingest`. It says a failure exits 0 by default and that this matches the rest of the bim CLI. Neither part is true now. The rest of the bim CLI exits 1 on failure. `bim doc ingest` exits 1 without `--strict` when it fails before the pipeline starts.

If unchanged, script authors read a rule that is no longer true. The problem is stable.

## Solution

In `docs/source/tools/bim.rst`, in the `--strict` bullet under the `bim doc ingest` options, replace this sentence (it wraps over two lines in the file):

```
Default exit code is 0 even on ``success=False``, matching the rest of the bim CLI.
```

with this exact text:

```
Without it, a pipeline failure exits 0. A failure before the pipeline starts exits 1 with or without this flag: a missing file, a missing ``doc`` config section, an unreachable model server, or a bad ``issuers.yml``.
```

Keep the text before it (the bullet's first sentence, which ends `(for scripting).`) and the text after it (`Triaged and duplicate outcomes are not failures and remain exit 0 regardless of this flag.`). Re-wrap the bullet to the file's line width with the two-space continuation indent. Change nothing else in the file.

The wording agrees with the `console` entry in `CHANGELOG.md` `[Unreleased]`, which says: "`ingest` and `promote` exit non-zero only with `--strict`" for pipeline failures, and "A failure before the pipeline starts (a missing file, a missing `doc` config section, an unreachable model server) exits non-zero." The docs add the bad `issuers.yml` case by the operator's decision. Do not edit the CHANGELOG.

## Requirements

### Must have
- The phrase `matching the rest of the bim CLI` is absent from `docs/source/tools/bim.rst`.
- The `bim doc ingest` `--strict` bullet says a pipeline failure exits 0 without `--strict`.
- The same bullet says a failure before the pipeline starts exits 1 with or without the flag, and names the four cases: missing file, missing `doc` config section, unreachable model server, bad `issuers.yml`.
- No CHANGELOG line. This is a docs-only change.

### Nice to have
- None.

## Implementation

### Module: bim docs
- **Location**: `docs/source/tools/bim.rst`
- **Responsibility**: state the current exit-code rule for `bim doc ingest`.
- **Exports**: none
- **Risk**: low. The `bim doc promote` `--strict` bullet in the same file has a sibling sentence ("Default exit code is 0 on failure to match the rest of the bim CLI."). The finding does not cover it, so this PRD leaves it. The bad `issuers.yml` case comes from the operator's decision. The report's evidence shows the missing-file and unreachable-server cases only. Moving all exit-code rules to one docs section was offered and not chosen.

### Dependencies
- bim docs: No dependencies (foundation)

## Test Strategy

This is a docs-only change. It needs no test. The `rg` checks in the tasks replace the template's test tasks. The checks use `rg -U` with `\s+` between words, so they pass however the bullet is wrapped.

The finding's evidence, verbatim:

```
**Evidence** (confirmed). The text: "Default exit code is 0 even on `success=False`, matching the
rest of the bim CLI." Observed: `bim show missing-a.md` rc 1; `bim doc ingest <missing>.pdf` rc 1
without `--strict`; unreachable model server rc 1.
```

## Tasks

### Phase 0: Fix
- [ ] Replace the stale sentence in the `bim doc ingest` `--strict` bullet of `docs/source/tools/bim.rst` with the exact text from Solution - Acceptance: `rg -U 'matching\s+the\s+rest\s+of\s+the\s+bim\s+CLI' docs/source/tools/bim.rst` prints nothing and exits 1.
- [ ] Confirm the pipeline rule is present (depends on: previous task) - Acceptance: `rg -U -c 'Without\s+it,\s+a\s+pipeline\s+failure\s+exits\s+0\.\s+A\s+failure\s+before\s+the\s+pipeline\s+starts\s+exits\s+1\s+with\s+or\s+without\s+this\s+flag:' docs/source/tools/bim.rst` prints `1`.
- [ ] Confirm the four pre-pipeline cases are named (depends on: previous task) - Acceptance: `rg -U -c 'a\s+missing\s+file,\s+a\s+missing\s+``doc``\s+config\s+section,\s+an\s+unreachable\s+model\s+server,\s+or\s+a\s+bad\s+``issuers\.yml``\.' docs/source/tools/bim.rst` prints `1`.

## Success Criteria

- `rg -U 'matching\s+the\s+rest\s+of\s+the\s+bim\s+CLI' docs/source/tools/bim.rst` prints nothing; the two `rg -U -c` checks above each print `1`; the project's full test gate passes.
