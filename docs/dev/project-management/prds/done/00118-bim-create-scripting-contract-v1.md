---
default_model: opus
model_tier_rationale: id allocation under concurrency and a JSON contract another repo's skill consumes; the exact expressions are not all given
---

# bim create: scripting contract for agents

Source: conversation assessment of 2026-11-08 comparing `bim create` (buvis-gems 0.18.1) with the `create-note` skill's `create_note.py` in buvis/agent-skills; the user skipped a discovery doc. First of three PRDs (00118 contract, 00119 vault templates, 00120 vault links) that let `bim create` replace that script, so the skill can shrink to `bim --skill` plus a thin wrapper.

## Execution prerequisite

Run first. The 2026-11-09 scope reconciliation is recorded in `../../autopilot/reports/00118-00120-unblock-20261109.md`.

## Overview

### Problem Statement
An agent cannot drive `bim create` reliably. Measured on 2026-11-08 against a scratch zettelkasten:

- `set_default_id` derives the id in UTC while `date` is rendered in local time, so `date: 2026-11-08T13:49:25+01:00` got `id: 20261108124925`. Every Templater-made note in the vault uses local time, so bim notes sort an hour off their neighbours and their filename disagrees with their date.
- `bim create -t nonexistent --title X` and a same-second second create both print a failure and exit 0. Success is a Rich line wrapped at terminal width. There is no machine-readable result.
- A same-second collision fails instead of waiting for the next free id.
- There is no way to pass a body: the note holds only the template's sections. There is no dry run. An inbox file cannot be the source.
- `--tags "#Person, two words"` is accepted verbatim.

### Target Users
Coding agents and scripts that create notes through `bim`, and the `create-note` skill that will call `bim create` instead of shipping its own writer.

### Success Metrics
- `uv run pytest tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py tests/lib/zettel/entities/zettel/fixers/test_set_default_date.py tests/lib/zettel/application/test_create_zettel_use_case.py tests/tools/bim/test_create_note.py tests/tools/bim/test_note_write_cli.py tests/tools/bim/test_bim_cli_handlers.py -q` passes with the new cases.
- Against a scratch `BUVIS_BIM_PATH_ZETTELKASTEN`: `bim create -t note --title probe --json` prints one JSON object whose `id` equals the local-time `date` digits; `bim create -t nonexistent --title X` exits 1; two creates in the same second produce two files.

## Functional Decomposition

### Capability: Local-time identity
Ids and dates agree with the vault's Templater convention.

#### Feature: Date defaults to local time
- **Description**: `set_default_date` stamps a timezone-aware local time instead of UTC.
- **Inputs**: `ZettelData` without `date`.
- **Outputs**: `metadata["date"] = datetime.now().astimezone().replace(microsecond=0)`.
- **Behavior**: An existing `date` is kept. The instant is unchanged from today, only the offset differs, so `test_zettel_consistency_service.py`'s equality against `datetime.now(timezone.utc)` still holds.

#### Feature: Id follows the date's own offset
- **Description**: `set_default_id` formats the date as it is, with no conversion to UTC.
- **Inputs**: `metadata["date"]`, an aware or naive datetime.
- **Outputs**: `metadata["id"] = int(date.strftime("%Y%m%d%H%M%S"))`.
- **Behavior**: `2024-09-13T12:00:00+02:00` gives `20240913120000`; the same instant written as `10:00:00Z` gives `20240913100000`. A non-datetime still raises `ValueError("Invalid date format")`.

### Capability: Safe id allocation
Two creates never share a file, and a same-second clash waits instead of failing.

#### Feature: Prepare without writing
- **Description**: `CreateZettelUseCase.prepare` builds the zettel, runs the fixers and returns the target path and zettel without touching disk.
- **Inputs**: template, answers.
- **Outputs**: `tuple[Path, Zettel]`; the path is `zettelkasten_path / f"{zettel.id}.md"`.
- **Behavior**: When the path exists, sleep one second and rebuild (a rebuild re-reads the clock, so the id moves on), up to `MAX_ID_ATTEMPTS = 5` tries, then raise `FileExistsError` with today's message. No origin check: a template that pins its own date simply exhausts the budget and fails.

#### Feature: Exclusive reservation
- **Description**: `execute` reserves the path with `os.open(path, O_CREAT | O_EXCL)` before `writer.save`, so two processes that passed `prepare` in the same second cannot both write it.
- **Inputs**: result of `prepare`.
- **Outputs**: the saved path, as today.
- **Behavior**: A reservation that fails with `FileExistsError` counts as a collision: re-run `prepare` within the same `MAX_ID_ATTEMPTS` budget. Hooks run after the save, as today (00119 moves them). The returned type stays `Path`, so `CommandCreateNote`, `tui/create_note.py` and `serve/_actions.py` keep working.

### Capability: Scriptable create command
`bim create` takes a body, validates tags, can dry-run, and reports in JSON with real exit codes.

#### Feature: Tag validation
- **Description**: `CommandCreateNote.execute` normalises and validates `params.tags` before the template sees them.
- **Inputs**: comma-separated `tags`.
- **Outputs**: `answers["tags"]` as a comma-joined list of cleaned tags, or `CommandResult(success=False, error=...)`.
- **Behavior**: Each item is stripped, a leading `#` removed, lowercased; empty items are dropped; duplicates keep the first occurrence. An item that does not match `[\w-]+(/[\w-]+)*`, or that matches `[\d/]+`, fails with `invalid tag '<item>': use letters, digits, '-', '_', and '/' for nesting`.

#### Feature: Body and source input
- **Description**: `--body-file PATH` (`-` for stdin) or `--source PATH` supplies the note body; the two are mutually exclusive.
- **Inputs**: `CreateNoteParams.body: str | None`, `CreateNoteParams.source: Path | None`.
- **Outputs**: body text placed in one template section; with `--source`, the source file moved to `<vault_root>/.trash/`.
- **Behavior**: `vault_root` is `path_zettelkasten.parent`, the same derivation `_create_project_dir` uses. `CreateZettelUseCase.prepare` and `execute` take a keyword-only `body: str | None = None` (existing callers unchanged); after `build_data` they append it, normalised (`\r\n` to `\n`, leading blank lines and trailing whitespace removed), to the body of the section whose heading equals `getattr(template, "body_section", None)`, else the first section (the `# Title` heading). `--source` must be an existing `.md` file under `<vault_root>/inbox/`, else failure `--source must be a Markdown file inside <vault_root>/inbox`; a leading frontmatter block (`\A---\n[\s\S]*?\n---\n`) is stripped; when `--title` is omitted the file stem is the title, so `-t` plus `--source` is enough to run non-interactively. After a successful save the source moves to `<vault_root>/.trash/<name>`, adding ` 1`, ` 2`, ... before the suffix on a name clash; a failed move is reported in `metadata["errors"]`, not raised, because the note already exists.

#### Feature: Dry run
- **Description**: `--dry-run` renders the note and writes nothing.
- **Inputs**: `CreateNoteParams.dry_run: bool = False`; `CommandCreateNote` gains a `formatter: ZettelFormatter` dependency from `get_formatter`.
- **Outputs**: `metadata["content"]` holds the formatted note from `PrintZettelUseCase(self.formatter).execute(zettel.get_data())`; `metadata["dry_run"] = True`.
- **Behavior**: Calls `prepare` only; no reservation, no save, no hooks, no source move. Non-JSON output prints the content with `console.print(mode="raw")`.

#### Feature: Result metadata and JSON output
- **Description**: `CommandResult.metadata` carries everything a caller needs, and `--json` prints it as one object.
- **Inputs**: the saved or prepared zettel.
- **Outputs**: metadata keys `id` (str), `type`, `title`, `tags` (list), `path` (absolute str), `relative_path` (path relative to `vault_root`, for example `notes/20261108134925.md`), `wikilink` (`[[notes/20261108134925|Title]]`, the relative path without `.md`), plus `dry_run` and `content` on a dry run, `trashed_source` after a source move, `errors` (list) for post-save problems.
- **Behavior**: With `--json`, the CLI prints `json.dumps(metadata, ensure_ascii=False)` through `click.echo` and nothing else; on failure it prints `{"error": "<message>"}` and exits 1. `click.echo` is the sanctioned payload exception to the console rule, as for `dot filter`: Rich would wrap a long line. Without `--json`, output is unchanged (`Created <path>`).

#### Feature: Non-zero exit on failure
- **Description**: Every bim note command exits 1 when its `CommandResult.success` is false.
- **Inputs**: the `CommandResult` each handler already reports.
- **Outputs**: `ctx.exit(1)` after `console.report_result`.
- **Behavior**: Applies to `create_note`, `import_note`, `edit_note`, `archive_note`, `delete_note` in `src/tools/bim/note_write_cli.py` and `format_note`, `sync_note`, `show_note` in `src/tools/bim/note_read_cli.py`, and to `query` when neither `-Q` nor `-q` is given. Premise: the `success=False` handler tests in `tests/tools/bim/test_bim_cli_handlers.py` (7 at authoring) and `tests/tools/bim/test_note_read_cli.py` (1) assert `exit_code == 0` today; re-count with `rg -c "success=False"` at execution time and flip exactly those assertions to 1.

## Structural Decomposition

### Repository Structure

```
src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_date.py   # Maps to: Local-time identity
src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_id.py     # Maps to: Local-time identity
src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py     # Maps to: Safe id allocation
src/tools/bim/params/create_note.py                                             # Maps to: Scriptable create command
src/tools/bim/commands/create_note/create_note.py                               # Maps to: Scriptable create command
src/tools/bim/note_write_cli.py                                                 # Maps to: JSON output, exit codes
src/tools/bim/note_read_cli.py                                                  # Maps to: exit codes
src/tools/bim/commands/serve/_actions.py                                        # Maps to: formatter dependency
src/tools/bim/tui/create_note.py                                                # Maps to: formatter dependency
src/tools/bim/SKILL.md                                                          # Maps to: documentation
docs/source/tools/bim.rst                                                       # Maps to: documentation
CHANGELOG.md                                                                    # Maps to: documentation
README.md                                                                       # Maps to: scripting example
tests/lib/zettel/entities/zettel/test_zettel_consistency_service.py               # Maps to: preserve existing ids
tests/lib/zettel/entities/zettel/fixers/test_set_default_date.py
tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py
tests/lib/zettel/application/test_create_zettel_use_case.py
tests/tools/bim/test_create_note.py
tests/tools/bim/test_note_write_cli.py
tests/tools/bim/test_bim_cli_handlers.py
tests/tools/bim/test_note_read_cli.py
```

### Module: fixers
- **Maps to capability**: Local-time identity
- **Responsibility**: default `date` and `id` for a new zettel.
- **Location**: `src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_date.py`, `src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_id.py`
- **Exports**: `set_default_date`, `set_default_id` (signatures unchanged).
- New symbols: `id_keeps_the_dates_own_offset`, `date_defaults_to_local_offset`

### Module: create_zettel_use_case
- **Maps to capability**: Safe id allocation
- **Responsibility**: allocate a free id, reserve the path, save, run hooks.
- **Location**: `src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py`
- **Exports**: `CreateZettelUseCase.execute` (keyword-only `body` added), `CreateZettelUseCase.prepare`.
- New symbols: `prepare`, `MAX_ID_ATTEMPTS`, `waits_for_next_second_on_collision`, `gives_up_after_five_attempts`, `second_writer_loses_reservation_and_retries`

### Module: create_note command
- **Maps to capability**: Scriptable create command
- **Responsibility**: validate tags, read body or source, dry-run or create, build result metadata, trash the source.
- **Location**: `src/tools/bim/params/create_note.py`, `src/tools/bim/commands/create_note/create_note.py`
- **Exports**: `CreateNoteParams` (new fields `body`, `source`, `dry_run`), `CommandCreateNote` (new `formatter` constructor argument; `serve/_actions.py` and `tui/create_note.py` pass `get_formatter()`).
- New symbols: `wikilink`, `trashed_source`, `rejects_tag_with_hash_or_space`, `dedupes_tags_case_insensitively`, `source_outside_inbox_is_rejected`, `source_frontmatter_is_stripped_and_file_trashed`, `dry_run_writes_nothing_and_returns_content`, `metadata_has_relative_path_and_wikilink`

### Module: bim CLI handlers
- **Maps to capability**: Scriptable create command
- **Responsibility**: `--body-file`, `--source`, `--dry-run`, `--json` flags on `create`; exit 1 on failure in all note handlers.
- **Location**: `src/tools/bim/note_write_cli.py`, `src/tools/bim/note_read_cli.py`
- **Exports**: `register_note_write_commands`, `register_note_read_commands` (unchanged).
- New symbols: `json_prints_single_object_and_nothing_else`, `json_failure_prints_error_and_exits_1`, `create_failure_exits_1`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **fixers**: local-time `date`, offset-faithful `id`.
- **create_zettel_use_case**: `prepare`, collision wait, exclusive reservation.

### Core Layer (Phase 1)
- **create_note command**: depends on [create_zettel_use_case] for `prepare`.
- **bim CLI handlers**: depends on [create_note command] for the new params and metadata.

### Integration Layer (Phase 2)
- **docs**: depends on [bim CLI handlers].

## Implementation Phases

### Phase 0: Foundation
**Goal**: New notes get local-time ids and two creates never share a file.

**Tasks**:
- [ ] Change `set_default_date` to `datetime.now().astimezone().replace(microsecond=0)` and `set_default_id` to `int(date.strftime("%Y%m%d%H%M%S"))`; add tests `id_keeps_the_dates_own_offset` (`+02:00` noon gives `20240913120000`) and `date_defaults_to_local_offset` (`utcoffset()` equals `datetime.now().astimezone().utcoffset()`); verify in `test_zettel_consistency_service.py` that consistency preserves an existing UTC-derived id with a non-UTC date (no deps) - Acceptance: `uv run pytest tests/lib/zettel/entities/zettel/fixers tests/lib/zettel/entities/zettel/test_zettel_consistency_service.py -q` passes.
- [ ] Add `prepare` and the collision wait to `CreateZettelUseCase`, and the `O_EXCL` reservation to `execute`; tests `waits_for_next_second_on_collision` (patch `time.sleep`, pre-create the first path, assert the second id and one sleep), `gives_up_after_five_attempts`, `second_writer_loses_reservation_and_retries` (no deps) - Acceptance: `uv run pytest tests/lib/zettel/application/test_create_zettel_use_case.py -q` passes.

**Exit Criteria**: `uv run pytest tests/lib/zettel -q` passes.

### Phase 1: Core
**Goal**: `bim create` is scriptable.

**Tasks**:
- [ ] Extend `CreateNoteParams` and `CommandCreateNote` with tag validation, body/source handling, dry run, the `formatter` dependency and the metadata keys; update `serve/_actions.py` and `tui/create_note.py` constructor calls; tests `rejects_tag_with_hash_or_space`, `dedupes_tags_case_insensitively`, `source_outside_inbox_is_rejected`, `source_frontmatter_is_stripped_and_file_trashed`, `dry_run_writes_nothing_and_returns_content`, `metadata_has_relative_path_and_wikilink` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/bim/test_create_note.py -q` passes.
- [ ] Add `--body-file`, `--source`, `--dry-run`, `--json` to the `create` handler (mutual exclusion checked in the callback with `console.panic`), `--json` printing via `click.echo`, and `ctx.exit(1)` after a failed `report_result` in all eight note handlers plus `query` without a spec; flip the `success=False` tests named in the premise to `exit_code == 1`; tests `json_prints_single_object_and_nothing_else`, `json_failure_prints_error_and_exits_1`, `create_failure_exits_1` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/bim/test_note_write_cli.py tests/tools/bim/test_bim_cli_handlers.py tests/tools/bim/test_note_read_cli.py -q` passes.

**Exit Criteria**: against a scratch `BUVIS_BIM_PATH_ZETTELKASTEN`, `bim create -t note --title probe --tags "#A,a" --json` prints one object with `tags: ["a"]` and an `id` equal to the local-time digits of its `date`; `bim create -t nonexistent --title X; echo $?` prints 1.

### Phase 2: Integration
**Goal**: Documented for humans and agents.

**Tasks**:
- [ ] Document the four new flags and the exit code in the "bim create" section of `docs/source/tools/bim.rst`; rewrite the Create section of `src/tools/bim/SKILL.md` to recommend `--json` and `--dry-run`, drop the sentence about exit 0 and add the tag rules; add `Added` and `Changed` (`bim` exits 1 on failure; ids follow local time) lines under `[Unreleased]` in `CHANGELOG.md` prefixed `**bim**:`; add a scripting example to `README.md` (depends on: Phase 1) - Acceptance: `rg -c "\-\-json" docs/source/tools/bim.rst src/tools/bim/SKILL.md` prints at least 1 for each file and `rg -c "still exits 0" src/tools/bim/SKILL.md` prints 0.

**Exit Criteria**: `uv run pytest -q` passes; `uv run ruff check src tests` and `uv run mypy src/lib/ src/tools/` are clean.

## Test Strategy

### Critical Scenarios
- **Happy path**: `bim create -t note --title "Why caches lie" --tags "cache,debugging" --json` → Expected: one JSON object, file `<zettelkasten>/<id>.md` exists, `wikilink` is `[[notes/<id>|Why caches lie]]`, exit 0.
- **Happy path**: `--source inbox/draft.md` with frontmatter and no `--title` → Expected: title `Draft`, body without the frontmatter, `inbox/draft.md` moved to `.trash/draft.md`, `trashed_source` in metadata.
- **Edge case**: two creates within one second → Expected: second `prepare` sleeps once and takes the next id; both files exist.
- **Edge case**: `--dry-run` → Expected: no file, no `.trash` move, `content` starts with `---\n`.
- **Error case**: `--tags "two words"` → Expected: exit 1, message names the tag, no file written.
- **Error case**: `--body-file x --source y` together → Expected: exit 1 before any read.
- **Error case**: unknown template with `--json` → Expected: stdout is exactly `{"error": "Unknown template: nonexistent"}` and exit 1.

## Risks

- **DST fall-back hour**: local-time ids repeat one hour per year; the collision wait handles a clash the same way Templater users do by hand. Accepted.
- **Behaviour change for existing scripts**: exit 1 on failure and local-time ids are visible changes; both go under `Changed` in the changelog and bump the minor version at release.
- **TUI and WebUI parity**: `formatter` becomes a constructor argument, so both call sites change in the same task; `uv run pytest tests/tools/bim -q` guards them.
