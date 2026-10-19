# Assumptions ledger: PRD 00088 dot host links

## 1: Implement host-links manifest parsing (dot/hostlinks/manifest.py)

- Tess: the `OSError` path is tested by making the manifest path a directory (`IsADirectoryError`); only the `host-links: ` prefix and a single error are asserted, not the exception text.
- Tess: `UnicodeDecodeError` is tested the same way, with invalid UTF-8 bytes.
- Tess: duplicate detection counts only earlier valid lines; an invalid line does not reserve its target.
- Tess: `a => b => c` yields source `b => c` (split on the first `=>`), which is valid.
- Tess: `~` alone is absolute; `a..b` and `..c` are allowed because `..` must be a whole path part.
- Qwen: `hostlinks/__init__.py` not created (namespace package import works; a later task adds it).
- Qwen: "target equals source" is checked before "duplicate target"; no test pins their relative order.

## 2: Implement host link reconciliation (dot/hostlinks/linker.py)

- Tess: "exists and is not a link; skipped" applies to an existing directory as well as a file.
- Tess: on POSIX nothing is asserted about `target_is_directory` beyond the resulting link working.
- Tess: the "links elsewhere" problem uses the raw absolute readlink value as `<link>`.
- Ivan: `_read_link` strips only a leading `\\?\` (via `removeprefix`).

## 3: Implement relink git hook installer (dot/hostlinks/hooks.py)

- Tess: the `OSError` path is triggered by a regular file where the hooks dir should be (`FileExistsError` from `mkdir`).
- Tess: mode and symlink tests skip on Windows.
- Tess: an existing hook's mode is asserted untouched (reading of "never read or written").
- Tess: hook files read back as UTF-8 text with no newline translation.

## 5: Add DotGitService.hooks_path() reading core.hooksPath

- Orchestrator: tests went to a new file `tests/tools/dot/test_git_service_hooks_path.py` instead of appending to `test_git_service.py`, which is already over the 800-line limit (pre-existing, 2100+ lines).
- Tess: an error plus non-empty stdout returns None (contract: `err` non-empty -> None).
- Tess: the `HOME` override for `~` expansion is POSIX-only behavior.

## 6: Add CommandMaterialize, CommandLinkStatus and `dot materialize [--hook]`

- Tess: link targets sit at the root top level; links checked with `is_symlink()` + `resolve()`, not by absolute/relative form.
- Tess: CLI info and warning lines are captured on stdout by `CliRunner`.
- Tess: the install-`OSError` case uses `hooks_path()` returning `<regular file>/hooks`.
- Tess: a second `--hook` run is silent, like a normal run.

## 7: Append host link warnings to `dot status`

- Tess: `result.output` is not "No modifications found" whenever link warnings exist.
- Tess: whether `CommandLinkStatus` creates anything is checked on disk, not mocked.

## 8: TUI link problem count and key L

- Orchestrator: new TUI tests live in `tests/tools/dot/test_tui_host_links.py` because `test_tui_app.py` already exceeds 800 lines.
- Orchestrator: Gemini (routing row 1, UI) failed on Copilot-backend auth under the agent PAT; Claude Sonnet implemented the task.
- Orchestrator: Pat's MEDIUM (TUI ignores `result.success`) discarded: `CommandMaterialize` never returns `success=False` by contract.
- Tess: `DiffView` imported from `dot.tui.widgets.diff_view`; status bar widget id `#status-bar`.

# Assumptions ledger: PRD 00098 sysup run observability v1

## 5: sysup: exit-0 error scan, one final result per entry, capability log markers

- Tess: the log header formats for captured, not-captured and timed-out steps come from the `append_step` docstring in `src/tools/sysup/runlog.py`, which she read with a targeted `rg`.
- Tess: "immediate failure diagnostics" means that in abort mode the failure is yielded before any later step spawns, and a failed step's output is not scanned for error lines.
- Tess: "all failure details retained" means each failed step's stdout and stderr stay in the run log. The final result carries the last failure's message, as the contract code says.
- Tess: "no intermediate success lines and red dominance" is tested in the runner (exactly one result, failed beats warned), not in the CLI output. The contract gives no cli.py change to test.
- Tess (strengthen): a capability may yield `StepResult` values with status `expiring` or `warned`. The `Status` literal allows both.
- Ivan: the 5-line print limit counts per step, not across the whole entry.
- Ivan: with `continue_on_error` and several failures, the final result is the last failure.
- Ivan: in `_run_use`, `append_step` is called before the `yield` of the stamped step, not after it — the retry text only said "after the replace(...)"; logging first means the section is written even if the consumer stops at that yield.

## 6: sysup: cli.py Runner binding, full-log line, and FatalError diagnostics

- Ivan: the real `Runner` exposes a `log_path` attribute (`Path | None`) once `run()` has finished; could not verify against `runner.py` (not on allowlist), but `Runner.__init__` already sets `self.log_path = None` unconditionally (confirmed in task 5's prior diff).
- Ivan (style fix): tests patch `sysup.attention.*` and `sysup.config.*` at module level, so moving their lazy imports into the new `_persist_attention` helper is safe.

# Assumptions ledger: PRD 00099 dot shared config host fragments v1

## 3: Add CommandShare to opt a tracked file into the dot-host filter

- Orchestrator: the `home` passed to `count_home` is `str(dotfiles_root)`, the root the command was constructed with. The task contract named `home` without defining it; dot's git work-tree is that root and `hostfilter.resolve_home` falls back to `DOTFILES_ROOT`. Recorded as an assumed ambiguity in the batch deferred record.
- Tess: the out-of-root confinement refusal returns a `CommandResult` failure with an unspecified message (no string is pinned in the PRD or the design doc), so those tests assert the failure plus unchanged state only, and cover three different basenames so no basename-matching shortcut survives.
- Tess: check 7 ("already has a dot-host filter line") matches the anchored line form `/<path> filter=dot-host`, neither substring nor prefix.
- Tess: check 5 matches a host-links manifest *target*, not a source; a `#`-commented or unparsable manifest line is not an entry, so refusal 5 must not fire on it.
- Tess: `check_attr_filter` returning `None` counts as "not exactly dot-host" and takes the conflicting-attribute branch with `effective!r == 'None'`.
- Tess: a failed `cfg ls-files -s` read is represented as a non-empty error element and/or empty output from `shell.exe`; the task named no failure encoding.
- Tess: the exact `:(literal)` pathspec spelling is left unasserted (no doc pins that magic-pathspec form); the test asserts only that an `ls-files` call carries the target path.
- Tess (strengthen): a path escaping the root through a symlinked parent directory must be refused, per the PRD's "resolve and confine ... and reject links".
- Tess (strengthen, in-contract): a literal double quote is NOT a refusal, because the design doc's check 10 list is exactly whitespace, `#`, `!`, `[` and backslash. Git's attribute-file quoting does need `"` escaped, so the design doc's list is arguably incomplete - recorded as a design-gap deferred item rather than pinned in a test.
- Ivan: the root-escape refusal message was unpinned, so it reads `{target} resolves outside the dotfiles root; shared opt-in refused`.
- Ivan: the index mode is read twice from two sources - a direct `cfg ls-files -s -- :(literal)<path>` shell call for the mode check, and `capture_index_entry` for the rollback entry. Redundant against a real repo, but both are what the tests require.
- Ivan: `.gitattributes` is never captured or restored at the index level; `restore_index_entry(".gitattributes", None)` would run `rm --cached`, so its rollback is filesystem-only.
- Ivan: regular index modes are `100644` and `100755`; anything else, or an unreadable read, is "not a plain tracked file".
- Ivan: the ROLLBACK-FAILED message keeps a literal em dash because the pinned test string carries one, overriding the project writing rule.
- Ivan (review fix): the failed-attribute-restore note text was unspecified, so it reads `could not restore .gitattributes (<exc>)`; when both that restore and `restore_index_entry` fail, the two reasons join with `"; "` inside one `ROLLBACK FAILED (...)`.
- Ivan (review fix): `atomic_write_text` is byte-exact for CRLF here because `os.linesep == "\n"` on POSIX; a Windows write side would re-translate, which this repo's POSIX-only scope makes moot.
- Ivan (review fix): `is_symlink()` was put before `exists()` on explicit instruction, overriding the contract's numbering (symlink 12, missing-from-disk 8), so a broken tracked symlink reports "not a plain tracked file" instead of "missing from disk".
