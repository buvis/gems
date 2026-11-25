---
design: skip
model_tier_rationale: docs-only change, two tokens replaced with exact text, checked by rg
---
# The docs still show an env variable form that does nothing

Source: agoge run 2026-11-23, finding 16 of 21 (LOW, confirmed, lane wendy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

Two MYAPP examples in `docs/source/configuration.rst` keep the old nested env form `BUVIS_MYAPP__DB__HOST`. The same form was already fixed for the PHOTO examples. The variable has no effect: `db.host` stays `localhost`. One of the two examples is a documented test, and that test would fail as written.

If unchanged, a reader copies a variable that does nothing. The problem is stable. It does not get worse.

## Solution

Change both occurrences of `BUVIS_MYAPP__DB__HOST` in `docs/source/configuration.rst` to `BUVIS_MYAPP_DB__HOST`. The prefix `BUVIS_MYAPP_` joins the field name `DB` directly. The double underscore stays only between `DB` and `HOST`.

The two occurrences are:

1. A comment in the nested-settings code block. Current text: `# BUVIS_MYAPP__DB__HOST=prod.db.local  (double underscore!)`. New text: `# BUVIS_MYAPP_DB__HOST=prod.db.local  (double underscore!)`.
2. A test example. Current text: `monkeypatch.setenv("BUVIS_MYAPP__DB__HOST", "env-db")`. New text: `monkeypatch.setenv("BUVIS_MYAPP_DB__HOST", "env-db")`.

Change nothing else in the file.

## Requirements

### Must have
- `BUVIS_MYAPP__DB__HOST` is absent from `docs/source` and `README.md`.
- `BUVIS_MYAPP_DB__HOST` is present twice in `docs/source/configuration.rst`.
- No CHANGELOG line. This is a docs-only change.

### Nice to have
- None.

## Implementation

### Module: config docs
- **Location**: `docs/source/configuration.rst`
- **Responsibility**: show the nested env variable form that the resolver reads.
- **Exports**: none
- New symbols: `BUVIS_MYAPP_DB__HOST`
- **Risk**: low. The text `(double underscore!)` in the comment still fits, because the DB and HOST parts keep their double underscore. A docs test that runs the examples was offered and not chosen, so the same drift can return.

### Dependencies
- config docs: No dependencies (foundation)

## Test Strategy

This is a docs-only change. It needs no test. The `rg` checks in the tasks replace the template's test tasks.

The finding's evidence, verbatim:

```
**Evidence** (confirmed, the doc's own settings class run through the resolver).
`BUVIS_MYAPP__DB__HOST` -> `db.host` stays `localhost`; `BUVIS_MYAPP_DB__HOST` -> `env-db`. The
documented test at line 728 would fail.
```

## Tasks

### Phase 0: Fix
- [x] Replace both `BUVIS_MYAPP__DB__HOST` occurrences in `docs/source/configuration.rst` with `BUVIS_MYAPP_DB__HOST` - Acceptance: `rg -F "BUVIS_MYAPP__DB__HOST" docs/source README.md` prints nothing and exits 1.
- [x] Confirm the new form is in both places (depends on: previous task) - Acceptance: `rg -c -F "BUVIS_MYAPP_DB__HOST" docs/source/configuration.rst` prints `2`.

## Success Criteria

- `rg -F "BUVIS_MYAPP__DB__HOST" docs/source README.md` prints nothing; `rg -c -F "BUVIS_MYAPP_DB__HOST" docs/source/configuration.rst` prints `2`; the project's full test gate passes.
