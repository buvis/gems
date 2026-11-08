# Design review: bim create scripting contract

## Findings

**1. cardinal-sin: JSON and exit-code contract has no versioning or compatibility rule**
- Evidence: "CLI and other adapters" and "Success metadata" define a flat JSON payload for scripts and a skill migration. The PRD calls it "contract v1", but the payload has no version field and no additive-only rule. The same change flips failed-result exits from 0 to 1 in eight commands, and "Risks" admits `metadata["path"]` changes from `Path` to `str`. Section "Risks" also expects 00119 and 00120 to add keys.
- suggested_fix: Pick a policy and state it in the design and docs. For example: keys are additive only, consumers ignore unknown keys, and any removal or retyping needs a new flag or major version. Optionally add a `"schema": 1` key now. Record the exit-code change as a documented breaking change in CHANGELOG and SKILL.md.

**2. blocker: post-save failure semantics are unbuildable and invite duplicate notes**
- Evidence: "CommandCreateNote" requires that a hook or readback failure "explicitly state that a note may already exist at the target". But `execute` raises from the hook before it returns the `Path` (the review-log question), so the command never learns the target. The command also treats `find_by_location`, `relative_to(vault_root)` and a broad `ValueError` catch as pre-save failures. `relative_to` can raise if `zettelkasten_path` in the use case is an unresolved symlink while the command resolves its own copy. Any of these returns `success=False`, exit 1 and `{"error": ...}` with no path or id, although the note exists. A script that retries then creates a duplicate.
- suggested_fix: In the use case, wrap hook failures as `RuntimeError(f"note saved at {path}, but hook failed: {exc}") from exc`, which carries the path in the message. Use the same resolved `zettelkasten_path` for the use case and the command. Treat metadata derivation after a successful save as success with `errors`, or build it from known values. Add `path` and `id` to the failure JSON whenever a note may exist.

**3. question: does the consistency service accept offset-faithful ids?**
- Evidence: "Identity fixers" gives `+02:00 → …120000` and `10:00Z → …100000` for the same instant. "Test strategy" keeps "consistency-service instant-equality coverage". If that service compares id to date by instant or in UTC, every note created with a non-UTC local default is flagged inconsistent. Existing vault ids were presumably UTC-derived, and no section covers how old and new ids coexist.
- suggested_fix: Read the consistency service and state what it compares. Change it, or add a test showing a local-offset note passes. Add a short compatibility paragraph on mixed UTC and local ids.

**4. non-blocker: dry-run and real metadata come from different sources**
- Evidence: "CommandCreateNote" sets `answers["tags"]` to a comma-joined string. Dry run takes `zettel.tags` from the in-memory prepared zettel, which may still be that string. Real create takes it from `find_by_location`, which parses YAML and applies `normalize_tags`. The table promises `list[str]` and `id` as `str(zettel.id)` in both cases.
- suggested_fix: Take `tags` from the validated list in the command for both paths. Add a test asserting identical key sets and types for dry run and real create.

**5. non-blocker: 0o600 placeholder may become the final note mode**
- Evidence: "CreateZettelUseCase" reserves with `os.open(..., 0o600)`, then relies on `atomic_write_text` replacing it. If that helper copies the mode of an existing target, every new note becomes 0600. That would be a silent regression for vault sync and shared access. The design does not say what the helper does.
- suggested_fix: Read `atomic_write_text`. Reserve with `0o666` (the umask applies) unless the helper is shown to ignore the target's mode. Add a test asserting the final mode equals the pre-change mode.

**6. non-blocker: frontmatter regex mishandles edge cases, and the source is then trashed**
- Evidence: `\A---\n[\s\S]*?\n---\n` does not match empty frontmatter (`---\n---\n`). It also misses a closing `---` at EOF without a trailing newline or with trailing spaces, and a BOM defeats `\A---`. A leading horizontal rule `---` with no frontmatter makes the lazy match swallow content up to the next `---`.
- suggested_fix: Use `\A---[ \t]*\n(?:[\s\S]*?\n)?---[ \t]*(?:\n|\Z)`. Read with `utf-8-sig`. Add tests for empty, EOF-terminated, HR-only and BOM cases.

**7. non-blocker: input size is unbounded, notably on the serve path**
- Evidence: "CLI and other adapters" reads `--body-file -` from stdin without a limit. "Source" reads a whole file without a limit. Serve forwards a request-derived `body` the same way. The design bounds retries and trash attempts but not input.
- suggested_fix: Add a `MAX_BODY_BYTES` constant, for example 1 MiB. Enforce it in the command so all adapters share it, and return a failed result when exceeded.

**8. question: scripted mode and template questions or empty tags**
- Evidence: "Preserve existing template question/default behavior" and "Existing no-flag incomplete invocations retain TUI behavior". It is unstated whether scripted mode prompts for unanswered template questions, which would hang when stdin carries the body or fail on EOF. `--tags ""` or `","` normalizes to an empty list, and it is unclear whether that clears template tags or falls back to defaults.
- suggested_fix: Specify that scripted mode never prompts and uses template defaults or fails. Specify that explicitly provided empty tags yield `[]`, not the template default, or reject them.

**9. non-blocker: hook output or logging can corrupt JSON stdout**
- Evidence: "CLI and other adapters" guarantees "exactly one parseable JSON object". Hooks run after save through `hook_runner`, and the "Risks" JSON note covers only template-discovery logging. Hooks or subprocesses that write to stdout would break the guarantee.
- suggested_fix: In JSON mode, run hooks with stdout redirected to stderr, or add a test with a noisy hook asserting stdout is a single JSON line.

**10. non-blocker: `ctx.exit(1)` can be swallowed, and source identity is not rechecked before the trash move**
- Evidence: Only sync is called out as needing the exit outside exception conversion. `click.exceptions.Exit` subclasses `RuntimeError`, so any `except Exception` around the other handlers swallows it. Separately, in "Trash", `os.link(source, destination)` follows symlinks on macOS. A source swapped to a symlink between ingestion and move would put an outside file's content in `.trash`. The review log defers only revision checks.
- suggested_fix: Audit each of the eight handlers for enclosing `except Exception` and test the exit code of each. Record `(st_dev, st_ino)` at ingestion and verify it, plus `not is_symlink()`, immediately before the move.

**11. non-blocker: `body_section` is a speculative seam**
- Evidence: "CreateZettelUseCase" reads `getattr(template, "body_section", None)`, but the same section says "No template protocol or YAML loader change is required", so nothing can set it in this PRD. It is an undeclared duck-typed contract, justified only by 00119 in "Risks".
- suggested_fix: Drop the lookup and always use section zero. Let 00119 add the attribute properly with its loader. If kept, declare it on the template type and test it with a real template.

**12. non-blocker: wikilink is not escaped**
- Evidence: the `wikilink` row is `[[{relative_path_without_md}|{title}]]`. A title containing `|` or `]]` yields a broken link.
- suggested_fix: Strip or replace `|`, `[` and `]` in the display title, and test it.

**13. non-blocker: the reservation race is tested only with mocks**
- Evidence: "Test strategy" patches reservation races. The real `O_EXCL` guarantee against concurrent creators is never exercised.
- suggested_fix: Add one test that starts two threads or processes behind a barrier on a tmp vault, with a pinned clock, and asserts two distinct files with no overwrite.

## Checked correct

- **Attempt accounting** ("CreateZettelUseCase"): one attempt per build, a sleep only when attempts remain, and a shared budget across existence and reservation losses give at most 5 builds and 4 sleeps. The invocation-local counter avoids mutable instance state.
- **Placeholder cleanup**: the `(st_dev, st_ino)` compare is consistent with the atomic replace changing the inode. A lost reservation is never unlinked, and `finally` covers `KeyboardInterrupt`.
- **Dry run**: `prepare` writes nothing, creates no directories and runs no hooks. The cost (up to 4 s of sleeps) is stated.
- **Source confinement**: the resolved-inbox-under-vault check blocks symlink broadening, and exclusion is checked before any read. The serve path adds a second confinement layer.
- **Rollback and recovery**: no schema or persistence-backend change, and the trash move is the recoverable path for sources. Secrets and authentication are not in scope for this change.
- **Alternatives and reuse**: each rejected helper (`resolve_collision`, `replace_section`, `normalize_tags`) has a stated reason, and alternative 2 is justified against 1 and 3.
- **Doc consistency**: "Unresolved questions: none" sits beside a logged open question (finding 2). Fix the wording when you address finding 2.
