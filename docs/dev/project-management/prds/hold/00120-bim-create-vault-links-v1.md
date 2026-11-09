---
default_model: opus
model_tier_rationale: contact-name matching is a heuristic with protected spans and ambiguity rules, and the article flow writes outside the vault with rollback
---

# bim create: vault links and the article workflow

Source: conversation assessment of 2026-11-08; third of three PRDs after 00118 (scripting contract) and 00119 (vault templates). Ports the last three behaviours of `create_note.py` and `vault_links.py` from the `create-note` skill in https://github.com/buvis/agent-skills (`skills/create-note/scripts/`); read both before implementing. When this lands, that skill shrinks to `bim --skill` plus a wrapper, which is a change in the other repository and not a task here.

## Execution prerequisite

Start only after PRDs 00118 and 00119 are implemented and pass their completion reviews. Do not absorb their tasks into this PRD.

## Overview

### Problem Statement
A note the vault owner makes by hand leaves three traces that `bim create` does not: a `- [ ] _DD.MM.YYYY HH:mm:ss_ - [[notes/<id>|Title]]` line under `## Log` in today's daily note, wikilinks on the first mention of every known contact in the body, and, for articles, an archived copy of the original text under `40-archives/articles/<YYYY>/<YYYYMM>00/` that the `note` zettel points to with `article::` and `web::` backmatter. Today bim's `article` template only sets `type: article`, which the vault does not use.

### Target Users
The vault owner and the agents that will create notes through `bim create` instead of the skill's own script.

### Success Metrics
- `uv run pytest tests/tools/bim/test_vault_links.py tests/tools/bim/test_article_archive.py tests/tools/bim/test_create_note.py tests/tools/bim/test_note_write_cli.py tests/tools/bim/test_settings.py tests/lib/zettel/templates/test_article_template.py -q` passes with the new cases.
- Against a scratch vault holding `contact/ada-lovelace.md` (title `Ada Lovelace`) and `calendar/daily/<today>.md` with `## Log`: `bim create -t note --title T --body-file b.md --json`, where `b.md` mentions `ada lovelace`, writes `[[notes/contact/ada-lovelace|ada lovelace]]` into the note and one new `- [ ]` line into the daily note.

## Functional Decomposition

### Capability: Daily note log
Every created note is logged where QuickAdd would log it.

#### Feature: Log entry
- **Description**: `daily_log_entry(now, wikilink)` returns the QuickAdd capture shape.
- **Inputs**: the note's `date`, its `wikilink` from 00118.
- **Outputs**: `- [ ] _{now:%d.%m.%Y %H:%M:%S}_ - {wikilink}`.
- **Behavior**: pure function.

#### Feature: Append to today's daily note
- **Description**: `append_daily_log(path_daily, now, wikilink)` inserts the entry into `<path_daily>/<YYYY-MM-DD>.md`.
- **Inputs**: `BimSettings.path_daily` (default `~/bim/notes/calendar/daily/`, env `BUVIS_BIM_PATH_DAILY`), `now`, `wikilink`.
- **Outputs**: `{"status": "added", "path": "<file>", "entry": ...}`, or `{"status": "skipped: <file> does not exist (Obsidian creates it)", "entry": ...}`, or `{"status": "skipped: <file> has no '## Log' section", "entry": ...}`.
- **Behavior**: Never creates the daily note. The `## Log` section ends at the next line matching `^#{1,2} `; the entry goes after the last non-blank line of that section, directly under the heading when the section is empty. The file is rewritten with `atomic_write_text`. `CommandCreateNote` calls it after the save and hooks, with `now = metadata["date"]`, when `CreateNoteParams.daily_log` (default `True`; CLI `--no-daily-log`) is set; the dict lands in `metadata["daily_log"]`; an `OSError` goes to `metadata["errors"]`. A dry run reports `{"status": "not written (dry run)", "entry": ...}`.

### Capability: Contact wikilinks
Known people are linked on first mention, nothing else is touched.

#### Feature: Contact name index
- **Description**: `contact_names(contact_dir)` maps every unambiguous multi-word name to its contact slug.
- **Inputs**: `<path_zettelkasten>/contact/*.md`; the first 2048 bytes of each file are read.
- **Outputs**: `dict[folded name, slug]` where slug is the file stem.
- **Behavior**: Names are the frontmatter `title`, each `aliases` entry (flow list `[a, b]`, inline comma list, or block list `- a`), and `Last, First` for a two-word title. Single-word names are dropped. Folding is NFKD, combining marks removed, lowercase, whitespace collapsed. A name owned by two slugs is dropped. Unreadable files are skipped.

#### Feature: Link first mentions
- **Description**: `link_contacts(text, names, link_prefix, skip_slug="")` wikilinks the first mention of each contact.
- **Inputs**: body text, the index, `link_prefix` = `f"{path_zettelkasten.name}/contact"`.
- **Outputs**: new text and the list of links added, in document order.
- **Behavior**: The text is folded with an index back to source offsets, so `Ada Lovelace`, `ada lovelace` and `Ada  Lovelace` all match `(?<!\w)ada\s+lovelace(?!\w)`. Protected spans are never rewritten: fenced code (``` and ~~~), inline code, existing `[[...]]`, Markdown links and images, autolinks `<scheme:...>`, bare `https?://` URLs. Candidates sort by start then longest first; overlapping candidates and later mentions of an already linked slug are dropped. Each chosen span becomes `[[{link_prefix}/{slug}|{original text}]]`. `CommandCreateNote` applies it to the body before `prepare` when `CreateNoteParams.link_contacts` (default `True`; CLI `--no-link-contacts`) is set and the template's `folder` is not `contact`; links land in `metadata["linked_contacts"]`.

### Capability: Article workflow
`bim create -t article` archives the original and writes a `note` that links to it.

#### Feature: article template (python, replaces article.yaml)
- **Description**: `ArticleTemplate` builds a `note` with article backmatter.
- **Inputs**: answers `archive_link` and `web` supplied by the command; question `web` (optional) for the TUI.
- **Outputs**: metadata `type: note`; sections `# {title}`; reference `article: {archive_link}`, then `web: [{title}]({web})` when `web` is given.
- **Behavior**: `type: article` is gone (breaking; changelog `Changed`). The body (the summary) lands in the first section as for `note`.

#### Feature: Archive the original
- **Description**: `archive_original(path_articles, title, original, web, now)` writes the original text outside the vault.
- **Inputs**: `BimSettings.path_articles` (default `~/Documents/reference/40-archives/articles/`, env `BUVIS_BIM_PATH_ARTICLES`), title, original text, optional URL, `now`.
- **Outputs**: `<path_articles>/<YYYY>/<YYYYMM>00/<name>.md` holding `# {title}\n\n{original}\n` plus `\n---\n\nSource: {web}\n` when `web` is given; returns the path.
- **Behavior**: `name` is the title with `/`, `\`, `:` and control characters replaced by `-`, stripped, trailing dots removed; an empty name raises `ValueError("title '<title>' cannot be used as a file name")`. A missing parent directory of `path_articles` raises `ValueError("<parent> does not exist; set path_articles")`. An existing target raises `FileExistsError`; the file is opened with `"xb"` so a race cannot overwrite.

#### Feature: Create command branch
- **Description**: for `template.name == "article"`, `CommandCreateNote.execute` archives first, then creates.
- **Inputs**: `--summary-file PATH` (new `CreateNoteParams.summary: str | None`; the handler reads the file), the original from `--source` or `--body-file` (00118), `-a web=URL`.
- **Outputs**: `metadata["archive"] = {"path": ...}` plus `content` under dry run; reference `article` = `[{title}](file://{quote(str(archive_path), safe="/")})`.
- **Behavior**: Missing summary fails with `article needs --summary-file with the core facts`; missing original fails with `article needs the original text: pass --body-file or --source`. The summary is the note body and gets contact links; the original is archived verbatim after frontmatter stripping. When the note creation fails after the archive was written, the archive is unlinked before the failure returns. `--summary-file` with any other template is a usage error (`console.panic`). The source file moves to `.trash/` only after both files exist.

## Structural Decomposition

### Repository Structure

```
src/tools/bim/shared/vault_links.py                                             # Maps to: Daily note log, Contact wikilinks (new)
src/tools/bim/shared/article_archive.py                                         # Maps to: Archive the original (new)
src/lib/buvis/pybase/zettel/domain/templates/article.py                         # Maps to: article template (new)
src/lib/buvis/pybase/zettel/domain/templates/article.yaml                       # Maps to: article template (deleted)
src/tools/bim/settings.py                                                       # Maps to: path_daily, path_articles
src/tools/bim/params/create_note.py                                             # Maps to: daily_log, link_contacts, summary
src/tools/bim/commands/create_note/create_note.py                               # Maps to: Create command branch, wiring
src/tools/bim/note_write_cli.py                                                 # Maps to: --no-daily-log, --no-link-contacts, --summary-file
src/tools/bim/commands/serve/_actions.py                                        # Maps to: constructor call site
src/tools/bim/tui/create_note.py                                                # Maps to: constructor call site
src/tools/bim/SKILL.md                                                          # Maps to: documentation
docs/source/tools/bim.rst                                                       # Maps to: documentation
CHANGELOG.md                                                                    # Maps to: documentation
tests/tools/bim/test_vault_links.py
tests/tools/bim/test_article_archive.py
tests/tools/bim/test_create_note.py
tests/tools/bim/test_note_write_cli.py
tests/tools/bim/test_settings.py
tests/lib/zettel/templates/test_article_template.py
tests/lib/zettel/templates/test_discover_templates.py
```

### Module: vault_links
- **Maps to capability**: Daily note log, Contact wikilinks
- **Responsibility**: pure text and file helpers ported from the skill's `vault_links.py`; no Click, no console.
- **Location**: `src/tools/bim/shared/vault_links.py`
- **Exports**: `daily_log_entry`, `append_daily_log`, `contact_names`, `link_contacts`.
- New symbols: `daily_log_entry`, `append_daily_log`, `contact_names`, `link_contacts`, `link_prefix`, `skip_slug`, `log_entry_matches_quickadd_shape`, `appends_after_last_log_line`, `skips_when_daily_note_missing`, `skips_when_no_log_heading`, `links_first_mention_case_and_diacritic_insensitive`, `never_links_inside_code_links_or_urls`, `ambiguous_name_is_not_linked`, `last_first_form_is_linked`

### Module: article_archive
- **Maps to capability**: Article workflow
- **Responsibility**: dated archive path and exclusive write of the original text.
- **Location**: `src/tools/bim/shared/article_archive.py`
- **Exports**: `archive_file_name`, `archive_original`.
- New symbols: `archive_file_name`, `archive_original`, `archive_path_is_year_month00_title`, `archive_refuses_existing_file`, `archive_name_replaces_path_characters`

### Module: article template
- **Maps to capability**: Article workflow
- **Responsibility**: `note` with `article` and `web` backmatter.
- **Location**: `src/lib/buvis/pybase/zettel/domain/templates/article.py`
- **Exports**: `ArticleTemplate`.
- New symbols: `ArticleTemplate`, `archive_link`, `article_template_is_a_note_with_backmatter`

### Module: create_note wiring
- **Maps to capability**: Daily note log, Contact wikilinks, Article workflow
- **Responsibility**: settings, params, command branch, CLI flags.
- **Location**: `src/tools/bim/settings.py`, `src/tools/bim/params/create_note.py`, `src/tools/bim/commands/create_note/create_note.py`, `src/tools/bim/note_write_cli.py`
- **Exports**: `BimSettings.path_daily`, `BimSettings.path_articles`, `CreateNoteParams` (new `daily_log`, `link_contacts`, `summary`), `CommandCreateNote` (new `path_daily`, `path_articles` constructor arguments; `serve/_actions.py` and `tui/create_note.py` pass them from settings).
- New symbols: `path_daily`, `path_articles`, `BimSettings.path_daily`, `BimSettings.path_articles`, `BUVIS_BIM_PATH_DAILY`, `BUVIS_BIM_PATH_ARTICLES`, `daily_log`, `CreateNoteParams.daily_log`, `link_contacts`, `linked_contacts`, `wikilink`, `summary_file`, `daily_log_runs_after_save`, `contact_template_body_is_not_linked`, `article_without_summary_fails`, `article_archive_is_removed_when_note_fails`, `summary_file_rejected_for_non_article`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **vault_links**: entry shape, daily append, name index, linker.
- **article_archive**: archive path and write.
- **article template**: `ArticleTemplate`.

### Core Layer (Phase 1)
- **create_note wiring**: depends on [vault_links, article_archive, article template].

### Integration Layer (Phase 2)
- **docs**: depends on [create_note wiring].

## Implementation Phases

### Phase 0: Foundation
**Goal**: The helpers exist and are tested in isolation.

**Tasks**:
- [ ] Port `daily_log_entry`, `append_daily_log`, `contact_names`, `link_contacts` into `src/tools/bim/shared/vault_links.py` using `atomic_write_text`; tests `log_entry_matches_quickadd_shape`, `appends_after_last_log_line`, `skips_when_daily_note_missing`, `skips_when_no_log_heading`, `links_first_mention_case_and_diacritic_insensitive`, `never_links_inside_code_links_or_urls`, `ambiguous_name_is_not_linked`, `last_first_form_is_linked` (no deps) - Acceptance: `uv run pytest tests/tools/bim/test_vault_links.py -q` passes.
- [ ] Add `src/tools/bim/shared/article_archive.py`; tests `archive_path_is_year_month00_title`, `archive_refuses_existing_file`, `archive_name_replaces_path_characters` (no deps) - Acceptance: `uv run pytest tests/tools/bim/test_article_archive.py -q` passes.
- [ ] Replace `article.yaml` with `article.py` (`ArticleTemplate`); test `article_template_is_a_note_with_backmatter`; update `test_discover_templates.py` if it names `article` (no deps) - Acceptance: `uv run pytest tests/lib/zettel/templates -q` passes.

**Exit Criteria**: `uv run pytest tests/tools/bim/test_vault_links.py tests/tools/bim/test_article_archive.py tests/lib/zettel/templates -q` passes.

### Phase 1: Core
**Goal**: `bim create` logs, links and archives.

**Tasks**:
- [ ] Add `path_daily` and `path_articles` to `BimSettings`; `daily_log`, `link_contacts`, `summary` to `CreateNoteParams`; the daily-log call, contact linking and the article branch to `CommandCreateNote` with `path_daily` and `path_articles` constructor arguments; update the three call sites; tests `daily_log_runs_after_save`, `contact_template_body_is_not_linked`, `article_without_summary_fails`, `article_archive_is_removed_when_note_fails` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/bim/test_create_note.py tests/tools/bim/test_settings.py -q` passes.
- [ ] Add `--no-daily-log`, `--no-link-contacts`, `--summary-file` to the `create` handler, reading the summary file in the callback and rejecting `--summary-file` for non-article templates with `console.panic`; test `summary_file_rejected_for_non_article` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/bim/test_note_write_cli.py -q` passes.

**Exit Criteria**: the scratch-vault command in Success Metrics writes the contact link and the daily-note line; `bim create -t article --title T --source inbox/a.md --summary-file s.md -a web=https://example.com --json` writes the archive copy and a `note` whose backmatter has `article::` and `web::`.

### Phase 2: Integration
**Goal**: Documented, skill complete.

**Tasks**:
- [ ] Document the three flags, the two settings and the article flow in `docs/source/tools/bim.rst`; rewrite the Create section of `src/tools/bim/SKILL.md` to cover every kind (note, project, contact, book, meeting-minutes, illustrated-note, youtube, problem-resolution-report, article) with one example each, the daily-log and contact-link defaults and when to switch them off; add `Added` (daily log, contact links, article archive, `path_daily`, `path_articles`) and `Changed` (`article` writes `type: note`) lines under `[Unreleased]` in `CHANGELOG.md` prefixed `**bim**:` (depends on: Phase 1) - Acceptance: `rg -c "summary-file" docs/source/tools/bim.rst src/tools/bim/SKILL.md` prints at least 1 for each file and `rg -c "no-daily-log" src/tools/bim/SKILL.md` prints at least 1.

**Exit Criteria**: `uv run pytest -q` passes; `uv run ruff check src tests` and `uv run mypy src/lib/ src/tools/` are clean.

## Test Strategy

### Critical Scenarios
- **Happy path**: body mentions `Ada Lovelace` twice and a daily note with `## Log` exists → Expected: one wikilink on the first mention, one new log line after the section's last entry, `linked_contacts` and a `daily_log` entry with status `added` in metadata.
- **Happy path**: article with `--source inbox/a.md --summary-file s.md -a web=URL` → Expected: archive at `<path_articles>/<YYYY>/<YYYYMM>00/T.md` ending with `Source: URL`, note `type: note`, backmatter `- article:: [T](file://...)` then `- web:: [T](URL)`, source in `.trash/`.
- **Edge case**: `Lovelace, Ada` in the body → Expected: linked to `ada-lovelace`.
- **Edge case**: the name appears inside a fenced block and in prose → Expected: only the prose mention is linked.
- **Edge case**: no daily note today → Expected: note created, the `daily_log` status starts with `skipped:`, exit 0.
- **Error case**: two contacts share an alias → Expected: that alias is never linked; their unique titles still are.
- **Error case**: archive written, note creation raises → Expected: archive removed, failure returned, nothing in `.trash/`.

## Risks

- **Single-word names**: first names and company short names are never linked by design; a human links those. Documented in the skill.
- **Daily note outside the zettelkasten**: `path_daily` defaults under `~/bim/notes/`; a vault that keeps daily notes elsewhere sets the setting, and a missing file is a skip, never an error.
- **Archive outside the vault**: `path_articles` is written with an exclusive open and removed on note failure, so a half-done article leaves no orphan.
