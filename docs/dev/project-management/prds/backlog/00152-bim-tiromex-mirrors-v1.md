---
design: run
default_model: opus
model_tier_rationale: cross-cutting shape change and recoverable writes across vault and mirror repositories
eligibility: test -f docs/dev/project-management/prds/done/00151-bim-tiromex-backends-v1.md && git merge-base --is-ancestor 86b758d90b0ab92c295c3cc8d606bb659ca25d11 master && git merge-base --is-ancestor 86b758d90b0ab92c295c3cc8d606bb659ca25d11 HEAD
---

# bim mirror roots and article migration

Source: [Discovery 00149](docs/dev/project-management/intake/processed/00149-merge-klyreon-into-bim/discovery.md); adjacent port-plan.md supplies the approved inventory. Discovery overrides older examples. Part 3 of 6; explicit discovery numbering is retained.

Grounding: `archive_path` at `src/tools/bim/shared/article_archive.py:18-20` defines dated naming; `CommandCreateNote` at `src/tools/bim/commands/create_note/create_note.py:43-75` owns the shared creation seam.

## Overview

### Problem Statement
Move article originals into the owner's named mirror while keeping exporter-owned content read-only. Covers M9 and M13–M17. Requires 00150–00151 landed and reviewed machine-local loader PRD 00122 merged into master and this checkout; do not build another config loader.

### Target Users
The vault owner and unattended agents using bim. Tests use scratch vaults and isolated HOME/XDG_STATE_HOME; never the private vault.

### Success Metrics
`uv run pytest tests/tools/bim/test_mirrors.py tests/tools/bim/test_migrate_articles.py tests/tools/bim/test_article_archive.py tests/tools/bim/test_create_note_vault.py` verifies resolution, exact-path commits, collision refusal, complete fixture migration and zero-write dry runs.

## Functional Decomposition

### Capability: Mirror resolution
#### Feature: Named host-local roots
- **Description**: Resolve stable mirror citations through bim configuration.
- **Inputs**: mirrors map keyed by stable root name, mirror_articles_root default git; machine-local root paths.
- **Outputs**: Resolved files or not on this host; missing-file warnings.
- **Behavior**: Use the existing loader from 00122: shared names/settings in buvis-bim.yaml, host paths under ~/.local/.config/buvis/buvis-bim.yaml. Reject traversal/absolute/symlink escapes inside a citation. Unconfigured or absent roots report exactly not on this host, not dangling; a missing file in a present root warns without making validation fail. Never rename root IDs. Source-dependent rules skip unavailable roots. Exporter-owned clippings/pocket/readwise/readwise-unofficial are read-only.
### Capability: Article storage cutover
#### Feature: Create into the git mirror
- **Description**: Store new article originals in the bim-owned articles subtree.
- **Inputs**: Existing article title/original/web and configured git mirror.
- **Outputs**: Original file and summary with article:: mirror:<root>/<path>.
- **Behavior**: Keep archive_file_name sanitization and articles/<YYYY>/<YYYYMM>00/<title>.md naming. Require the selected root to be a git work tree; exclusive/no-overwrite atomic persistence; one exact-original-path commit under bim identity, no push and no global git config. CLI/TUI/serve use the same creation command. Retire path_articles from normal creation; preserve access to its old value only for migration/compatibility diagnostics (guess), so existing configs can reach migration instead of failing at load.
#### Feature: Migrate originals and links
- **Description**: Move old originals and repoint only article backmatter lines.
- **Inputs**: Legacy path_articles value or explicit legacy root, scratch old archive and vault, --dry-run.
- **Outputs**: Moved originals, mirror citations, per-file skip report and scoped commits.
- **Behavior**: Premise: each source still belongs to the legacy article archive and each destination is absent. Recheck per source at execution; failed premise means skip and report. Never overwrite; do not change exporter files or unrelated note bytes. Report existing destinations, unreadable sources and unmatched references. Plan first; dry run creates no files, directories, locks, state or commits. Stage/recover the migration across its two repositories: commit exact mirror destinations and exact changed vault notes separately, at most one scoped migration commit per repository (guess); no cross-repository atomic-commit claim. Retain/recover originals on failure; rerun safely without duplication. Do not execute migration against the owner's real vault during implementation.

## Structural Decomposition

### Repository Structure
```text
src/tools/bim/shared/mirrors.py             # resolution
src/tools/bim/shared/article_archive.py      # original storage
src/tools/bim/commands/migrate_articles/     # migration command
src/tools/bim/                              # caller cutover, exact paths below
tests/tools/bim/                            # fixture and adapter tests
CHANGELOG.md
docs/source/tools/bim.rst
src/tools/bim/SKILL.md
src/tools/bim/cli.py
src/tools/bim/commands/create_note/create_note.py
src/tools/bim/commands/serve/_actions.py
src/tools/bim/commands/serve/_app.py
src/tools/bim/commands/serve/_security.py
src/tools/bim/commands/serve/serve.py
src/tools/bim/commands/tx/validate.py
src/tools/bim/dependencies.py
src/tools/bim/manifest.toml
src/tools/bim/note_write_cli.py
src/tools/bim/params/serve.py
src/tools/bim/serve_cli.py
src/tools/bim/settings.py
src/tools/bim/tui/create_note.py
```

### Module: Mirror resolver
- **Maps to capability**: Mirror resolution
- **Location**: `src/tools/bim/shared/mirrors.py`, `tests/tools/bim/test_mirrors.py`
- **Responsibility**: Stable root resolution, confinement and availability diagnostics.
- **Exports**: Stable root resolution, confinement and availability diagnostics.
New symbols: `src/tools/bim/shared/mirrors.py`, `tests/tools/bim/test_mirrors.py`
### Module: Article storage and migration
- **Maps to capability**: Article storage cutover
- **Location**: `src/tools/bim/commands/migrate_articles/__init__.py`, `src/tools/bim/commands/migrate_articles/migrate_articles.py`, `tests/tools/bim/test_mirrors.py`, `tests/tools/bim/test_migrate_articles.py`, `src/tools/bim/settings.py`, `src/tools/bim/cli.py`, `src/tools/bim/dependencies.py`, `src/tools/bim/note_write_cli.py`, `src/tools/bim/serve_cli.py`, `src/tools/bim/shared/article_archive.py`, `src/tools/bim/commands/create_note/create_note.py`, `src/tools/bim/tui/create_note.py`, `src/tools/bim/params/serve.py`, `src/tools/bim/commands/serve/serve.py`, `src/tools/bim/commands/serve/_app.py`, `src/tools/bim/commands/serve/_security.py`, `src/tools/bim/commands/serve/_actions.py`, `src/tools/bim/commands/tx/validate.py`, `tests/tools/bim/test_settings.py`, `tests/tools/bim/test_article_archive.py`, `tests/tools/bim/test_create_note_vault.py`, `tests/tools/bim/test_create_note_cli_wiring.py`, `tests/tools/bim/test_note_write_cli.py`, `tests/tools/bim/test_bim_cli_handlers.py`, `tests/tools/bim/test_create_edit_round_trip.py`, `tests/tools/bim/create_note_helpers.py`, `tests/tools/bim/tui/test_create_note.py`, `tests/tools/bim/test_serve_app.py`, `tests/tools/bim/test_serve_actions.py`
- **Responsibility**: Shared article creation and CommandResult migration with recoverable persistence.
- **Exports**: Shared article creation and CommandResult migration with recoverable persistence.
New symbols: `src/tools/bim/commands/migrate_articles/__init__.py`, `src/tools/bim/commands/migrate_articles/migrate_articles.py`, `tests/tools/bim/test_mirrors.py`, `tests/tools/bim/test_migrate_articles.py`
### Module: Operator documentation
- **Maps to capability**: Article storage cutover
- **Location**: `src/tools/bim/SKILL.md`, `src/tools/bim/manifest.toml`, `docs/source/tools/bim.rst`, `CHANGELOG.md`
- **Responsibility**: Configuration cutover, migration CLI usage and exporter ownership rules.
- **Exports**: Configuration cutover, migration CLI usage and exporter ownership rules.

## Dependency Graph

### Foundation Layer (Phase 0)
- **Mirror resolver**: Depends on external PRD 00122 machine-local loader; no new internal dependencies. Eligibility verifies its reviewed commit is an ancestor of master and HEAD.

### Core Layer (Phase 1)
- **Article storage and migration**: Depends on [Mirror resolver]; existing creation behavior is the compatibility baseline.

### Integration Layer (Phase 2)
- **Operator documentation**: Depends on [Article storage and migration]. Port order requires 00150 and 00151 complete.

## Implementation Phases

### Phase 0: Foundation
**Goal**: Resolve mirrored sources safely.

**Tasks**:
- [ ] Add named settings, host-local resolution and tx validation diagnostics (depends on: 00122 and 00150). Acceptance: `uv run pytest tests/tools/bim/test_mirrors.py` covers per-key overrides, absent roots, missing files and all escape forms.

**Exit Criteria**: Resolution tests pass against the existing loader, with no loader implementation duplicated.

### Phase 1: Core
**Goal**: Move article writes and implement safe migration.

**Tasks**:
- [ ] Cut article creation over through every existing caller (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/bim/test_article_archive.py tests/tools/bim/test_create_note_vault.py tests/tools/bim/test_create_note_cli_wiring.py tests/tools/bim/test_note_write_cli.py tests/tools/bim/tui/test_create_note.py tests/tools/bim/test_serve_actions.py` checks exact git paths and mirror citations.
- [ ] Add migration command and fixtures (depends on: article creation). Acceptance: `uv run pytest tests/tools/bim/test_migrate_articles.py` checks all originals/links, per-file premise recheck and skip/report, collision/rerun/failure recovery and full filesystem snapshots for dry-run.

**Exit Criteria**: Scratch migration preserves original content, touches only article links, and succeeds on rerun.

### Phase 2: Integration
**Goal**: Document and verify integration.

**Tasks**:
- [ ] Wire migration through composition/CLI and shared actions, update skill/docs/manifest/changelog, and adapt legacy test fixtures without removing assertions (depends on: Phase 1). Acceptance: `uv run pytest tests/tools/bim/test_migrate_articles.py tests/tools/bim/test_settings.py tests/tools/bim/test_bim_cli_handlers.py tests/tools/bim/test_create_edit_round_trip.py tests/tools/bim/test_serve_app.py` covers legacy config reachability and interface wiring.

**Exit Criteria**: `uv run pytest` and `uv run mypy src/lib/ src/tools/` pass once at closeout.

## Test Strategy

### Critical Scenarios
- **Happy path**: old originals and article links migrate with no content loss; new articles use the same naming.
- **Edge case**: one root absent on this host is informational; one missing file in a present root warns.
- **Error case**: collision, dirty affected note, ENOSPC or second repository commit failure preserves recoverable originals and unrelated content.
- **Integration**: seed unrelated staged changes in both git repos and assert they never enter commits; hash exporter trees before/after.

## Risks

- **Two repositories**: scoped commits cannot be atomic together; failure/retry tests must prove recoverability and truthful reporting.
- **Premise drift**: test execution-time checks, not only plan-time snapshots. If the prerequisite loader/legacy layout premise fails, skip and report rather than force.
- **Legacy config retirement**: a temporary migration-only alias is acceptable; never silently resume writes to path_articles.
- **Invented CLI spelling**: migration's exact subcommand/options beyond --dry-run remain internal design choices; do not invent a second storage contract.
