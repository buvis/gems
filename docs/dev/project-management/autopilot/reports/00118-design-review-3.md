**Prior blockers**

1. **v1 compatibility policy: resolved.** "CLI and other adapters", final paragraph: keys and types are stable, additions are additive, consumers ignore unknown keys, and removing or retyping a key needs a new contract flag or a major release. It is documented in the CLI docs, skill and changelog. Residuals are in F3.
2. **Path-carrying post-save failure: resolved for hook and readback failures.** `CreateZettelUseCase` (final paragraph) and `CommandCreateNote` ("Once execute has returned a path") both emit `note saved at <path>, but ...`, and both keep the note and the source. Residuals are in F3 and F4.

**Findings**

**F1. blocker: id semantics change has no stated rule for existing notes or the consistency service**
- Evidence:
  - "Identity fixers" says `Set metadata["id"] = int(metadata["date"].strftime(...))` with no `id is None` guard, while the date branch is explicitly guarded.
  - "Architecture fit" and the Reuse inventory keep the ids in fixers run by `ZettelFactory.create`.
  - The test outline says "Keep consistency-service instant-equality coverage".
  - The old code converted to UTC. Vault notes with a non-UTC date offset therefore carry ids with different digits than the new rule produces.
  - The design never says whether fixers run when loading existing notes (`format`, `sync`, `show`, `find_by_location`).
  - It never says whether the consistency service reads id digits as UTC or as the date's own offset.
- Risk: if fixers run on load, `bim format` or `sync` can silently re-key historical notes and break links and filenames. Otherwise the consistency check reports every new non-UTC note as inconsistent. The vault ends up with two id conventions and no stated migration or compatibility rule.
- Fix:
  - State and test that the id fixer only fills a missing id (or runs only on the create path).
  - Specify how the consistency service interprets ids from both conventions.
  - Add a test that a note with a UTC-derived id and a +02:00 date keeps its id through format and sync.
  - Add a one-line note in the docs and changelog that ids now use the local wall clock.

**F2. non-blocker: readback creates an avoidable "saved but exit 1" path**
- Evidence: `CommandCreateNote`, "read the saved zettel through `repo.find_by_location`". Data flow step 5.
- Risk:
  - A parse failure on an unusual body (stray `---` lines) turns a successful write into exit 1, which invites script retries.
  - A concurrent sync or editor can change the note between save and readback, so the metadata describes someone else's content.
  - The design already uses a private `_prepare` helper to keep the public signatures.
- Fix: add a private `_execute` that returns `(Path, Zettel)` and let public `execute` return only the `Path`. Build metadata from the in-memory zettel. Keep readback only as an optional test assertion.

**F3. non-blocker: v1 contract leaves the failure channel loosely defined**
- Evidence: "CLI and other adapters", v1 paragraph; `{"error": message}` shape; the `note saved at <path>, but ...` messages.
- Risk:
  - The saved path exists only inside free text, so scripts must regex it. That regex becomes a de facto contract the policy does not cover.
  - There is no in-band version marker, so consumers cannot detect v1.
  - "A new contract flag" is not named.
  - The exit 0 to 1 change on `format`, `sync` and `show` sits outside the create contract and has no release classification.
- Fix:
  - Declare the `note saved at <path>,` prefix stable and the remainder free text.
  - Or add an optional `path` key to the failure object, which the additive-only policy permits. Confirm the PRD allows it.
  - Name the future opt-in flag.
  - Say which release level carries the exit-code change.

**F4. non-blocker: save can fail after the atomic replace, and the failure then carries no path**
- Evidence: `CreateZettelUseCase` cleanup ("remove only the placeholder... compare `(st_dev, st_ino)`"; "preserve a completed replacement").
- Risk: if `writer.save` raises after `os.replace` (for example a directory fsync error), cleanup correctly skips the unlink. The caller still gets a path-less `OSError` for a note that exists.
- Fix: in the save-failure handler, compare the current inode with the reservation inode. If they differ, raise `note saved at <path>, but save did not complete cleanly: <exc>`. Add a test.

**F5. non-blocker: up to 4 s of `sleep` on shared adapter threads**
- Evidence: the five-build, four-sleep budget in `CreateZettelUseCase`. "CLI and other adapters" says TUI and serve call the same command.
- Risk: a collision burst can freeze the Textual UI thread or block a serve event loop for 4 s.
- Fix: confirm serve and the TUI call the command in a worker or thread pool, and add a test or note. Otherwise inject a sleep callable.

**F6. non-blocker: body and source have no size cap**
- Evidence: `--body-file -`, `source` read, serve forwarding `body`.
- Risk: a network-facing serve endpoint accepts an arbitrarily large body into memory. The token and loopback bind mitigate this but are not stated as the accepted control.
- Fix: add a `MAX_BODY_BYTES` check in the command (one shared place), applied to body and source, returning a normal failed result. Or record explicit acceptance with the justification.

**F7. non-blocker: `ctx.exit(1)` inside a try block can be swallowed in the JSON path**
- Evidence: "CLI and other adapters". The design routes validation and constructor failures through the JSON path, and only calls out sync's placement.
- Risk: `click.exceptions.Exit` subclasses `RuntimeError`. A broad `except` around the command call in `create_note` can turn the exit into a second error object or exit 0.
- Fix: emit the JSON, leave the try block, then call `ctx.exit(1)`. Add a CLI test asserting exit code 1 and exactly one JSON object.

**F8. non-blocker: the empty placeholder is visible to readers and has no recovery path**
- Evidence: "Risks & edge cases" (abrupt kill leaves an empty file; "do not automatically steal it").
- Risk: between reservation and save, and permanently after SIGKILL, a zero-byte `<id>.md` sits in the vault. Scanners, sync tools and `bim list` or `load_all` can see it. Users get no cleanup instruction.
- Fix:
  - Test that the scanner and `load_all` tolerate a zero-byte note. They should return an `errors` entry, not crash.
  - Document manual removal of a zero-byte `<id>.md`.
  - Optionally add a hint when allocation hits a zero-byte file.

**F9. question: does `atomic_write_text` inherit the destination file's mode?**
- Evidence: reservation uses `0o600`; `save` replaces the placeholder.
- Risk: if the writer preserves the existing target's mode, every new note becomes `0600`, a silent permission change versus today's default.
- Fix: verify in `buvis.pybase.filesystem.atomic_write_text`. If it preserves mode, reserve with `0o666 & ~umask`, or chmod after the save, and add a test.

**F10. non-blocker: cleanup guard is slightly weaker than described**
- Evidence: owned-inode cleanup; `os.open` then close.
- Risk:
  - `(st_dev, st_ino)` must be captured via `fstat` before closing, and the open, fstat and try must be structured so a `KeyboardInterrupt` cannot land between them.
  - Inode numbers are reusable, so the comparison alone is not proof of ownership.
- Fix: record `fstat` inside the try, and require `st_size == 0` in addition to the inode match before unlinking.

**F11. non-blocker: source handling details**
- Evidence: "Read source as UTF-8"; the `\A---\n` regex; the `os.link(source, destination)` and unlink move.
- Risk:
  - A UTF-8 BOM defeats `\A---`.
  - The design does not say which path (given or resolved) is used for read, link and unlink, so a symlink inside the inbox can be moved or unlinked ambiguously.
- Fix: read with `utf-8-sig` and use the resolved path for read, link and unlink. Add a test with a BOM source and a symlinked source.

**F12. non-blocker: fallback heading uses `answers["title"]` before template defaults**
- Evidence: "initialize `[(f"# {answers.get('title', '')}", body)]` before the fixers".
- Risk: when the title comes from a template default or a fixer (the source-stem title is a params value, but other paths exist), the note gets an empty `# ` heading.
- Fix: derive the heading from the built data's title, or add a test for a template with no sections and no title answer.

**F13. non-blocker: dry-run and real-create `tags` may differ in type**
- Evidence: metadata table (`tags: list[str]`, `zettel.tags or []`). The dry run uses the unparsed prepared zettel, while real create uses the parsed readback.
- Risk: the prepared zettel may hold `"a,b"` as a string.
- Fix: normalize to `list[str]` in the command in both paths. Add a dry-run versus real tags equality test.

**F14. question: `vault_root = path_zettelkasten.parent` when the zettelkasten path is the vault root**
- Evidence: Interfaces › `CommandCreateNote`; Reuse inventory (`_create_project_dir` convention).
- Risk: for a flat vault, `inbox` and `.trash` resolve outside the vault. The "trash beneath the vault" check then confines to the wrong root.
- Fix: state the layout precondition and fail clearly if `<vault_root>/inbox` is absent when `--source` is used.

**Checked correct**

- Shared five-attempt budget with consistent accounting for existence checks and reservation losses (`CreateZettelUseCase`).
- `prepare` is side-effect-free apart from existence checks and sleeps, and dry run uses only `prepare` (`CommandCreateNote`).
- `execute` still returns `Path`, and hooks run only after a successful save.
- `finally`-based cleanup that never catches `BaseException` for hook normalization.
- Trash suffix search is bounded (`MAX_TRASH_ATTEMPTS = 1000`) and does not clobber. Post-save trash failures stay successful with `errors`.
- Atomic persistence is reused unchanged, and the lib does not import bim (Architecture fit; Reuse inventory).
- `CommandResult` discipline is kept, and the sanctioned console-output exception for JSON is stated.
- The tag grammar is precise, and the validator and the question handling do not overwrite each other.

**Already recorded in the review log, not repeated:** frontmatter regex edge cases, `body_section` duck typing, noisy hooks corrupting stdout JSON, concurrent allocation test coverage, and the explicit-empty-tags question.
