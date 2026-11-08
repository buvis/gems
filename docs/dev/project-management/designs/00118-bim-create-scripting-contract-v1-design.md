# Design: bim create scripting contract

PRD: `docs/dev/project-management/prds/wip/00118-bim-create-scripting-contract-v1.md`.

## Architecture fit

Keep the existing boundary: Click, TUI and serve adapters construct `CreateNoteParams` and call `CommandCreateNote`; the command calls interface-agnostic zettel use cases. Identity defaults remain domain fixers. Allocation, reservation and body insertion belong to `CreateZettelUseCase`. Tag validation, inbox handling and result metadata belong to the bim command. Rendering and process exit status belong to the adapters.

The project capsule confirms atomic persistence and shared command implementations. Keep `MarkdownZettelRepository.save` and its `atomic_write_text` unchanged: an exclusive empty reservation precedes its atomic replacement. No new persistence backend, library dependency on bim, or alternate note writer is needed. PRDs 00119 and 00120 own vault templates and links respectively; this design only provides their body-placement and metadata seams.

## Module placement

Edit existing files; no new production modules:

- `src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_date.py` and `set_default_id.py`: local date default and offset-faithful id.
- `src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py`: preparation, body insertion, shared attempt accounting, exclusive reservation and cleanup.
- `src/tools/bim/params/create_note.py`: body, source and dry-run fields.
- `src/tools/bim/commands/create_note/create_note.py`: formatter dependency, validation, source ingestion, dry run, metadata and trash move.
- `src/tools/bim/note_write_cli.py`: four flags, body-file/stdin adaptation, JSON output and failed-result exits for five note commands.
- `src/tools/bim/note_read_cli.py`: failed-result exits for format/sync/show and missing-query-spec exit.
- `src/tools/bim/tui/create_note.py` and `src/tools/bim/commands/serve/_actions.py`: inject `get_formatter()` into every `CommandCreateNote` construction. Serve forwards `body`, `source` and `dry_run` through the existing params/command boundary; confine request-derived source paths before forwarding.
- Existing tests named in the PRD, plus existing TUI/serve adapter tests where constructor expectations change.
- `src/tools/bim/SKILL.md`, `docs/source/tools/bim.rst`, `CHANGELOG.md`: document flags, payload, tag rules, failure exits and local ids. Add a concise scripted-create example to the existing bim section of `README.md`, as required by the capsule's CLI-documentation convention.

## Interfaces & contracts

### Identity fixers

Signatures remain `set_default_date(zettel_data: ZettelData) -> None` and `set_default_id(zettel_data: ZettelData) -> None`.

- When `metadata.get("date") is None`, assign `datetime.now().astimezone().replace(microsecond=0)`. Preserve any existing date.
- Set `metadata["id"] = int(metadata["date"].strftime("%Y%m%d%H%M%S"))`. Do not convert the date's timezone. A naive datetime keeps its wall-clock digits. A non-datetime raises `ValueError("Invalid date format")`; retain `ValueError("Invalid ID format")` for a failed numeric conversion.
- `2024-09-13T12:00:00+02:00` yields `20240913120000`; the same instant expressed as `10:00:00Z` yields `20240913100000`.
- Existing ids remain unchanged: `ZettelConsistencyService._DEFAULTS` delegates to `domain/services/base.py:apply_defaults`, which calls the id fixer only when `metadata.get("id") is None`. `ensure_consistency` has no id/date comparison. Keep that dispatch guard unchanged; mixed old UTC-derived and new local ids require no migration or re-keying. Test that consistency preserves an existing UTC-derived id alongside a non-UTC date.

### CreateZettelUseCase

Public signatures:

```python
MAX_ID_ATTEMPTS = 5

def prepare(
    self, template: ZettelTemplate, answers: dict[str, Any], *, body: str | None = None
) -> tuple[Path, Zettel]: ...

def execute(
    self, template: ZettelTemplate, answers: dict[str, Any], *, body: str | None = None
) -> Path: ...
```

Keep the constructor unchanged. Both methods use one preparation implementation. Use a private `_prepare` helper with the same template/answers/body inputs plus a remaining-attempt count, returning `(path, zettel, remaining_attempts)`; `prepare` supplies five attempts and discards the count, while `execute` retains the count across reservation retries. The counter is invocation-local, never mutable instance state.

Each candidate consumes one attempt before `template.build_data(answers)`. Inject the body into that fresh data, then run `Zettel(data)` and `ZettelFactory.create(zettel)`. Set `path = self.zettelkasten_path / f"{zettel.id}.md"` and `zettel.get_data().file_path = str(path)`. If occupied, sleep exactly one second before rebuilding if attempts remain. Exhaustion raises `FileExistsError(f"Zettel already exists: {path}")`. At most five builds and four sleeps occur across existence checks and reservation losses combined. A reservation loss consumes the candidate already built, not an additional attempt; sleep once before the next rebuild. A fixed-date template gets the same five attempts and fails without special origin detection.

`prepare` does not create directories, reserve files, save, or run hooks. Its existence checks and collision sleeps are permitted in a dry run.

For a nonempty normalized body, normalize `\r\n` to `\n`, remove leading whitespace-only blank lines, and apply `rstrip()` to the whole body. Preserve indentation of its first content line and internal whitespace. Find the first section whose heading exactly equals `getattr(template, "body_section", None)`; if absent, select section zero. Append with one blank line between existing nonempty section content and the supplied body. Preserve all other sections. If the template supplied no sections, initialize `[(f"# {answers.get('title', '')}", body)]` before the fixers. `body=None` or a body that normalizes to empty leaves template content unchanged. No template protocol or YAML loader change is required in this PRD.

For an available candidate, `execute` calls `os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)`, then closes the descriptor. Only a `FileExistsError` from reservation counts as a retryable collision. Call `writer.save(zettel)` once after reservation succeeds. The writer retains atomic replacement of the placeholder. Run `hook_runner(template.hooks(), zettel.get_data(), self.zettelkasten_path)` only after the save returns successfully, preserving today's order. Return the saved `Path`.

Use `finally` cleanup for any exit before save succeeds, including `KeyboardInterrupt`: close any open reservation descriptor and remove only the placeholder owned by this invocation. Compare its original `(st_dev, st_ino)` before unlinking so cleanup cannot delete a file that has replaced it. After `save` returns, retain the note on hook failure. Normalize ordinary hook exceptions with `raise RuntimeError(f"note saved at {path}, but hook failed: {exc}") from exc`; never catch `BaseException` for hook normalization. Never unlink an occupied path whose reservation this invocation lost. Process termination that cannot run `finally` may leave a zero-byte reservation; do not automatically steal it.

### CreateNoteParams and CommandCreateNote

Keep existing fields and append:

```python
body: str | None = None
source: Path | None = None
dry_run: bool = False
```

The constructor becomes:

```python
def __init__(
    self,
    params: CreateNoteParams,
    path_zettelkasten: Path,
    repo: ZettelRepository,
    templates: dict[str, Any],
    hook_runner: Any,
    formatter: ZettelFormatter,
) -> None: ...
```

`execute(self) -> CommandResult` remains the shared entry point. Resolve `path_zettelkasten` and derive `vault_root = path_zettelkasten.parent`. Preserve the existing constructor directory check and template question/default behavior.

Before template construction, split `params.tags` on commas; strip each item, remove one leading `#`, lowercase it, drop empty items, and deduplicate in first-occurrence order. Accept only `re.fullmatch(r"[\w-]+(/[\w-]+)*", item)` with no `re.fullmatch(r"[\d/]+", item)`. Thus Unicode word characters, underscores and nesting are accepted; whitespace, repeated `#`, punctuation and purely numeric nesting fail. Return `CommandResult(success=False, error=f"invalid tag '{item}': use letters, digits, '-', '_', and '/' for nesting")` for the cleaned invalid item. Supply the comma-joined normalized string in `answers["tags"]` when tags were explicitly provided; do not add it when `params.tags is None`. Question handling must not overwrite normalized `tags` with an unvalidated answer.

Reject `params.body is not None and params.source is not None` before reading either input. For source input, resolve the path and require an existing regular file, suffix `.md`, and containment under the resolved `<vault_root>/inbox/`. Resolving an inbox symlink must not broaden the allowed vault root; check that the resolved inbox itself remains under `vault_root`. Invalid input returns exactly `--source must be a Markdown file inside <vault_root>/inbox`, replacing `<vault_root>` with its absolute path. Do not import server middleware into the command.

Read source as UTF-8, normalize CRLF, and remove at most one leading frontmatter block matching `r"\A---\n[\s\S]*?\n---\n"`. Use its remaining text as `body`. When `params.title is None`, use the source file stem before the usual title fixers. Do not overwrite an explicit title. After this derivation, missing type or title keeps the existing `zettel_type and title are required` error. An unknown template keeps `Unknown template: <name>`.

For `dry_run=True`, call `use_case.prepare(template, answers, body=body)` only and format its zettel using `PrintZettelUseCase(self.formatter).execute(zettel.get_data())`. No reserve, save, hooks, source move, or trash-directory creation occurs. For a real create, call `use_case.execute(template, answers, body=body)` and read the saved zettel through `repo.find_by_location(str(path))` to build metadata from the final saved data rather than a second independently prepared candidate.

Success metadata is a flat JSON-compatible dictionary:

| Key | Type and value |
| --- | --- |
| `id` | `str(zettel.id)` |
| `type` | saved/prepared zettel type, a string |
| `title` | saved/prepared zettel title, a string |
| `tags` | `list[str]`, using `zettel.tags or []` |
| `path` | absolute resolved path as `str` |
| `relative_path` | `path.relative_to(vault_root).as_posix()` |
| `wikilink` | `f"[[{relative_path_without_md}|{title}]]"` |
| `dry_run` | `True`, present only on dry run |
| `content` | formatted Markdown string, present only on dry run |
| `trashed_source` | absolute destination string, present after a completed source move |
| `errors` | `list[str]`, present when post-save source cleanup has a problem |

For example: `relative_path="notes/20261108134925.md"`, `wikilink="[[notes/20261108134925|Title]]"`. Do not add a `date` field to this payload: compare id/date using the written note's frontmatter in acceptance checks. Real success retains `output=f"Created {path}"`.

After save and metadata readback succeed, move a source into `<vault_root>/.trash/`. Resolve and confine the trash directory beneath the vault before creating it. Try `<name>`, then `<stem> 1<suffix>`, `<stem> 2<suffix>`, up to `MAX_TRASH_ATTEMPTS = 1000` candidates total. On exhaustion retain the source, keep success, append a cleanup error and omit `trashed_source`. Use the existing no-clobber move pattern (`os.link(source, destination)` then `source.unlink()`) so a concurrent destination collision retries a suffix without overwriting data. A link/move failure, including cross-device failure, is post-save: keep `success=True`, keep the note, append the error to metadata `errors`, and omit `trashed_source` unless removal completed. Never remove an existing trash entry. A failed source unlink may leave both files; report their paths.

Catch expected `OSError`, `UnicodeError`, `ValueError` and the normalized hook `RuntimeError` before or during creation and return a failed result with a useful message. Do not catch `BaseException` at the command boundary. Pass the command's resolved zettelkasten path into the use case so metadata derivation uses that same root. A hook failure preserves the exact `note saved at <path>, but hook failed: <error>` message. Once execute has returned a path, catch ordinary readback or metadata failures separately and report `note saved at <path>, but metadata failed: <error>`. Both failures retain the saved note and source; this explicit path tells scripts to inspect that note instead of blindly retrying. Keep the PRD's failure JSON shape `{"error": message}`. Do not broaden this PRD into a hook transaction redesign.

### CLI and other adapters

Add Click options `--body-file PATH`, `--source PATH`, `--dry-run` and `--json` to `create_note`. Use plain string paths with validation inside the callback, avoiding parse-time `exists=True` checks. `--body-file -` reads text from stdin; other body files are read as UTF-8 and passed in `CreateNoteParams.body`. Pass source paths without reading them in the adapter. Check mutual exclusion before opening a body file or source. In human mode report this through `console.panic`; in JSON mode emit the failure object below and exit 1.

Explicit scripting flags (`--body-file`, `--source`, `--dry-run`, `--json`) select the command path even when required fields are absent, producing a command error rather than starting a TUI. `-t` plus `--source` is sufficient without `--title`. Existing no-flag incomplete invocations retain their TUI behavior. `--list` retains its current human listing; reject combining `--list` with `--json` through the JSON failure path rather than emitting non-JSON lines.

With `--json`, successful create/dry-run prints exactly `json.dumps(result.metadata, ensure_ascii=False)` through `click.echo` plus its final newline. Failure prints exactly `json.dumps({"error": message}, ensure_ascii=False)` through `click.echo` and exits 1. Route callback validation, body-read failures and constructor failures through that same path. Do not call `console.report_result`, success messages, or the TUI in JSON mode. This payload is the PRD's explicit exception to the console-output invariant. Unknown-template output is exactly `{"error": "Unknown template: nonexistent"}` with exit 1.

Without JSON, real create uses the existing `Created <path>` reporting. Dry run prints metadata `content` with `console.print(mode="raw")`, without a Created line. Each failed `CommandResult` is rendered first and then followed by `ctx.exit(1)` in `create_note`, `import_note`, `edit_note`, `archive_note`, `delete_note`, `format_note`, `sync_note`, and `show_note`. Place sync's exit outside infrastructure exception conversion. The `query` branch with neither `-Q` nor `-q` reports its existing message and then calls `ctx.exit(1)`. Do not change cancel/confirmation exits or invent a broad interactive-error overhaul.

The scripting contract is version 1. Its keys and types are stable; future additions are additive and consumers must ignore unknown keys. Removing or retyping a key requires a new contract flag or a major package release. Document this policy and the failure-exit behavior change in the CLI docs, agent skill and changelog; do not add an unrequested schema key.

All three `CommandCreateNote` callers inject `formatter=get_formatter()`. TUI and WebUI continue consuming `CommandResult` and the existing result serialization. Serve's existing source confinement plus the command's narrower inbox check both apply; body and dry-run have no alternate implementation in adapters.

## Data flow

1. CLI parses flags and reads body-file/stdin; API/TUI construct the same params. The command validates tags, source confinement and required fields, then gathers template answers.
2. The use case builds fresh template data, appends normalized body, runs domain fixers, and checks the id path. Collision checks and reservation losses consume one shared five-candidate budget.
3. Dry run returns the prepared candidate to `PrintZettelUseCase` and returns metadata/content without writes.
4. Real create exclusively reserves the candidate, atomically saves through the existing repository, runs hooks, and returns `Path`.
5. The command reads the saved note through the existing repository, derives metadata, and moves a source to recoverable trash. Post-save trash failures remain successful results with `errors`.
6. The adapter emits the requested representation and maps failed results to exit 1. No library component emits terminal output.

## Reuse inventory

Sweep used the installed rationalizations catalog's verb/noun synonyms: `format|render|serialize|strftime` with `date|timestamp`; `build|create|make|prepare|reserve|retry|collision` with `id|timestamp`; `normalize|validate|check|verify|is_valid` with `tag`; `read|parse|load|strip|move|rename|trash` with `body|source|frontmatter|section`; and `format|render|serialize|print|json|dry_run` with `CommandResult`. Searches covered `src/lib` and `src/tools/bim`; known existing symbols confirmed the search paths.

- `.../zettel/domain/entities/zettel/fixers/set_default_date.py:set_default_date` and `set_default_id.py:set_default_id`: edit in place; do not add a second identity generator.
- `.../zettel/application/use_cases/create_zettel_use_case.py:CreateZettelUseCase` and `.../zettel/domain/services/zettel_factory.py:ZettelFactory.create`: retain construction/fixer pipeline and move its allocation check into shared preparation.
- `.../zettel/infrastructure/persistence/markdown_zettel_repository/markdown_zettel_repository.py:save` and `buvis.pybase.filesystem.atomic_write_text`: reuse atomic persistence unchanged. `find_by_location` supplies final metadata without changing `execute`'s return type.
- `.../zettel/application/use_cases/print_zettel_use_case.py:PrintZettelUseCase.execute` and `bim.dependencies.get_formatter`: reuse dry-run rendering and dependency wiring.
- `.../zettel/domain/value_objects/zettel_data.py:ZettelData.sections`: mutate its existing `list[tuple[str, str]]` representation. `bim/commands/shared/sections.py:replace_section` replaces rather than appends, and the library cannot import bim; do not reuse this tool helper for body insertion.
- `.../zettel/infrastructure/persistence/template_loader.py:_create_project_dir`: reuse its `zettelkasten_path.parent` vault-root convention and retain hook timing.
- `src/tools/bim/commands/doc/migrate/migrate_layout.py`: reuse the established `os.link`/unlink no-clobber move pattern for trash; its migration-specific method is unsuitable as a shared API.
- `src/tools/bim/commands/doc/shared/naming.py:resolve_collision`: inspected; its 60 synthetic timestamp increments, PDF/zettel pair checks and directory creation violate this PRD's five real-clock rebuilds and no-write preparation. Keep separate use-case allocation, without importing doc business logic.
- `.../zettel/infrastructure/persistence/file_parsers/parsers/markdown/helpers.py:parse_metadata` and `front_matter_preprocessor.py:normalize_tags`: inspected; these parse existing note YAML and accept a different grammar. They must not silently reinterpret input tags or parse source metadata that must be discarded.
- `src/lib/buvis/pybase/result.py:CommandResult`, `to_dict` and `notify_result`: retain result boundary and API/TUI presentation. CLI JSON intentionally serializes flat metadata instead of the full `to_dict` envelope.
- No matching strict input-tag validator or source-to-trash suffix helper found; greps tried `normalize|validate|check|verify|is_valid` plus `tag`, and `move|rename|trash|collision` plus `source|file` in `src/lib` and `src/tools/bim`. Implement small private command helpers, without a general utility framework.

## Alternatives considered

1. **Smallest diff: edit defaults and add flags around current execute.** Retains check-then-write races, duplicates dry-run preparation, and cannot reliably report the actual winning candidate. Insufficient for the PRD.
2. **Chosen: extend the existing use case and command.** Shared candidate preparation, exclusive reservation and existing repository/formatter reuse add only the required seams. Saved-note readback avoids changing the public `Path` return contract or adding hidden result state.
3. **Introduce an allocation service, richer create result, and generalized transactional writer.** Could eventually unify doc allocation and template hooks, but adds public abstractions and forces unrelated callers to migrate. Defer until a concrete second compatible consumer exists.

## Risks & edge cases

- Local ids repeat during DST fall-back and templates can pin dates; five real-clock rebuilds fail safely rather than fabricating a future date. A dry-run id is a preview, never a reservation promise.
- Exclusive reservations coordinate creators using this protocol. An abrupt kill can leave an empty file; allocation treats it as occupied. Atomic writer replacement changes the placeholder inode, so failed-save cleanup must preserve a completed replacement.
- Hooks still run after persistence. Existing project hooks mutate in-memory resources after the write; PRD 00119 owns changing that timing. Hook/readback failures can leave a created note and must name that possibility.
- Source paths and `.trash` can contain symlinks; resolve and check confinement before filesystem operations. Confinement here follows the repo's existing resolved-path policy, not a new descriptor-relative filesystem sandbox.
- No-clobber hard-link moves can fail across mounted subtrees or filesystems without hard-link support. The note remains successful and the source remains available with a reported cleanup error. A future source-relocation requirement may justify a copy-plus-exclusive-destination fallback.
- Existing consumers comparing `metadata["path"]` to `Path` need updated expectations: this PRD deliberately makes it a JSON-compatible absolute string.
- Likely next changes are 00119's vault templates/body-section selection and pre-save hooks, 00120's link resolution, and the create-note skill migration. The optional `body_section` attribute, flat metadata and unchanged public Path return provide those seams without implementing them early.
- JSON guarantees cover the create callback and its expected failures. Template discovery currently uses library logging for malformed templates; tests must verify normal configured operation stays silent. Do not add unrelated logging infrastructure changes.

## Test strategy outline

- Exercise old regressions first: local-offset id conversion, existing UTC/default-date assumptions, failed command exit 0, same-second collisions, and missing machine output. Keep the existing public-call tests while updating formatter injection and string metadata expectations.
- Fixer tests cover local aware defaults, preserving explicit dates, positive/negative offsets, naive dates, invalid date values and equal instants with different wall-clock ids. Keep consistency-service instant-equality coverage.
- Use-case tests patch sleep/clock/template builds for collision progress, fixed-date exhaustion, reservation races, and mixed existence/reservation collisions. Assert five total builds, at most four sleeps, no dry-run writes, no duplicate save, no hooks before save, correct body section/fallback/normalization, and owned-reservation cleanup on save failure and `KeyboardInterrupt`.
- Command tests cover Unicode/nested tags, leading hash cleanup, case-insensitive deduplication, invalid spaces/punctuation/numeric paths, unchanged question defaults, body/source exclusion, confined sources and symlink escapes, exact frontmatter stripping, explicit versus inferred title, suffix collisions, source move errors, and full flat metadata. Use real scratch repository/formatter coverage for at least one create and dry run so readback is tested rather than inferred from mocks.
- CLI tests assert exactly one parseable JSON object, Unicode and long unwrapped values, no console calls in JSON mode, JSON constructor/validation/read failures, unknown-template exact error, stdin, flag exclusion before reads, scripted missing-field failure without TUI, dry-run raw output, and preserved interactive fallback.
- At draft time `rg -c 'success=False' tests/tools/bim/test_bim_cli_handlers.py tests/tools/bim/test_note_read_cli.py` returns 7 and 1. Recount during implementation and change the corresponding failed-result exit assertions to 1; add missing handler cases, including query without a spec. Verify TUI and serve constructor wiring and request-derived source confinement.
- Run the PRD's targeted pytest files, then `uv run pytest tests/lib/zettel -q` and `uv run pytest tests/tools/bim -q`. Final gates are `uv run pytest -q`, `uv run ruff check src tests`, and `uv run mypy src/lib/ src/tools/`. Use the capsule's documented isolated environment if host configuration affects the run.
- Scratch-vault acceptance checks verify JSON tags `["a"]`, local id/date digits from the saved frontmatter, distinct files for two same-second creates, failure exit 1, and zero filesystem changes for dry run. Check both agent and human documentation mention `--json`; ensure the stale `still exits 0` sentence is removed.

Unresolved questions: recorded non-blocking questions remain in the review log; no unresolved planning blockers.

## Review log

dispatch 1 (claude): cardinal-sin 1, blocker 0, non-blocker 3, question 1
Host adaptation: native gpt-6.1-sol/high, isolated design_review_1. Fixed unbounded trash suffix retries with MAX_TRASH_ATTEMPTS = 1000.
Non-blocker: source revisions may change between ingestion and cleanup; revision checks deferred.
Question: hook failures occur before execute returns its path; supported exception normalization and path reporting need care during implementation.
Checked correct: shared allocation budget, owned-inode cleanup, and side-effect-free dry run.

dispatch 2 (codex): cardinal-sin 1, blocker 1, non-blocker 9, question 2
Host role swap: external Anthropic Sonnet via installed use-sonnet wrapper, high effort requested through CLAUDE_CODE_EFFORT_LEVEL, no tools; output docs/dev/tmp/design-00118-dispatch-2-output.md. Fixed contract version policy and post-save path-carrying hook/readback failures; retained the PRD error-only JSON shape.
Non-blockers retained: dry-run versus parsed tags types; reservation mode; exact PRD frontmatter regex edge cases; body size; noisy hooks; handler exits/source revision race; body_section duck typing; wikilink display punctuation; real concurrent allocation test coverage. These are recorded concerns, not authorization for scope expansion. The regex, body_section and wikilink format are PRD-pinned.
Questions retained: consistency service compatibility with local ids; scripted defaults and explicit empty tags. Test the PRD contract using the existing fixer/template behavior.

dispatch 3 (codex): cardinal-sin 0, blocker 1, non-blocker 11, question 2
Host role swap: external Anthropic Sonnet via installed use-sonnet wrapper, high effort requested through CLAUDE_CODE_EFFORT_LEVEL, no tools; output docs/dev/tmp/design-00118-dispatch-3-output.md. Prior two blockers verified resolved. F1 rejected with source evidence: domain/services/base.py:apply_defaults guards existing ids, and ZettelConsistencyService.ensure_consistency never compares id/date digits. Clarified existing behavior above; no migration is needed.
Non-blockers retained: readback failure/revision window; failure prefix versioning; save failure after replace; synchronous collision sleeps; body size; JSON exit placement; abandoned reservation recovery; cleanup identity; source encoding/path details; empty-section heading; dry-run tags. Questions retained: placeholder mode and configured vault layout. These remain review observations and receive normal contract tests where applicable.
Open cardinal sins/blockers: none. All three dispatches contained section-anchored findings; no weak dispatches.
