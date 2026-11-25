---
design: skip
model_tier_rationale: docs-only change, one exact sentence appended to one CHANGELOG entry, checked by rg
---
# `bim serve` under `nohup` no longer stops on SIGHUP, and the changelog does not say so

Source: agoge run 2026-11-23, finding 17 of 21 (LOW, confirmed, lane wendy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

The new signal handler in `src/tools/bim/commands/serve/serve.py` leaves an ignored SIGHUP ignored. That is the right behaviour. But it is a change: before, a server started under `nohup` died on SIGHUP. Now it keeps running. `CHANGELOG.md` does not say so.

If unchanged, someone who stopped a nohup'd server with SIGHUP finds it still running, with no note that explains why. The case is rare.

## Solution

Extend the existing `bim serve` SIGHUP entry in `CHANGELOG.md`, under `## [Unreleased]`, `### Fixed`. Do not add a new entry. Do not change code.

The entry's current text:

```
- **bim serve**: remove the private token file when the server stops on SIGTERM or SIGHUP, not only on Ctrl-C; SIGHUP shuts down gracefully like SIGTERM, without a traceback, on loopback binds too.
```

Append this exact sentence to the end of that entry, on the same line, after one space:

```
A server started under `nohup` (SIGHUP ignored) keeps running on SIGHUP.
```

The entry's new text:

```
- **bim serve**: remove the private token file when the server stops on SIGTERM or SIGHUP, not only on Ctrl-C; SIGHUP shuts down gracefully like SIGTERM, without a traceback, on loopback binds too. A server started under `nohup` (SIGHUP ignored) keeps running on SIGHUP.
```

## Requirements

### Must have
- The `bim serve` SIGHUP entry in `CHANGELOG.md` `[Unreleased]` ends with the new sentence.
- The entry stays one line. No second `bim serve` SIGHUP entry is added.
- The CHANGELOG edit is the change itself. No other CHANGELOG line.

### Nice to have
- None.

## Implementation

### Module: changelog
- **Location**: `CHANGELOG.md`
- **Responsibility**: record that a server with SIGHUP ignored keeps running on SIGHUP.
- **Exports**: none
- **Risk**: low. `docs/source/tools/bim.rst` does not get the same note, because that option was not chosen. If the entry moves out of `[Unreleased]` in a release before this lands, edit it where it then lives.

### Dependencies
- changelog: No dependencies (foundation)

## Test Strategy

This is a docs-only change. It needs no test. The `rg` checks in the tasks replace the template's test tasks.

The finding's evidence, verbatim:

```
**Evidence** (confirmed, A/B). With `trap '' HUP` before `exec`, `-H 0.0.0.0`: at `669b74b6`
`kill -HUP` -> the server died, exit 143; at HEAD -> still alive, SIGTERM then stops it cleanly.
```

## Tasks

### Phase 0: Fix
- [ ] Append the sentence ``A server started under `nohup` (SIGHUP ignored) keeps running on SIGHUP.`` to the `bim serve` SIGHUP entry in `CHANGELOG.md` - Acceptance: `rg -c 'bim serve\*\*: remove the private token file.*on loopback binds too\. A server started under .nohup. \(SIGHUP ignored\) keeps running on SIGHUP\.$' CHANGELOG.md` prints `1`.
- [ ] Confirm the sentence appears once only (depends on: previous task) - Acceptance: `rg -c -F '(SIGHUP ignored) keeps running on SIGHUP.' CHANGELOG.md` prints `1`.

## Success Criteria

- `rg -c 'bim serve\*\*: remove the private token file.*on loopback binds too\. A server started under .nohup. \(SIGHUP ignored\) keeps running on SIGHUP\.$' CHANGELOG.md` prints `1`; the project's full test gate passes.
