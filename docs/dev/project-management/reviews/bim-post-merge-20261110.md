# BIM post-merge review, 2026-11-10

## Scope and reviewers

Reviewed `2f6aee15..7cae3a37` from merged PR #269, limited to
`src/lib/buvis/pybase/zettel`, `src/rust`, `src/tools/bim`,
`tests/lib/zettel`, and `tests/tools/bim`. The existing 00118–00120
completion reviews remain the authority for earlier dispositions.

The user requested Claude after the coordinator could not locate the intended
`/code-review medium` workflow. Native Claude Sonnet 5.5 at high effort reviewed
the supplied complete diff and read relevant source through read-only tools.
Claude performed a medium-depth review directly; it did not execute the named
workflow or run tests. The session transcript identifies `claude-sonnet-5-5`,
session `72a54620-9351-4830-b93b-86c204883182`.

Codex independently reproduced findings, implemented fixes, and ran verification
in an isolated worktree using synthetic notes only. Claude then reviewed the
fix diff in the same review session. This is a post-merge code review, not a
replacement for an autopilot completion-review cycle.

Settled conventions remain unchanged: tags are flow lists before `type`,
written order is preserved, keys after `processed` retain insertion order,
and project fields reserve `completed`, `resources`, `deliverable`.

## Dispositions

| Finding | Disposition and evidence |
| --- | --- |
| C1: Daily-log `splitlines()` rewrites Unicode separators. | Fixed. Split on LF after `read_text` normalizes physical line endings. Five regression cases preserve U+2028, U+2029, NEL, vertical tab, and form feed; each failed before the fix. Existing CRLF test still passes. |
| C2: Home-directory expansion errors escape the create JSON/console contract. | Fixed. Catch `RuntimeError` around configured path expansion and scripted input preparation. Eight cases cover source/body/summary/settings in JSON and human output; each failed before the fix. The catch does not enclose result rendering, because Click's `Exit` also inherits `RuntimeError`. Conflict validation still precedes source expansion. |
| C3: Daily-log section-end scan mishandles mixed fence delimiters; heading scan accepts an info-bearing closer. | Deferred to a shared Markdown fence scanner follow-up. A tilde fence containing a backtick fence and `## Code heading` inserts the entry inside the example identically at `2f6aee15` and `7cae3a37`. The newer heading matcher also needs a proper closing-line rule. This patch does not claim complete CommonMark fence support. |
| C4a: Contact linking rewrites multiline inline code. | Fixed. Matching backtick runs can span a line break within a paragraph. The regression keeps the name inside code unchanged and links the subsequent prose occurrence. |
| C4b: Four-backtick fences containing three-backtick lines expose code to contact linking. | Deferred with C3. Executing the same synthetic example against the base and merged helpers produces the same wrong link. A shared fence scanner should protect complete fenced and indented code blocks. The review's performance concern was not measured and is not treated as a verified defect. |
| C5: Non-article CRLF source frontmatter survives stripping. | Rejected; Claude withdrew it on follow-up. `Path.read_text` normalizes CRLF before the regex sees the content. `test_source_frontmatter_is_stripped_and_file_trashed` already covers a CRLF source. |
| C6: Defaults outside a choice list, including an undeclared empty string, are rejected. | Rejected as intended validation. Resolved defaults and explicit inputs must obey declared choices. An optional answer can be omitted (`None`); accepting an invalid default would bypass validation. No bundled template needs an exception. Claude accepted this disposition. |
| C7a: Deduplication comments describe conversion to a set and back. | Deferred documentation maintenance. Python uses `dict.fromkeys`, Rust filters in original order; the comments predate the reviewed range. The order contract is pinned by tests. |
| C7b: Rust preserves duplicate numeric tags while Python deduplicates them. | Deferred pre-existing parity gap for malformed/non-string tag lists. Normal CLI tags are validated strings; this review does not broaden tag normalization. |
| C7c: `convert_markdown_to_preserve_line_breaks` remains exported but unused by the formatter. | Deferred API cleanup. Removing an exported helper is unnecessary for the preservation fix. |
| C8a: Cargo and frontend lockfiles include dependency changes. | Accepted existing PR scope. They are not silently described as Rust formatting-only changes. Rust test/fmt/clippy and repository CI cover the reviewed dependency state. No lockfile was changed by this patch. |
| C8b: Parity can accidentally use a stale extension. | Verified: a fresh editable build compiled and signed the worktree's CPython 3.15 extension, and the scoped suite includes the Rust/Python parity tests. |
| C8c: An `fstat` failure can leave an empty reserved filename despite the skill's no-write claim. | Kept the ownership policy settled in 00118 review R5 and pinned by `TestReservationInspectionFailures`; documented the empty-reservation exception in `bim --skill`. Removing a path without a verified inode could delete a replacement file. |
| X1: Per-key YAML dumps reuse anchor names across fields and make notes unreadable. | Fixed. A document-local counter assigns unique anchor names across dumps without changing field order, tag flow style, or other wrapping. A real parse/format/parse regression with aliases under two fields failed with duplicate `id001` before the fix, and now preserves metadata and stable output. |
| Follow-up C9: A stray backtick can protect prose across a blank line. | Fixed after Claude's patch review. Inline spans stop at blank lines. The stray-backtick regression failed before this adjustment and passes alongside the multiline-code test. |

No finding remains without a disposition. The deferred Markdown scanner,
non-string tag parity, and documentation/API cleanup are follow-up work, not
claims of complete support in this patch. Earlier recorded deferrals, including
article creation from the TUI and concurrent daily-log writes, remain unchanged.

## Verification

- Before fixes: scoped zettel/BIM suite, 2,203 passed.
- New regressions were observed failing before their respective fixes.
- After the main fixes: scoped suite, 2,218 passed; after C9, all 24 vault-link
  tests passed.
- Ruff lint and format checks passed; mypy passed across 576 source files.
- Rust: 36 tests passed; formatting and clippy with warnings denied passed.
- First full-suite run: 7,231 passed, 16 skipped, one expected failure, and one
  unrelated backup live-status failure. The execution environment had
  `TERM=dumb`; Rich emitted no status text even with `force_terminal=True`.
  The failing test passed with `TERM=xterm-256color`. No backup code was changed.
- Full-suite rerun with `TERM=xterm-256color`: 7,246 passed, 16 skipped,
  one expected failure. This run started before the final C9 adjustment;
  C9 was separately verified with the complete 24-test vault-link suite.
- `pre-commit run --all-files`: all five gates passed. The fix PR's check
  runs retain the CI evidence for the final committed revision.

Claude's patch review approved the YAML, daily-log, and error-rendering fixes;
its remaining low finding C9 was reproduced and fixed. Claude's review was
static; the executed evidence above comes from the coordinator.
