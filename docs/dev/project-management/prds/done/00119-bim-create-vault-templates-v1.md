---
default_model: opus
model_tier_rationale: the templates must reproduce the vault's Templater output (equivalence obligation) and the template protocol gains new attributes several modules read
---

# bim create: vault-shaped templates

Source: conversation assessment of 2026-11-08; second of three PRDs after 00118 (scripting contract). The target shapes are the eight templates the `create-note` skill ported from the vault's Templater files: `skills/create-note/assets/templates/*.md` in https://github.com/buvis/agent-skills, read them before writing a template.

## Execution prerequisite

Start only after PRD 00118 is implemented and passes its completion review. Do not absorb its tasks into this PRD.

## Overview

### Problem Statement
`bim create` fills bim's own templates, which do not match the notes the vault's Templater makes, so a note created by bim looks foreign and Obsidian automations miss it:

- `project` asks `dev_type`, writes `dev-type` and an `## Actions buffer`, and lacks `deliverable`, `resources`, `## Plan` and `## Solution`. Its `create_project_dir` hook runs after the save, so `resources` never reaches the file, and it creates `<vault>/projects/<id>` instead of the PARA project folder.
- `contact` writes a flat `<id>.md` titled `Ada lovelace` with `contact-type: colleague`; the vault keeps people at `notes/contact/<slug>.md`, title-cased, tagged `person` so Auto Note Mover and the contacts query find them. Books have no template at all.
- `meeting-minutes` has no dated `YYYY-MM-DD | <subject> meeting minutes` title, offers `online` instead of `webex|teams|phone|face to face`, and lacks the GTD post-processing block.
- There is no `illustrated-note`, `youtube` or `problem-resolution-report` template, and no template can set backmatter (`ZettelData.reference`).

### Target Users
The vault owner and the agents creating notes through `bim create`, who need bim output indistinguishable from Templater output.

### Success Metrics
- `uv run pytest tests/lib/zettel/templates tests/lib/zettel/test_template_loader.py tests/lib/zettel/application/test_create_zettel_use_case.py tests/tools/bim/test_create_note.py -q` passes with the new cases.
- Against a scratch zettelkasten, `bim create -t contact --title "ada lovelace" --json` writes `<zettelkasten>/contact/ada-lovelace.md` with `title: Ada Lovelace` and `tags: [person]`; `bim create -t project --title "Probe" -a deliverable=fix --json` writes a note whose frontmatter has `resources` and whose backmatter starts with `- parent:: [[notes/<id>|Probe]]`.

## Functional Decomposition

### Capability: Template placement and shape
Templates decide where a note lives, what it is named, which tags it carries, where a body lands and what backmatter it has.

#### Feature: Optional template attributes
- **Description**: `ZettelTemplate` implementations may expose `folder`, `file_stem`, `default_tags` and `body_section`; readers use `getattr(template, name, default)` so the fourteen existing templates need no change.
- **Inputs**: template object.
- **Outputs**: `folder: str = ""` (subdirectory of the zettelkasten), `file_stem: "id" | "slug"` (default `"id"`), `default_tags: list[str] = []`, `body_section: str | None = None`.
- **Behavior**: `YamlTemplate` reads the same four keys from the YAML top level, a `reference` mapping into `data.reference`, and adds `slug` (see Slugs) to the answers before `format_map`, so `{slug}` works in metadata and sections.

#### Feature: Slugs
- **Description**: `StringOperator.slugify` ports the vault's slug expression.
- **Inputs**: a title.
- **Outputs**: NFKD-normalised, combining marks dropped, lowercased, characters outside `[a-z0-9 -]` removed, whitespace runs to `-`, dash runs collapsed; `"Ada  Lovelace"` gives `ada-lovelace`, and "Čapek" gives "capek".
- **Behavior**: An empty result for a `file_stem: slug` template fails the create with `title '<title>' gives an empty slug; use a title with Latin letters or digits`.

#### Feature: Path from template
- **Description**: `CreateZettelUseCase.prepare` (00118) builds the path from the template attributes.
- **Inputs**: prepared zettel, template.
- **Outputs**: `zettelkasten_path / folder / f"{stem}.md"` where `stem` is `str(zettel.id)` or the slug.
- **Behavior**: `execute` creates `folder` with `mkdir(parents=True, exist_ok=True)`. The 00118 collision wait applies only to `file_stem: id`; a slug path that exists fails at once with `Zettel already exists: <path>`.

#### Feature: Default tags
- **Description**: `CommandCreateNote.execute` merges `default_tags` ahead of the validated user tags.
- **Inputs**: template `default_tags`, cleaned user tags, the `templates` dict.
- **Outputs**: `answers["tags"]`.
- **Behavior**: Order is defaults first, then user tags not already present. A user tag that is a default tag of a different template fails with `tag '<tag>' is reserved for the <name> template`, so `--tags person` on a note cannot trigger Auto Note Mover by accident.

#### Feature: Hooks before save
- **Description**: `execute` runs `template.hooks()` between `prepare` and `writer.save`, so a hook's metadata lands in the file.
- **Inputs**: hooks, `ZettelData`, zettelkasten path, settings bound by `get_hook_runner`.
- **Outputs**: mutated `ZettelData`.
- **Behavior**: `get_hook_runner(path_projects: Path)` returns `functools.partial(run_template_hooks, path_projects=path_projects)`; `run_template_hooks` gains that keyword. Registry: `create_project_dir` makes `<path_projects>/<id>-<slug>` when `path_projects` exists (else skips and leaves a `warnings` entry on the result) and sets `metadata["resources"] = f"[project resources]({project_dir.as_uri()})`; `set_parent_reference` sets `reference["parent"] = f"[[{zettelkasten_path.name}/{id}|{title}]]`; `set_illustration_link` replaces `{id}` in the first section body. `BimSettings.path_projects` defaults to `~/Documents/reference/10-projects/`, env `BUVIS_BIM_PATH_PROJECTS`.

### Capability: Vault templates
Eight templates reproduce the Templater output. Prose bodies are transcribed from the agent-skills template files named in the source line; `{title}`, `{slug}`, `{now}` are filled at build time, `{id}` by a hook. Python templates set `metadata["date"] = datetime.now().astimezone().replace(microsecond=0)` whenever the title or a section needs the date, so date, id and text agree.

#### Feature: project (python, rewritten)
- **Description**: project loop file with resources folder.
- **Inputs**: questions `deliverable` (choices `fix`, `enhancement`, `support`, required, no default), `ticket` (optional).
- **Outputs**: metadata `type: project`, `completed: false`, `deliverable`; sections `# {title}`, `## Description` ("One paragraph summarizing the problem statement."), `## Log` (`- [ ] {now:%Y-%m-%d %H:%M} - plan the next action to move this project forward | #gtd/act/now 📅 {now:%Y-%m-%d}`), `## Plan` ("Plan the steps to complete the project. Use templates for recurring projects."), `## Solution` ("Describe what was done to get project closure acceptance."); reference `parent` (hook), `ticket` when given, `us: ""`, `psd: ""`; hooks `set_parent_reference`, `create_project_dir`; `body_section = "## Solution"`.
- **Behavior**: `dev_type` and `## Actions buffer` are gone (breaking; changelog `Changed`).

#### Feature: contact (python, replaces contact.yaml)
- **Description**: a person at `contact/<slug>.md`.
- **Inputs**: optional answers `company`, `job-title`, `email` (default `""`).
- **Outputs**: title with every word capitalised (`ada lovelace` to `Ada Lovelace`); `folder = "contact"`, `file_stem = "slug"`, `default_tags = ["person"]`; metadata `type: contact`, `contact-type: person`, `summary: ""`, `company`, `job-title`, `email`; sections `# {title}` with body `![{title} photo|180]({slug}.jpeg)`, `## First contact`, `## Timeline`, `## Relationships`.
- **Behavior**: `contact_type` question removed (breaking).

#### Feature: book (yaml, new)
- **Description**: a book at `book/<slug>.md`.
- **Inputs**: none beyond title and tags.
- **Outputs**: `folder: book`, `file_stem: slug`, `default_tags: [book]`; metadata `type: book`, `summary: ""`, `last-read: "9999-12-31"`, `author: ""`; sections `# {title}` with body `![{title} cover|240](resources/book-cover/{slug}.cover.jpeg)`, `## Thesis`, `## Antithesis`, `## Synthesis`; reference `shop: ""`.
- **Behavior**: static YAML; proves the new YAML keys.

#### Feature: meeting-minutes (python, replaces meeting_minutes.yaml)
- **Description**: dated minutes with the GTD block.
- **Inputs**: `location` (choices "webex", "teams", "phone", "face to face"; required, no default), `organizer` (optional, default `""`).
- **Outputs**: title `{now:%Y-%m-%d} | {Subject} meeting minutes` where `Subject` is the input with a trailing `meeting minutes` (case-insensitive) removed and its first letter upper-cased; metadata `type: meeting-minutes`, `location`, `start: "hh:mm"`, `end: "hh:mm"`, `organizer`, `attendees: [""]`, `summary: ""`; sections `# {title}`, `## Agenda`, `## Log`, `## Post-processing` with the body "Don't forget to write a summary into frontmatter!\n\nGo through the log and record actions into GTD lists below.\n\n#gtd/act/now\n\n#gtd/act/next\n\n#gtd/wait\n\n#gtd/act/someday"; `body_section = "## Log"`.
- **Behavior**: an empty subject raises `ValueError("meeting title needs a subject, not just 'meeting minutes'")`, which `CommandCreateNote` turns into a failed result.

#### Feature: illustrated-note (python, new)
- **Description**: Excalidraw note.
- **Inputs**: none beyond title and tags.
- **Outputs**: metadata `type: illustrated-note`, `excalidraw-plugin: parsed`, `excalidraw-open-md: true`; sections `# {title}` with body `![{title}]({id}.svg)`, `# Text Elements` with the body `%%\n# Drawing\n` + the fenced Excalidraw JSON from the ported template + `\n%%`; hook `set_illustration_link`.
- **Behavior**: `{id}` is resolved by the hook after the fixers assign the id.

#### Feature: youtube (python, new)
- **Description**: notes on a video, `type: note`.
- **Inputs**: `video` (required): a YouTube URL or an 11-character id.
- **Outputs**: metadata `type: note`, `summary: "One sentence summarizing the content"`, `origin: youtube`, `author: ""`, `source: https://www.youtube.com/watch?v={video_id}`; sections `# {title}` with the ported iframe line, a blank line, `> [!abstract] Summary` and `> One paragraph summarizing the content.`, then `## Notes`; `body_section = "## Notes"`.
- **Behavior**: id extraction accepts youtu.be/ID, youtube.com/watch?v=ID, and the /live/, /shorts/, /embed/ and /v/ paths on youtube.com, its subdomains and youtube-nocookie.com, or a bare `[A-Za-z0-9_-]{11}`; anything else raises `ValueError("cannot find a YouTube video id in '<value>'")`.

#### Feature: problem-resolution-report (yaml, new)
- **Description**: PRR skeleton.
- **Inputs**: none beyond title and tags.
- **Outputs**: metadata `type: problem-resolution-report`; sections `# PRR: {title}`, `## Define the problem`, `## Gather information`, `### What?`, `### Who?`, `#### Reporter`, `#### Client employees`, `### When?`, `### Where?`, `### How?`, `### Why?`, `### Observations`, `## Analyze the information`, `### Questions`, `### Answers`, `## Propose solutions`, `## Implement the solution`, `## Validate the solution`, `## Monitor and control`, `## Document and report`, each with the prose body of the ported template; reference `parent: ""`; `body_section: "## Gather information"`.
- **Behavior**: static YAML.

## Structural Decomposition

### Repository Structure

```
src/lib/buvis/pybase/formatting/string_operator/string_operator.py              # Maps to: Slugs
src/lib/buvis/pybase/zettel/domain/templates/__init__.py                        # Maps to: Optional template attributes (protocol docs)
src/lib/buvis/pybase/zettel/domain/templates/yaml_template.py                   # Maps to: Optional template attributes
src/lib/buvis/pybase/zettel/domain/templates/project.py                         # Maps to: project
src/lib/buvis/pybase/zettel/domain/templates/contact.py                         # Maps to: contact (new)
src/lib/buvis/pybase/zettel/domain/templates/contact.yaml                       # Maps to: contact (deleted)
src/lib/buvis/pybase/zettel/domain/templates/book.yaml                          # Maps to: book (new)
src/lib/buvis/pybase/zettel/domain/templates/meeting_minutes.py                 # Maps to: meeting-minutes (new)
src/lib/buvis/pybase/zettel/domain/templates/meeting_minutes.yaml               # Maps to: meeting-minutes (deleted)
src/lib/buvis/pybase/zettel/domain/templates/illustrated_note.py                # Maps to: illustrated-note (new)
src/lib/buvis/pybase/zettel/domain/templates/youtube.py                         # Maps to: youtube (new)
src/lib/buvis/pybase/zettel/domain/templates/problem_resolution_report.yaml     # Maps to: problem-resolution-report (new)
src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py     # Maps to: Path from template, Hooks before save
src/lib/buvis/pybase/zettel/infrastructure/persistence/template_loader.py       # Maps to: Hooks before save
src/tools/bim/settings.py                                                       # Maps to: path_projects
src/tools/bim/dependencies.py                                                   # Maps to: get_hook_runner
src/tools/bim/commands/create_note/create_note.py                               # Maps to: Default tags
src/tools/bim/note_write_cli.py                                                 # Maps to: get_hook_runner call
src/tools/bim/commands/serve/_actions.py                                        # Maps to: get_hook_runner call
src/tools/bim/tui/create_note.py                                                # Maps to: get_hook_runner call
src/tools/bim/SKILL.md                                                          # Maps to: documentation
docs/source/tools/bim.rst                                                       # Maps to: documentation
CHANGELOG.md                                                                    # Maps to: documentation
tests/lib/pybase/formatting/test_string_operator.py
tests/lib/zettel/templates/test_yaml_template.py
tests/lib/zettel/templates/test_project_template.py
tests/lib/zettel/templates/test_contact_template.py
tests/lib/zettel/templates/test_meeting_minutes_template.py
tests/lib/zettel/templates/test_illustrated_note_template.py
tests/lib/zettel/templates/test_youtube_template.py
tests/lib/zettel/templates/test_discover_templates.py
tests/lib/zettel/test_template_loader.py
tests/lib/zettel/application/test_create_zettel_use_case.py
tests/tools/bim/test_create_note.py
tests/tools/bim/test_settings.py
```

### Module: string_operator
- **Maps to capability**: Template placement and shape
- **Responsibility**: text helpers shared by templates and the use case.
- **Location**: `src/lib/buvis/pybase/formatting/string_operator/string_operator.py`
- **Exports**: `StringOperator.slugify`.
- New symbols: `slugify`, `slugify_strips_diacritics_and_joins_with_dashes`, `slugify_returns_empty_for_non_latin_title`

### Module: templates
- **Maps to capability**: Vault templates
- **Responsibility**: one module or YAML file per template; python templates own title and date logic.
- **Location**: `src/lib/buvis/pybase/zettel/domain/templates/`
- **Exports**: `ProjectTemplate` (changed), `ContactTemplate`, `MeetingMinutesTemplate`, `IllustratedNoteTemplate`, `YoutubeTemplate`, `YamlTemplate` (new keys).
- New symbols: `ContactTemplate`, `MeetingMinutesTemplate`, `IllustratedNoteTemplate`, `YoutubeTemplate`, `extract_video_id`, `youtube`, `us`, `psd`, `folder`, `file_stem`, `default_tags`, `body_section`, `yaml_reference_lands_in_data_reference`, `yaml_slug_is_available_in_sections`

### Module: create_zettel_use_case and template_loader
- **Maps to capability**: Template placement and shape
- **Responsibility**: path from attributes, hooks before save, hook registry with settings.
- **Location**: `src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py`, `src/lib/buvis/pybase/zettel/infrastructure/persistence/template_loader.py`
- **Exports**: `CreateZettelUseCase.prepare`, `CreateZettelUseCase.execute`, `run_template_hooks` (new `path_projects` keyword).
- New symbols: `_set_parent_reference`, `_set_illustration_link`, `set_parent_reference`, `set_illustration_link`, `slug_template_writes_into_folder`, `slug_collision_fails_without_retry`, `hook_metadata_is_in_the_saved_file`, `project_dir_skipped_when_root_missing`

### Module: bim wiring
- **Maps to capability**: Template placement and shape
- **Responsibility**: `path_projects` setting, bound hook runner, default-tag merge.
- **Location**: `src/tools/bim/settings.py`, `src/tools/bim/dependencies.py`, `src/tools/bim/commands/create_note/create_note.py`
- **Exports**: `BimSettings.path_projects`, `get_hook_runner(path_projects)`, `CommandCreateNote`.
- New symbols: `path_projects`, `BimSettings.path_projects`, `BUVIS_BIM_PATH_PROJECTS`, `default_tags_come_first`, `reserved_tag_of_other_template_is_rejected`, `settings_path_projects_default`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **string_operator**: `slugify`.
- **create_zettel_use_case and template_loader**: path from attributes, hooks before save, registry.

### Core Layer (Phase 1)
- **templates**: depends on [string_operator] for slugs and [create_zettel_use_case and template_loader] for hooks.
- **bim wiring**: depends on [create_zettel_use_case and template_loader] for `run_template_hooks`.

### Integration Layer (Phase 2)
- **docs**: depends on [templates, bim wiring].

## Implementation Phases

### Phase 0: Foundation
**Goal**: The engine honours template placement attributes and persists hook output.

**Tasks**:
- [ ] Add `StringOperator.slugify` with tests `slugify_strips_diacritics_and_joins_with_dashes` and `slugify_returns_empty_for_non_latin_title` (no deps) - Acceptance: `uv run pytest tests/lib/pybase/formatting/test_string_operator.py -q` passes.
- [ ] Read `folder`, `file_stem`, `default_tags`, `body_section`, `reference` and inject `slug` in `YamlTemplate`; document the optional attributes in the `ZettelTemplate` docstring; tests `yaml_reference_lands_in_data_reference`, `yaml_slug_is_available_in_sections` (no deps) - Acceptance: `uv run pytest tests/lib/zettel/templates/test_yaml_template.py -q` passes.
- [ ] Build the path from `folder`/`file_stem` in `prepare`, create the folder and run hooks before `save` in `execute`, add `path_projects` to `run_template_hooks` and the `set_parent_reference` and `set_illustration_link` handlers; tests `slug_template_writes_into_folder`, `slug_collision_fails_without_retry`, `hook_metadata_is_in_the_saved_file`, `project_dir_skipped_when_root_missing` (no deps) - Acceptance: `uv run pytest tests/lib/zettel/application/test_create_zettel_use_case.py tests/lib/zettel/test_template_loader.py -q` passes.

**Exit Criteria**: `uv run pytest tests/lib/zettel -q` passes with the fourteen existing templates untouched.

### Phase 1: Core
**Goal**: The eight vault templates exist and bim wires them.

**Tasks**:
- [ ] Rewrite `project.py`; add `contact.py`, `meeting_minutes.py`, `illustrated_note.py`, `youtube.py`, `book.yaml`, `problem_resolution_report.yaml`; delete `contact.yaml` and `meeting_minutes.yaml`; one test module per python template asserting the exact metadata keys, section headings and, for meeting-minutes, the title regex `^\d{4}-\d{2}-\d{2} \| .+ meeting minutes$`; update `test_discover_templates.py` for the new names (depends on: Phase 0) - Acceptance: `uv run pytest tests/lib/zettel/templates -q` passes.
- [ ] Add `BimSettings.path_projects`, `get_hook_runner(path_projects)`, update the three call sites, and the default-tag merge with the reserved-tag check in `CommandCreateNote`; tests `default_tags_come_first`, `reserved_tag_of_other_template_is_rejected`, `settings_path_projects_default` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/bim/test_create_note.py tests/tools/bim/test_settings.py -q` passes.

**Exit Criteria**: the two scratch-vault commands in Success Metrics produce the described files.

### Phase 2: Integration
**Goal**: Documented.

**Tasks**:
- [ ] List every template with its answers and placement in the "bim create" section of `docs/source/tools/bim.rst`; update the Create examples in `src/tools/bim/SKILL.md` (`-a deliverable=fix` replaces `-a dev_type=feature`, add contact, book, meeting, youtube examples); add `Added` (book, illustrated-note, youtube, problem-resolution-report templates; `path_projects`) and `Changed` (project, contact, meeting-minutes shapes) lines under `[Unreleased]` in `CHANGELOG.md` prefixed `**bim**:` (depends on: Phase 1) - Acceptance: `rg -c "dev_type" src/tools/bim/SKILL.md docs/source/tools/bim.rst` prints 0 for both and `rg -c "deliverable" src/tools/bim/SKILL.md` prints at least 1.

**Exit Criteria**: `uv run pytest -q` passes; `uv run ruff check src tests` and `uv run mypy src/lib/ src/tools/` are clean.

## Test Strategy

### Critical Scenarios
- **Happy path**: contact `ada lovelace` → Expected: `contact/ada-lovelace.md`, `title: Ada Lovelace`, tags `[person]`, photo line names `ada-lovelace.jpeg`.
- **Happy path**: project with `deliverable=fix`, `ticket=SR-1` → Expected: frontmatter has `resources` and `deliverable: fix`, backmatter lines in order `parent`, `ticket`, `us`, `psd`, folder `<path_projects>/<id>-probe` exists.
- **Happy path**: meeting `weekly sync meeting minutes` with `location=teams` → Expected: title `YYYY-MM-DD | Weekly sync meeting minutes`, `## Log` receives the body, GTD block present.
- **Edge case**: youtube `https://youtu.be/dQw4w9WgXcQ?t=1` → Expected: `source: https://www.youtube.com/watch?v=dQw4w9WgXcQ`.
- **Edge case**: `path_projects` missing on this machine → Expected: note written with `resources`, result warning names the missing root, exit 0.
- **Error case**: `--tags person` on a `note` → Expected: failure naming the `contact` template, nothing written.
- **Error case**: contact title `日本語` → Expected: empty-slug failure, nothing written.

## Risks

- **Resources URL form**: Templater encodes each path segment (`%2F` separators); bim keeps `Path.as_uri()`, which Obsidian opens the same way. Accepted deviation, noted in the docs.
- **Excalidraw body parsing**: the `# Drawing` line inside the `# Text Elements` body is how Excalidraw stores notes; bim's parser already meets such notes in the vault, and creation only writes sections verbatim.
- **Breaking template changes**: `dev_type`, `contact_type` and the `online` location disappear; the changelog lists them under `Changed` and the release is a minor bump.
