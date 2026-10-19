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
