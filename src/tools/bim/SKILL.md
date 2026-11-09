---
name: bim
description: "Use when reading, searching, creating, editing, or archiving notes in a BUVIS InfoMesh zettelkasten through the bim CLI. Triggers on \"bim\", \"zettel\", \"query the vault\", \"bim create\", \"archive this note\"."
---

# bim

`bim` manages a zettelkasten of Markdown notes with YAML frontmatter. Notes live
in one directory (default `~/bim/notes/`), archived notes in another (default
`~/Documents/reference/40-archives/`). Every note carries `id` (14 digits,
`YYYYMMDDHHMMSS`), `title`, `date`, `tags`, `type`, `publish` and `processed`,
then a `# Title` heading and sections. bim assigns `id` and `date` itself.

## Learn the installed CLI

The installed binary is the authority for syntax:

```bash
bim --help
bim <command> --help
bim create -l      # bundled and user templates
bim query -l       # saved queries and their paths
```

Both directories come from settings: `path_zettelkasten` and `path_archive` in
`~/.config/buvis/buvis-bim.yaml`, the environment variables
`BUVIS_BIM_PATH_ZETTELKASTEN` and `BUVIS_BIM_PATH_ARCHIVE`, or `bim --config FILE`.
To experiment, point `BUVIS_BIM_PATH_ZETTELKASTEN` at a scratch directory. Never
test against the real notes.

## Select notes

`show`, `edit`, `format`, `archive`, `delete` and `sync` take note paths, or a
query in their place: `-Q NAME` runs a saved query, `-q 'YAML'` an inline one.
A query is a YAML spec with `filter`, `columns`, `sort` and `output`:

```bash
bim query -q '{filter: {field: type, op: eq, value: project}, columns: [{field: id}, {field: title}], output: {format: json}}'
bim query -Q recent
bim show -q '{filter: {field: title, op: contains, value: cache}}'
```

Use `output: {format: json}` or `jsonl` when you parse the result; `table` is
for humans. Saved queries include `recent`, `inbox`, `unprocessed`, `contacts`,
`active_projects` and `all_open_tasks`. Filter operators, calculated columns and
lookups: https://github.com/buvis/gems/blob/master/docs/source/bim-query-examples.md

## Read

`bim show PATH` prints the note as stored, frontmatter included.

## Create

```bash
bim create -t note --title "Why caches lie" --tags "cache,debugging" --json
bim create -t note --title "Meeting takeaways" --body-file takeaways.md --json
bim create -t note --source ~/bim/inbox/draft.md --json      # title from the file name; file moves to .trash/
bim create -t project --title "Redesign homepage" -a deliverable=enhancement -a ticket=SR-1 --json
bim create -t contact --title "ada lovelace" -a email=ada@example.com --json   # notes/contact/ada-lovelace.md, tag person
bim create -t book --title "Dune" --json                                         # notes/book/dune.md, tag book
bim create -t meeting-minutes --title "Weekly sync" -a location=teams --body-file log.md --json
bim create -t youtube --title "Talk title" -a video=https://youtu.be/dQw4w9WgXcQ --json
bim create -t illustrated-note --title "Sketch" --json
bim create -t problem-resolution-report --title "Outage" --json
bim create -t article --title "Why caches lie" -a web=https://example.com/post --body-file original.md --summary-file facts.md --json
```

Always pass `-t` plus `--title` or `--source`; a bare `bim create` opens an
interactive TUI. Prefer `--json`: it prints one object with `id`, `type`,
`title`, `tags`, `path`, `relative_path` and `wikilink` (paste the `wikilink`
into other notes), and on failure `{"error": "<reason>"}` with exit 1. Run
with `--dry-run` first to see the rendered note in `content` without writing
anything. A failed create writes nothing. When the JSON has `errors`, the note
exists but a follow-up step (moving the source to `.trash/`) failed.

- `--body-file PATH` (`-` for stdin) appends Markdown to the template's body
  section: after the H1 for notes, under `## Solution` for projects, `## Log`
  for meetings, `## Notes` for youtube and `## Gather information` for PRRs.
  `--source PATH` converts a file from `<vault>/inbox/`: its frontmatter is
  dropped, its name is the default title, and it moves to `.trash/` once the
  note is written. Never combine the two.
- `-a key=value` answers a template question; a missing required answer fails
  with `Missing required answer: <key>`.
- Tags: comma-separated, `#` optional, lowercased, deduplicated. Use letters,
  digits, `-`, `_` and `/` for nesting; a tag with spaces or only digits fails.
  `person` and `book` belong to contacts and books, are added automatically
  and are rejected on any other template.
- Ids equal the local-time digits of `date`, like the vault's own notes.
- Every create logs the note under `## Log` in today's daily note
  (`path_daily`, default `~/bim/notes/calendar/daily/`; never created, a
  missing note is reported as `skipped`) and wikilinks the first mention of
  each person from `notes/contact/` in the body: title, multi-word aliases
  and `Last, First`, case- and diacritic-insensitive, never inside code,
  links or URLs, never one-word names or names two contacts share. The JSON
  reports `daily_log` and `linked_contacts`; mention both to the user. Pass
  `--no-link-contacts` for an exact copy that must stay verbatim and
  `--no-daily-log` when the note should not appear in the daily log. When a
  sender's full name is known but was not linked, write it in full in the body.

Articles (published prose to read and keep: a post, an announcement, a
newsletter) are a pair: `-t article` archives the original (`--body-file` or
`--source`, frontmatter dropped) under `path_articles` (default
`~/Documents/reference/40-archives/articles/<YYYY>/<YYYYMM>00/<title>.md`)
and writes a `note` with the `--summary-file` core facts whose backmatter has
`article::` (a `file://` link) and `web::`. Keep the article's own title with
its casing: it names the archive file. Leave the H1 out of both files. The JSON
has `archive.path`; report it with the `wikilink`.

Bundled templates and their answers:

- `note`, and the plain kinds `definition`, `how-to`, `list`, `procedure`,
  `quote`, `recipe`, `snippet`, `cheatsheet`, `course`, `wiki-article`: no
  answers.
- `article`: `web` (optional source URL); needs `--summary-file` and the
  original text through `--body-file` or `--source`.
- `project`: `deliverable` (`fix`, `enhancement`, `support`; required) and
  `ticket` (optional). The note links a resources folder
  `<path_projects>/<id>-<slug>` (`path_projects` defaults to
  `~/Documents/reference/10-projects/`); when that root is missing the JSON
  carries a `warnings` entry and the note is still written.
- `contact`: full name as `--title` (every word is capitalised); optional
  `company`, `job-title`, `email`. Written to `notes/contact/<slug>.md`.
- `book`: the title as printed on the cover. Written to `notes/book/<slug>.md`.
- `meeting-minutes`: `location` (`webex`, `teams`, `phone`, `face to face`;
  required) and `organizer`. Give only the subject as `--title`; the note is
  titled `YYYY-MM-DD | <Subject> meeting minutes`.
- `youtube`: `video` (URL or 11-character id; required).
- `illustrated-note`, `problem-resolution-report`: no answers.

A contact or book whose slug already exists fails with `Zettel already
exists`; open the existing note instead of retrying with another title. A
YAML file in `~/.config/buvis/templates/` with the same `name` overrides a
bundled template.

## Edit metadata

```bash
bim edit PATH --title "Better title"
bim edit PATH --tags "a,b" --processed
bim edit PATH -s "priority=high"
bim edit -q '{filter: {field: type, op: eq, value: note}}' --processed
```

Without a change flag `bim edit PATH` opens a TUI. Edit the body with your file
tools, then run `bim format PATH` so key order, tag sorting and spacing stay
canonical; `bim format PATH -d` shows the diff first.

## Import

`bim import FILE --tags "a,b"` copies a Markdown note into the zettelkasten as
`<id>.md`, normalised. The file needs an `id` in its frontmatter; otherwise it
is skipped with a warning. `--force` overwrites an existing target and
`--remove-original` deletes the source. Any flag makes the run non-interactive;
a bare `bim import FILE` prompts.

## Archive, delete, sync

- `bim archive PATH` marks the note processed and moves it to the archive
  directory; `--undo` moves it back.
- `bim delete PATH` is permanent. Prefer `archive`. `--force` skips the
  confirmation; without it a prompt waits for a human.
- `bim sync -t jira PATH` synchronises a project note with Jira using the
  `adapters.jira` settings.

`bim serve` starts the web dashboard and `bim doc` is the document ingestion
pipeline; both have their own `--help`.

## Rules

- Never run `bim create`, `bim edit PATH` or `bim import FILE` without flags in
  automation: they open a TUI or a prompt and hang.
- Do not invent ids and do not edit `id` or `date` by hand.
- Delete only when the user asked for deletion; archive otherwise.
- Every note command exits 1 on failure. Human-facing lines are prefixed with
  status markers such as `✓` and `✘`; with `--json` read the `error` key.
