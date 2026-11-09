---
name: bim
description: "Use when reading, searching, creating, editing, or archiving notes in a BUVIS InfoMesh (BIM) vault or zettelkasten, or when asked how the vault is organized. Triggers on \"bim\", \"zettel\", \"query the vault\", \"bim create\", \"archive this note\"."
---

# bim

`bim` manages a zettelkasten of Markdown notes with YAML frontmatter. Notes live
in one directory (default `~/bim/notes/`), archived notes in another (default
`~/Documents/reference/40-archives/`). Every note carries `id` (14 digits,
`YYYYMMDDHHMMSS`), `title`, `date`, `tags`, `type`, `publish` and `processed`,
then a `# Title` heading and sections. bim assigns `id` and `date` itself.
When the notes live in a BIM vault, read "The BIM vault" at the end before you
touch anything.

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
anything. A failed create writes nothing unless its error starts with
`note saved at`; that error means the file exists, so do not retry.
When the JSON has `errors`, the note
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

## The BIM vault

A BIM vault is an Obsidian vault that blends GTD, Zettelkasten and PARA. Its
root is the parent of `path_zettelkasten` (default `~/bim/`). The vault
documents itself in `notes/system/`; start at `notes/system/index.md`. Work
without Obsidian running.

### Layout

| Path | Holds | Rules |
|------|-------|-------|
| `inbox/` | Raw material: any file name, rarely frontmatter. Obsidian and automations (`inbox/automated/`) put new files here. | Read freely. Turn an item into a note with `bim create --source`, which moves it to `.trash/`. |
| `notes/` | `<id>.md` zettels, `contact/<slug>.md`, `book/<slug>.md`, `documents/` (`bim doc`), `kanban/` (Kanban plugin boards), `index.md`, `.base` files (Obsidian Bases) | See "Note anatomy". |
| `notes/calendar/` | `daily/YYYY-MM-DD.md`, `weekly/YYYY-Www.md` | Obsidian creates these; never create them. Append to a daily `## Log` only when asked; `bim create` logs its own notes. |
| `notes/system/` | System docs, `templates/` (Templater `.tpl`), `scripts/` | Read-only unless asked. |
| `resources/<category>/` | Assets: `book-cover/`, `contact-picture/`, `notes-attachments/` (Obsidian's attachment folder), `screenshots/`, `icon/`, `media-lib/`, and topic folders | Put a new asset in the matching category and link it from a note. Leave `media-lib/` alone. |
| `.obsidian/` | App and plugin config | Never edit. |
| `.trash/` | Obsidian's local trash | Move files here instead of deleting them. |

PARA reference material lives outside the vault, in
`~/Documents/reference/{10-projects,20-areas,30-resources,40-archives}`.
`path_projects`, `path_archive` and `path_articles` point into it. Notes never
go there.

### Note anatomy

```markdown
---
id: 20260105093012
title: Sourdough starter care
date: 2026-01-05T09:30:12+01:00
tags: [cooking, bread]
type: note
publish: false
processed: false
---

# Sourdough starter care

Body in Markdown.

---

- parent:: [[notes/20251220181544|§ Baking]]
- web:: [Starter basics](https://example.com/starter)
```

- The file name is the `id` and never changes. A rare variant carries a
  suffix (`<id>_a.md`); prefer a new note. Hub and table-of-contents notes may
  be named `<slug>.hub.md` or `<slug>.toc.md`; they still carry an `id`.
- One note, one idea: split a note that grows unrelated sections. The title
  stands alone, like a line in an index.
- Every note has `id`, `title`, `date` and `type`. Keys are lowercase with
  dashes; quote a value only when YAML needs it (a colon); booleans are
  `true` and `false`.
- The H1 matches `title` exactly. Older problem resolution reports prefix it
  with `PRR: `. Index (MOC) titles start with `§`.
- Tools write `publish: false` and `processed: false` only; the owner flips
  them after review.
- Tags: three to five (more than seven is a smell), kebab-case, nested broad
  to narrow with `/` (`lang/rust`), `tags: []` when there are none. Reuse
  existing tags. Older notes use a block list.
- Backmatter is everything after the last `---`: Dataview fields written as
  `- key:: value`, where the value is text, a URL, a Markdown link or a
  wikilink. bim omits the rule when the backmatter is empty. Common keys:
  `parent`, `project`, `ticket`, `sr`, `us`, `psd`, `web`, `teams`, `article`,
  `book`, `referral`, `twitter`, `intranet`, `repo`, `shop`. Put Microsoft
  Teams URLs in `teams::`, never `web::`. A note that comes from a web page
  keeps the URL in `web::`, not only in the body. Keep every key you do not
  recognize when you rewrite a note.
- `type` is a closed vocabulary: the bundled templates plus `configuration`,
  `customizing`, `project-tracker`, `tracker`, `index`, `toc`, `ai-prompt`,
  `budget`, `meter-reading`, `itinerary`, `poem`, `joke` and `application`
  (older reports use `problem-resolution`). When unsure, use `note`; never
  invent a type. Some older notes carry one-off types; report an unknown
  type, do not coerce it.

Type-specific frontmatter:

- `project`: `completed`, `deliverable`, `resources`.
- `meeting-minutes`: `location`, `start` and `end` (`HH:mm`), `organizer`,
  `attendees` (list), `summary`.
- `contact`: `contact-type` (comma-separated: `person`, `colleague`, `author`,
  `schoolmate`, `friend`, `family`, `business`), `summary`, `company`,
  `job-title`, `email`; rarely `birthday`, `location`, `socials`.
- `book`: `summary`, `author`, `last-read` (`9999-12-31` means unread).
- YouTube note: `origin: youtube`, `source` (watch URL), `author`, `summary`.
- `snippet`: `language` (the fence language). `course`: `provider`, `length`,
  `status`.

Body shapes:

| Type | Body |
|------|------|
| `note` | A short essay or structured explainer. |
| `definition` | One term in one or two paragraphs, then an optional `## Example`. Longer explanations are a `note`. |
| `procedure` | One numbered list; sub-steps are nested numbered lists; prose between steps stays short. |
| `wiki-article` | One setting, tweak or trick in two to ten lines, plus at most one code block. Grown past that, it becomes a `note` or a `procedure`. |
| `cheatsheet` | Bullets or a table, no long paragraphs. |
| `list` | A short lead-in, then bullets; sub-headings group the items. |
| `snippet` | One code block with one or two lines above it. |
| `recipe` | Ingredients, then steps. |
| `project` | `## Description` (why the project exists, rarely revised), `## Log` (the working record, newest on top), `## Plan` (a checklist; an item moves to the Log once acted on), `## Solution` (written at closure; the placeholder may stay while open). |
| `meeting-minutes` | `## Agenda` (may be empty), `## Log` (plain bullets as things happen), `## Post-processing` (a fixed block: move the actions under its GTD tags and write `summary`). |

### Links

- Internal links are wikilinks with the vault-absolute path and the title as
  alias: `[[notes/<id>|Title]]`, `[[notes/contact/<slug>|Name]]`,
  `[[notes/book/<slug>|Title]]`, `[[notes/<slug>.hub|Title]]`. The alias is
  optional but preferred.
- External URLs and local paths are Markdown links: `[Title](https://...)`.
- Embeds: `![[note#Heading]]` for a section, `![alt|240](path.jpeg)` for a
  sized image.

### GTD tasks and logs

- Tasks follow the Tasks plugin: `- [ ] text`, then `📅` (due), `⏳`
  (scheduled), `🛫` (start), `✅` (done) or `❌` (cancelled) with a date, and
  priority `⏬ 🔽 🔼 ⏫ 🔺`.
- States: `[ ]` open, `[x]` done, `[i]` information, `[>]` forwarded,
  `[-]` cancelled, `[/]` in progress. Any other state is an error; report it.
- GTD lists are tags on tasks: `#gtd/act/now` (today), `#gtd/act/next` (once
  the now items clear), `#gtd/act/later` (reconsider at the next review),
  `#gtd/act/someday` (maybe), `#gtd/wait` (blocked on someone or something
  else). `#gtd/inbox` marks a note whose checkboxes still need processing;
  `#gtd/ignore` keeps checkboxes that are not actions out of the lists.
- Project log entry, newest on top, never rewritten (new understanding goes
  on a new line):
  `- [STATE] YYYY-MM-DD HH:mm - what happened => next action | #gtd/act/now 📅 YYYY-MM-DD`.
  The fact comes first, in the past tense; `=>` and the decision, the GTD
  tag, and the date markers are optional. A line may carry a planning and a
  closure marker (`📅 2026-05-11 ✅ 2026-05-14`).
- Daily log entry (QuickAdd): `- [ ] _DD.MM.YYYY HH:mm:ss_ - entry` under
  `## Log` in `notes/calendar/daily/YYYY-MM-DD.md`.

### Plugins that act on files

- Templater runs the `.tpl` templates inside Obsidian only; `bim create`
  reproduces them.
- Auto Note Mover moves notes tagged `#person` to `notes/contact/` and `#book`
  to `notes/book/`. Never put those tags on other notes.
- Linter formats on save: it strips trailing spaces, sets blank lines around
  headings and rules, and drops empty list markers. Write output that already
  passes.
- Dataview, Tasks and Checklist read `type`, `processed`, `status` and task
  tags. Keep them accurate.
- Front Matter Title shows `title` in place of the file name, so no `aliases`
  key is needed. Excalidraw owns the drawing section of illustrated notes.

### Vault rules

1. Create notes with `bim create` so ids and shapes match the templates.
2. Never overwrite, rename or move an existing note: ids and slugs are link
   targets.
3. To delete a note, move it to `.trash/` and keep its name; on a clash add a
   space and a number (`Untitled 1.md`). `bim delete` is permanent; use it only
   when the user asks for it.
4. Do not edit `.obsidian/`, `notes/system/templates/`,
   `notes/system/scripts/`, Kanban board structure or Excalidraw JSON unless
   asked.
5. Write UTF-8 with LF line endings and one trailing newline.
6. The vault is private. Do not copy note content into shared repos, tickets
   or third-party services unless asked.
