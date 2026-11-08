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
bim create -t note --title "Why caches lie" --tags "cache,debugging"
bim create -t project --title "Redesign homepage" -a dev_type=feature
bim create -t contact --title "Ada Lovelace" -a contact_type=friend -a email=ada@example.com
bim create -t meeting-minutes --title "Weekly sync" -a "location=face to face" -a "organizer=Ada Lovelace"
```

Always pass both `-t` and `--title` when scripting; without them `bim create`
opens an interactive TUI. `-a key=value` answers a template question, and a
missing required answer fails with `Missing required answer: <key>`. Success
prints `Created <path>`. A failed create prints the reason and still exits 0,
so read the output, not the exit code. Bundled templates: `note`, `project`,
`contact`, `meeting-minutes`, `article`, `definition`, `how-to`, `list`,
`procedure`, `quote`, `recipe`, `snippet`, `cheatsheet`, `course`,
`wiki-article`. A YAML file in `~/.config/buvis/templates/` with the same
`name` overrides a bundled template.

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
- Human-facing lines are prefixed with status markers such as `✓` and `✘`.
  Treat `✘` as failure regardless of the exit code.
