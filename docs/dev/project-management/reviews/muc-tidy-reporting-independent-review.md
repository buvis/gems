# muc tidy reporting: independent review

Date: 2026-11-10
Initial implementation: `0cc1059e`
Reviewer: native Claude CLI, verified model `claude-sonnet-5-5`, explicit high effort.
Session: `df198c90-ef2f-47e9-bfe1-f3cb737ae51a`.
Isolation: fresh session, tools disabled, supplied requirements, commit diff and full relevant sources; no implementer conversation history. Two follow-up reviews examined corrections.
Final verdict: **no remaining actionable findings**. No Critical or High findings in the initial review.

## Disposition

- Fixed terminal-width-sensitive CLI assertions with `COLUMNS=500`.
- Fixed emoji expansion in filenames/messages with opt-in `ConsoleAdapter.report_result(literal=True)`. Only the trusted marker uses markup; user text is appended directly to Rich Text. Existing callers keep their default behavior.
- Reproduced a repeated-trailing-backslash loss in the intermediate escaping implementation; replaced it with direct Text append and added regression cases. Final correction independently reviewed.
- Added explicit assertions for the existing orphan-unlink failure test.
- Removed the extra changelog blank line.
- Rejected the suggestion to revert string comparison for case-only renames: `PureWindowsPath('track.MP3') == PureWindowsPath('track.mp3')` is True, while the names differ. Reviewer withdrew the finding.
- Traversal exceptions remain outside the stated per-item recovery policy; redesigning safe traversal is separate work.
- Literal marker layout uses existing marker/style constants; optional formatter deduplication is deferred because the current layouts match and no functional issue was found.

## Deferred pre-existing behavior

These are recorded for separate work, not introduced by this reporting change:

- Rename collisions can overwrite the destination on POSIX. Consider warn-and-skip with same-file handling; changing cleanup decisions is outside the requested reporting scope.
- `muc cover` and `muc limit` do not yet opt into literal result rendering.
- `.stfolder` protection applies only to direct children.
- Configured junk extensions are not normalized to lowercase.
- Metadata application can partly succeed before an error; the helper retains the AppleDouble file for recovery.
- Traversal errors can abort a stage, and Python rglob can silently omit inaccessible paths.

## Verification

- `.venv/bin/python -m pytest tests/tools/muc tests/lib/pybase/adapters/test_console_adapter.py -q`: **155 passed**.
- `.venv/bin/python -m mypy src/lib/ src/tools/`: passed, 576 source files.
- Targeted ruff lint/format and `git diff --check`: passed.
- Tests ran on macOS/Python 3.15. Native Windows behavior was not executed.
- One initial combined run had an unexplained `muc --help` failure. Standalone reproduction exited 0; the unchanged combined rerun passed, as did the final suite. The reviewer found no connection to the result-rendering change. Record this if it recurs rather than treating retries as proof of absence.
- Reviewer validation was static; test execution and finding reproduction were performed by the implementer.

## Evidence

- prompt.txt SHA-256: `00abf7f7e2241dfa179bac9a2d918b73dda907047af1f656c9c8736a71a49299`
- followup.txt SHA-256: `0c9ee5e6aaf18fce8142879c9dce5de447bbf701953c763202fa0f4784b99e53`
- final-prompt.txt SHA-256: `5b96d5525714a811d540a0185d002caa1348394f3c2131fe1205257c31940654`

### Initial review

No blocking issues. I found no regressions that lose data or break the stated error policy, and no Critical or High findings. This is read-only reasoning from the diff and the supplied sources. I ran nothing, so Rich wrapping, rglob behavior across Python 3.11–3.14, and Windows behavior are unverified.

## Requirement coverage

- **Helpers return results instead of logging:** met. `logging` is gone from all five helpers.
- **Aggregation into `CommandResult.info` and `warnings`:** met.
- **Console rendering and exit status 0:** met. `report_result` never exits on warnings.
- **Recoverable failures don't abort later work:** met per file or directory.
- **Plain-text programmatic results with literal filenames in the CLI:** met via `escape()` in `cli.py:89-97`. Trailing and doubled backslashes (Windows paths) are handled correctly by Rich's `escape`.

## Findings (regressions or new code)

1. **Low – `tests/tools/muc/test_tidy_reporting.py:105-130`, Rich line wrapping.** The CLI tests assert substrings like `"[bold].txt" in result.output` against output that Rich wraps at 80 columns under `CliRunner`. A macOS `tmp_path` is about 100 characters, so the path is folded mid-word. The fold position depends on tmp path length, so a fold landing inside `[bold].TXT` would fail the test on one machine and pass on another.
   - **Fix:** set `COLUMNS=500` via `monkeypatch.setenv`, or assert on `result.output.replace("\n", "")`.

2. **Low – `cli.py:89-97`, emoji codes.** `escape()` covers markup only, and `console.print` also expands `:name:` emoji shortcodes. A file named `a:heart:b.mp3` is displayed with an emoji, which breaks the "literal filenames" requirement for that edge case.
   - **Fix:** escape that case too, or render these messages as `Text` instead of markup strings.

3. **Low – traversal outside the `try`.** The `for ... in safe_rglob(...)` iteration and `sorted(safe_rglob(...))` in `remove_empty_directories.py:20` sit outside the per-item `try`. An `OSError` raised by the walk itself (not by an item) still aborts the stage. Rglob mostly swallows `PermissionError`, so this is narrow. Separately, a non-`OSError` exception in any stage drops the info and warnings already collected.
   - **Fix:** none needed for the stated per-item policy. If you want it, wrap each stage in `CommandTidy` and convert the exception to a warning.

4. **Low – `tests/tools/muc/test_merge_mac_metadata.py:105-118`.** `test_oserror_on_unlink_orphan_is_caught` now exercises a changed path (orphan unlink failure used to be silent, now it warns "Kept …") but asserts nothing. The parametrized test in the new file covers the behavior, so this is only a weak leftover. Capturing `result` and asserting one warning would tighten it.

5. **Trivial.**
   - `lowercase_file_extensions.py:26` changed `new_path != file_path` to `new_name != file_path.name`. It is equivalent and unrelated to the task, so it can be reverted.
   - The `CHANGELOG.md` entry adds a blank line between bullets, unlike the surrounding entries.

## Pre-existing (not regressions)

- **Medium – silent overwrite on rename.** `lowercase_file_extensions.py:27` and `rename_equivalent_extensions.py:39`: if `song.mp2` and `song.mp3` both exist, `Path.rename` replaces `song.mp3` on Linux and macOS with no warning. On Windows it raises `FileExistsError`, which is now a warning, so behavior differs by platform. The new output reports this as a plain "Renamed" action, which hides the overwrite.
  - **Smallest fix:** warn and skip when `new_path.exists()` and it isn't the same file. The task said to preserve existing cleanup behavior, so this belongs in a separate change.
- **Low – other commands still break on brackets.** `muc cover` and `muc limit` still pass unescaped paths into markup through `report_result`. The CLI-side escape means the console adapter itself is still unsafe. A shared fix would be to escape inside `report_result`. That is a wider change.
- **Low – `.stfolder` guard.** `delete_by_extension.py:22` only protects direct children of `.stfolder`.
- **Low – junk extension matching.** `extensions_to_delete` is compared against a lowercased suffix but is not lowercased itself.
- **Low – partial merge.** `merge_mac_metadata` can apply some xattrs and then fail, leaving the `._` file in place.

## Other checks

- **Tests:** coverage is good. Each helper has a failure-continues test, and the stage order, aggregation and warning-only exit are tested.
- **Interface separation:** `CommandTidy` has no console, `sys.exit` or logging, so the layering is preserved.


### First correction review

**Verdict: no remaining actionable findings.** I ran nothing, so this is reasoning from the diff and the earlier sources.

**Prior findings**
- **Rich wrapping in tests:** fixed. `COLUMNS=500` takes effect because, as I recall Rich's `Console.size`, it reads `COLUMNS` from `os.environ` on each access. That holds unless both `COLUMNS` and `LINES` were exported when the module-level console was created.
- **Emoji codes:** fixed. `Text.from_markup(..., emoji=False)` after `escape()` keeps `:heart:` literal. The new CLI test would fail without the fix, since the default path expands `:heart:`.
- **Orphan unlink test:** now asserts the warning and empty info.
- **Changelog blank line:** fixed.
- **Case-only rename guard (`new_name != file_path.name`):** I withdraw my objection. Your evidence is right: the original `new_path != file_path` is a case-insensitive comparison on Windows, so it would skip case-only renames there. The new guard is an improvement.
- **Traversal and rename overwrite:** accepted as recorded for separate work.

**The `literal=True` path**
- **Default callers:** `emit` calls the same `success`/`warning`/`failure` with the same arguments as before, so their behavior is unchanged. `literal` is keyword-only and last, so the signature stays compatible.
- **Escaping:** `escape()` is applied before the formatter wraps the text in its style tags, which is the right order. Rich's `escape` also handles a message ending in a single backslash. The only gap is a message ending in three or more backslashes, which is not a realistic path or exception text.
- **Text path:** `Text.from_markup` parses the same marker and style markup as the string path. Rich's repr highlighter does not run on `Text`, so paths lose the faint auto-colouring in literal mode. That is cosmetic, and arguably correct for literal output.
- **Callbacks:** `on_success` and `on_failure` receive the unescaped result, as the docstring says. `success_msg` and `failure_msg` are also treated as literal when `literal=True`, which also matches the docstring. Neither is a problem.
- **Lib test:** it covers backslash plus bracket plus emoji, both success and failure branches, and checks the input result is not mutated.
- **Suppression comment:** the new suppression on `report_result` follows the existing `print_side_by_side` pattern and carries a reason.

**Validation limits**
- Not run by me: your 151 passing tests, mypy and ruff are your report only.
- The transient `muc --help` failure is unexplained. I see no link to this diff, since `--help` never reaches `report_result`. If it recurs, check for order-dependent state or an environment variable fixed on the module-level console.
- The lib test's `"✔" in output` check on Windows depends on how the adapter's UTF-8 stdout wrapper interacts with `capsys`. I could not verify that.


### Final correction review

**Verdict: no remaining actionable findings.** I ran nothing, so this is reasoning from the diff and the earlier sources.

**The rendering change is correct.**
- `Text.from_markup(f" {marker} ")` parses only the trusted marker constants (`CHECKMARK`, `WARNING`, `CROSSMARK`). They contain no emoji codes or user text.
- `.append(message, style=style)` adds plain text and never parses markup or emoji. That removes the escape/trailing-backslash problem you reproduced. It also removes the cases I flagged before, such as backslashes before a tag and an odd number of trailing backslashes, because no user text goes through any parser.
- `append` returns the same `Text`, so `self.render(...)` receives a `Text`.
- The layout (leading space, marker, space, styled message) matches `format_success`, `format_warning` and `format_failure`. The style strings such as `"bold light_salmon3"` are valid for `append`.
- Default callers still call `self.success`, `self.warning` and `self.failure` with the same arguments, so they are unaffected. The unused `escape` import was removed from `console.py`, so lint stays clean.
- Tests now cover the one- and two-backslash cases that failed before, on both the success and failure branches. The assertions would catch a lost backslash.

**Non-blocking note (optional).** The literal path hard-codes the `" {marker} "` layout and the marker/style pairs instead of reusing the `format_*` methods. If a formatter's layout changes later, the literal output will drift from it. A small `emit` table or shared helper would fix that, but it isn't needed for this task.

**Validation limits.**
- Not run by me: your 155 targeted tests, mypy and ruff are your report only.
- I haven't seen the Windows output path (the UTF-8 stdout wrapper under `capsys`) run, as before.
- `Text.append` not parsing markup is from my knowledge of Rich, not from running it.
