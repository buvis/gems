---
default_model: sonnet
model_tier_rationale: every git command, message and return shape is fixed below and was measured on git 2.55 in a scratch bare repo on 2026-10-13; additive tests plus one rewritten test class whose collected count is pinned
---

# dot add: track untracked files, literal quoted paths, loud outcome

Source: `docs/dev/project-management/intake/processed/00093-dot-add-untracked-files/discovery.md`

## Overview

### Problem Statement
`dot add <file>` on a file the dotfiles repo has never tracked prints `No changes.` and stages nothing.
`stage_interactive` (`src/tools/dot/git/service.py:317-336`) decides "untracked" by searching the lookup error for the Python phrase `returned non-zero exit status 1`.
`ShellAdapter.exe` (`src/lib/buvis/pybase/adapters/shell/shell.py:35-39,69-73`) returns git's own stderr whenever there is any, so the phrase never appears, the untracked branch never fires, and the file falls through to `cfg add -p`, which has nothing to show.
`tests/tools/dot/test_git_service.py:1184` and `:1200` mock the Python phrase, so the suite passes while the real path fails.
Two neighbours sit in the same path. `CommandAdd` (`src/tools/dot/commands/add/add.py:14-37`) accepts a path that exists relative to the current directory but hands it to git relative to the dotfiles root, so `dot add config.yml` from `~/.config/gh-agent` looks for `~/config.yml`.
And the path reaches every git command unquoted and glob-matched: measured 2026-10-13 on git 2.55, `git add -- 'file[1].txt'` also stages a modified `file1.txt`, while `:(literal)file[1].txt` stages only the named file.

### Target Users
The solo dotfiles owner running `dot add` from any directory of the work tree.

### Success Metrics
- `uv run pytest tests/tools/dot/test_git_service.py -k TestDotGitServiceStageInteractive -q` passes and `test_untracked_file_is_added_whole_without_patch_mode` fails on master `66ea27ed` before the service change (the fail-first run is quoted in the task log).
- `uv run pytest tests/tools/dot/test_add.py tests/tools/dot/test_add_integration.py -q` passes with no test skipped on a machine with git on PATH under default pytest capture.
- Integration: from `<root>/.config/gh-agent`, `CommandAdd` with `config.yml` stages `.config/gh-agent/config.yml` (asserted through `git diff --cached --name-only`); an ignored file fails with the ignore rule in the error; a path outside the work tree fails without staging; untracked `file[1].txt` beside a modified tracked `file1.txt` stages only `file[1].txt`; a symlink to a directory is staged as a `120000` link entry.
- `rg -n "non-zero exit status" src/tools/dot` prints nothing.

## Functional Decomposition

### Capability: Tracking-state detection
Classify the named path from git's answer, never from Python exception wording.

#### Feature: Classify a file path
- **Description**: One `git status` call tells tracked, untracked, ignored, or lookup failure apart.
- **Inputs**: `path` as handed to `stage_interactive` (absolute, or relative to the dotfiles root); the `cfg` alias (`src/tools/dot/git/service.py:32-33`).
- **Outputs**: one of four states, read from `(err, out)` of `cfg status --porcelain --untracked-files=all --ignored -- ':(literal)<path>'`.
- **Behavior**: `err` non-empty is a lookup failure (git exits 128 with `fatal: ...`, for example a path outside the work tree or an unreadable repository); `out[:2] == "??"` is untracked; `out[:2] == "!!"` is ignored; anything else (empty output for a clean tracked file, ` M`, `MM`, ` A`, ...) is tracked. `--untracked-files=all` is mandatory: the bare repo sets `status.showUntrackedFiles=no` and without the flag an untracked file yields empty output (measured). The pathspec carries the `:(literal)` magic so `[`, `*` and `?` in a name never glob; `check-ignore` rejects pathspec magic (`fatal: pathspec magic not supported by this command`, measured) and gets the plain quoted path instead, which it already treats literally.

### Capability: Staging
Stage the named path the way its state demands and report what is staged afterwards.

#### Feature: Stage an untracked file whole
- **Description**: A `??` file is added with a plain `cfg add -- ':(literal)<path>'`, no hunk review.
- **Inputs**: untracked state from the feature above.
- **Outputs**: `CommandResult(success=False, error=f"Could not add {path}: {err}")` when the add fails, else the staged report below with `untracked=True`.
- **Behavior**: runs through `ShellAdapter.exe` (captured, non-interactive), not `interact`. Dangling symlinks are untracked files too and stage as the link (mode `120000`, measured).

#### Feature: Refuse an ignored file
- **Description**: A `!!` file is never added; the failure names the matching rule and the force escape.
- **Inputs**: ignored state; `cfg check-ignore -v -- <shlex-quoted path>` output of the form `.gitignore:1:*.log<TAB><path>`.
- **Outputs**: `CommandResult(success=False, error=f"{path} is ignored ({detail}); add it anyway with: {self._git} add -f -- {shlex.quote(path)}")` where `detail` is the stripped `check-ignore` stdout, or its error text when stdout is empty.
- **Behavior**: no `cfg add` runs; no new flag. `self._git` is the full `git --git-dir=... --work-tree=...` prefix, so the printed escape is copy-pasteable.

#### Feature: Stage a tracked file or a directory hunk by hunk
- **Description**: Tracked files keep `cfg add -p`; a real directory keeps intent-to-add then `cfg add -p`.
- **Inputs**: tracked state, or `(self.wd / path).is_dir() and not (self.wd / path).is_symlink()`.
- **Outputs**: the staged report below with `untracked=False`.
- **Behavior**: directory flow unchanged except for quoting: `cfg ls-files --others --exclude-standard -- ':(literal)<path>'`, then `cfg add --intent-to-add -- ':(literal)<path>'` when that output is non-blank, then `interact("cfg add -p -- ':(literal)<path>'")`. A symlink to a directory takes the file path above (`??` for an untracked link, measured) and is staged as the link itself, never its target's contents. Without a path, `interact("cfg add -p")` runs over the whole tree, as today.

#### Feature: Report the staged state
- **Description**: After any staging flow, say what is currently staged for the path, or that nothing is.
- **Inputs**: `path` or `None`; `untracked` flag; `cfg diff --cached --name-status -- ':(literal)<path>'` (no pathspec when `path` is `None`).
- **Outputs**: `CommandResult(success=True, output="Currently staged:\n" + out.strip())` when the output is non-blank. Blank output gives `CommandResult(success=False, error=f"{path} was not staged")` when `untracked`, else `CommandResult(success=True, warnings=[f"Nothing staged for {path or 'the work tree'}"])`. A failed diff gives `CommandResult(success=False, error=f"Could not read the staged state: {err}")`.
- **Behavior**: the report describes the final index state and never claims this invocation produced it: a tracked file whose earlier staged change survives a fully declined `add -p` reports `Currently staged:\nM\t<path>` (measured). An intent-to-add entry is not shown by `diff --cached` (measured), so a directory whose hunks were all declined reports the warning.

### Capability: Path resolution
`CommandAdd` turns the user's argument into a path git can locate from the dotfiles root.

#### Feature: Resolve the argument from any cwd
- **Description**: A path that exists relative to the current directory becomes absolute; otherwise the dotfiles-root-relative reading is tried; otherwise today's warning and whole-tree fallback stay.
- **Inputs**: `file_path` string, `dotfiles_root` string.
- **Outputs**: `self.file_path` as `Path(os.path.abspath(file_path))`, or `Path(dotfiles_root) / file_path`, or `None` plus the existing warning `Path {file_path} doesn't exist. Proceeding with cherry picking all.`
- **Behavior**: existence is tested with `os.path.lexists()` (both branches) so a dangling symlink is a path, not a missing file; `os.path.abspath()` prepends the cwd and collapses `..` without resolving symlinks, so a named link stays the link. Precedence (cwd first, then root) is unchanged. The missing-path fallback is out of scope (discovery Open Questions).

#### Feature: Pass the service result through
- **Description**: `CommandAdd.execute` returns the service's `CommandResult` with its own warnings first.
- **Inputs**: `stage_interactive` return value.
- **Outputs**: `dataclasses.replace(result, warnings=[*self.warnings, *result.warnings])`.
- **Behavior**: `cli.py` already renders through `console.report_result` (`src/tools/dot/cli.py:67-80`); no CLI change. The TUI stages through `DotGitService.stage` (`src/tools/dot/git/service.py:88`) and never calls `stage_interactive`.

## Structural Decomposition

### Repository Structure

```
src/tools/dot/
├── git/service.py                 # Maps to: Tracking-state detection, Staging (stage_interactive, _literal, _staged_report)
└── commands/add/add.py            # Maps to: Path resolution
tests/tools/dot/
├── test_git_service.py            # TestDotGitServiceStageInteractive rewritten against real git output shapes
├── test_add.py                    # cwd-relative, symlink and pass-through tests
└── test_add_integration.py        # NEW: CommandAdd through the real ShellAdapter against a bare repo
docs/source/tools/dot.rst          # dot add section
CHANGELOG.md                       # Fixed entry
```

### Module: dot.git.service
- **Maps to capability**: Tracking-state detection, Staging
- **Responsibility**: Build every git command for staging with `shlex.quote()` and a `--` guard, classify the path from porcelain output, report the staged state as a `CommandResult`.
- **Exports**: `DotGitService.stage_interactive(path: str | None = None) -> CommandResult`
- New symbols: `_literal`, `_staged_report`
- Final text of the three functions:

```python
def _literal(path: str) -> str:
    """Quote a path as a shell-safe literal pathspec (no glob matching)."""
    return shlex.quote(f":(literal){path}")
```

```python
    def stage_interactive(self, path: str | None = None) -> CommandResult:
        """Stage a path: whole when untracked, hunk by hunk otherwise.

        Args:
            path: Path to stage; the whole work-tree when omitted.

        Returns:
            What is staged for the path afterwards, or why staging stopped.
        """
        if path is None:
            self.shell.interact("cfg add -p", self.wd)
            return self._staged_report(None, untracked=False)
        spec = _literal(path)
        target = self.wd / path
        if target.is_dir() and not target.is_symlink():
            _err, untracked = self.shell.exe(f"cfg ls-files --others --exclude-standard -- {spec}", self.wd)
            if untracked.strip():
                self.shell.exe(f"cfg add --intent-to-add -- {spec}", self.wd)
            self.shell.interact(f"cfg add -p -- {spec}", self.wd)
            return self._staged_report(path, untracked=False)
        err, out = self.shell.exe(f"cfg status --porcelain --untracked-files=all --ignored -- {spec}", self.wd)
        if err:
            return CommandResult(success=False, error=f"Could not determine whether {path} is tracked: {err}")
        state = out[:2]
        if state == "!!":
            err, rule = self.shell.exe(f"cfg check-ignore -v -- {shlex.quote(path)}", self.wd)
            detail = rule.strip() or err
            escape = f"{self._git} add -f -- {shlex.quote(path)}"
            return CommandResult(success=False, error=f"{path} is ignored ({detail}); add it anyway with: {escape}")
        if state == "??":
            err, _out = self.shell.exe(f"cfg add -- {spec}", self.wd)
            if err:
                return CommandResult(success=False, error=f"Could not add {path}: {err}")
            return self._staged_report(path, untracked=True)
        self.shell.interact(f"cfg add -p -- {spec}", self.wd)
        return self._staged_report(path, untracked=False)

    def _staged_report(self, path: str | None, *, untracked: bool) -> CommandResult:
        pathspec = f" -- {_literal(path)}" if path else ""
        err, out = self.shell.exe(f"cfg diff --cached --name-status{pathspec}", self.wd)
        if err:
            return CommandResult(success=False, error=f"Could not read the staged state: {err}")
        if not out.strip():
            if untracked:
                return CommandResult(success=False, error=f"{path} was not staged")
            return CommandResult(success=True, warnings=[f"Nothing staged for {path or 'the work tree'}"])
        return CommandResult(success=True, output="Currently staged:\n" + out.strip())
```

### Module: dot.commands.add
- **Maps to capability**: Path resolution
- **Responsibility**: Resolve the argument, call the service, merge warnings.
- **Exports**: `CommandAdd` (unchanged signature)
- Final text of the resolution block and `execute` (`import os` and `from dataclasses import replace` added at the top):

```python
        if file_path:
            if os.path.lexists(file_path):
                self.file_path = Path(os.path.abspath(file_path))
            elif os.path.lexists(os.path.join(dotfiles_root, file_path)):
                self.file_path = Path(dotfiles_root) / file_path
            else:
                self.warnings.append(
                    f"Path {file_path} doesn't exist. Proceeding with cherry picking all.",
                )

    def execute(self: CommandAdd) -> CommandResult:
        result = self.dot_git_service.stage_interactive(str(self.file_path) if self.file_path else None)
        return replace(result, warnings=[*self.warnings, *result.warnings])
```

### Module: tests.tools.dot.test_git_service (class TestDotGitServiceStageInteractive)
- **Maps to capability**: Tracking-state detection, Staging
- **Responsibility**: Unit tests with the mocked `shell` fixture; every mocked git failure is real stderr (`fatal: not a git repository: '/home/user/dotfiles/.buvis/'`), never the Python phrase. Each test pins the exact command strings, so the `:(literal)` magic, the quoting and the `--` guard are asserted.
- **Exports**: none (tests)
- New symbols: `test_without_path_starts_patch_mode_then_reports_staged_state`, `test_without_path_and_nothing_staged_warns`, `test_untracked_file_is_added_whole_without_patch_mode`, `test_lookup_failure_stops_before_staging`, `test_ignored_file_is_refused_naming_the_rule_and_the_force_escape`, `test_declined_hunks_report_existing_staged_changes_as_currently_staged`, `test_tracked_file_with_nothing_staged_warns`, `test_untracked_file_left_unstaged_fails`, `test_failed_add_is_reported`, `test_path_with_embedded_quote_is_shell_quoted`, `test_symlink_to_a_directory_takes_the_file_path`
- Test table (`shell.exe.side_effect` in call order; `path` is `newfile.txt` unless stated; `S` = `cfg status --porcelain --untracked-files=all --ignored -- ':(literal)<path>'`, `D` = `cfg diff --cached --name-status -- ':(literal)<path>'`):
  - `test_without_path_starts_patch_mode_then_reports_staged_state`: `exe` -> `("", "M\t.bashrc\n")`; asserts `interact` called with `cfg add -p` in `/home/user/dotfiles`, `exe` called once with `cfg diff --cached --name-status`, `result.output == "Currently staged:\nM\t.bashrc"`, `result.warnings == []`.
  - `test_without_path_and_nothing_staged_warns`: `exe` -> `("", "")`; `result.success is True`, `result.warnings == ["Nothing staged for the work tree"]`.
  - `test_untracked_file_is_added_whole_without_patch_mode` (the regression test): side effects `[("", "?? newfile.txt\n"), ("", ""), ("", "A\tnewfile.txt\n")]`; asserts the exe commands are exactly `[S, "cfg add -- ':(literal)newfile.txt'", D]`, `shell.interact.assert_not_called()`, `result.success is True`, `result.output == "Currently staged:\nA\tnewfile.txt"`.
  - `test_tracked_file_is_staged_in_patch_mode` (kept name, rewritten): side effects `[("", ""), ("", "M\t.bashrc\n")]` for `.bashrc`; asserts `interact` called with `cfg add -p -- ':(literal).bashrc'`, exe commands `[S, D]`, output `Currently staged:\nM\t.bashrc`.
  - `test_lookup_failure_stops_before_staging` (replaces `test_unrelated_lookup_error_still_stages_in_patch_mode`): side effects `[("fatal: not a git repository: '/home/user/dotfiles/.buvis/'", "")]`; `result.success is False`, `result.error == "Could not determine whether .bashrc is tracked: fatal: not a git repository: '/home/user/dotfiles/.buvis/'"`, `interact` not called, exactly one exe call.
  - `test_ignored_file_is_refused_naming_the_rule_and_the_force_escape`: path `.cache/x`, side effects `[("", "!! .cache/x\n"), ("", ".gitignore:3:.cache/\t.cache/x\n")]`; `result.success is False`, `result.error == ".cache/x is ignored (.gitignore:3:.cache/\t.cache/x); add it anyway with: git --git-dir=/home/user/dotfiles/.buvis/ --work-tree=/home/user/dotfiles add -f -- .cache/x"`, second exe command `cfg check-ignore -v -- .cache/x`, `interact` not called, no exe command starts with `cfg add`.
  - `test_declined_hunks_report_existing_staged_changes_as_currently_staged`: path `.bashrc`, side effects `[("", "MM .bashrc\n"), ("", "M\t.bashrc\n")]`; `interact` called with `cfg add -p -- ':(literal).bashrc'`, `result.output == "Currently staged:\nM\t.bashrc"`, `result.warnings == []`.
  - `test_tracked_file_with_nothing_staged_warns`: path `.bashrc`, side effects `[("", ""), ("", "")]`; `result.success is True`, `result.warnings == ["Nothing staged for .bashrc"]`, `result.output is None`.
  - `test_untracked_file_left_unstaged_fails`: side effects `[("", "?? newfile.txt\n"), ("", ""), ("", "")]`; `result.success is False`, `result.error == "newfile.txt was not staged"`.
  - `test_failed_add_is_reported`: side effects `[("", "?? newfile.txt\n"), ("error: insufficient permission for adding an object to repository database .git/objects", "")]`; `result.success is False`, `result.error` starts with `Could not add newfile.txt: error: insufficient permission`, exactly two exe calls.
  - `test_path_with_embedded_quote_is_shell_quoted` (replaces `test_path_with_embedded_quote_is_passed_through_verbatim`, which locked in the unquoted bug): path `it's.txt`, side effects `[("", ""), ("", "")]`; first exe command `cfg status --porcelain --untracked-files=all --ignored -- ':(literal)it'"'"'s.txt'`, `interact` command `cfg add -p -- ':(literal)it'"'"'s.txt'`.
  - `test_patch_mode_follows_the_tracked_answer_not_the_path_name` (kept, parametrized over `.bashrc` and `newfile.txt`): tracked case side effects `[("", ""), ("", "")]` expects `interact` with `cfg add -p -- ':(literal){path}'`; untracked case side effects `[("", "?? {path}\n"), ("", ""), ("", "A\t{path}\n")]` expects exe command `cfg add -- ':(literal){path}'` and no `interact`.
  - `test_relative_directory_path_is_resolved_against_the_dotfiles_root` (kept, strings updated, third side effect `("", "")` added): exe commands `["cfg ls-files --others --exclude-standard -- ':(literal)sub'", "cfg add --intent-to-add -- ':(literal)sub'", "cfg diff --cached --name-status -- ':(literal)sub'"]`, `interact` with `cfg add -p -- ':(literal)sub'`, `result.warnings == ["Nothing staged for sub"]`.
  - `test_absolute_path_to_a_plain_file_is_not_treated_as_a_directory` (kept, strings updated): first exe command is `S` for the absolute path, `interact` with `cfg add -p -- ':(literal)<abs>'`.
  - `test_directory_with_untracked_content_gets_intent_to_add_first` and `test_directory_without_untracked_content_skips_intent_to_add` (kept): one more side effect `("", "")` for the diff; the `--intent-to-add` assertions unchanged; `interact` command starts with `cfg add -p -- `.
  - `test_symlink_to_a_directory_takes_the_file_path`: `tmp_path / "real"` directory, `tmp_path / "link"` symlink to it, service via `_service_at(shell, tmp_path)`, side effects `[("", "?? link\n"), ("", ""), ("", "A\tlink\n")]`; exe commands `[S, "cfg add -- ':(literal)link'", D]` for path `link`, no `--intent-to-add`, no `interact`.

### Module: tests.tools.dot.test_add
- **Maps to capability**: Path resolution
- **Responsibility**: Resolution and pass-through with `DotGitService` patched.
- **Exports**: none (tests)
- New symbols: `test_relative_path_resolves_against_cwd_before_the_dotfiles_root`, `test_symlink_is_kept_as_the_link_not_its_target`, `test_dangling_symlink_is_a_path_not_a_missing_file`
- Changes:
  - `test_relative_path_resolves_against_cwd_before_the_dotfiles_root`: create `dotfiles_root / ".config" / "gh-agent" / "config.yml"`, `monkeypatch.chdir` into that directory, `CommandAdd(..., file_path="config.yml")`; `cmd.file_path == dotfiles_root / ".config" / "gh-agent" / "config.yml"`, `cmd.warnings == []`.
  - `test_symlink_is_kept_as_the_link_not_its_target`: `real` directory and `link` symlink under `dotfiles_root`; `CommandAdd(..., file_path=str(link))`; `cmd.file_path == link`.
  - `test_dangling_symlink_is_a_path_not_a_missing_file`: `link` symlink to `dotfiles_root / "gone"`; `cmd.file_path == link`, `cmd.warnings == []`.
  - Every `TestCommandAddExecute` test sets `mock_service.stage_interactive.return_value` to a real `CommandResult` (a bare `MagicMock` cannot be `replace`d). `test_with_file_calls_stage_interactive_with_str_path` returns `CommandResult(success=True, output="Currently staged:\nA\ttracked.txt")` and asserts `result.output` equals it. `test_nonexistent_file_still_calls_stage_interactive_with_none_and_warns` returns `CommandResult(success=True, warnings=["Nothing staged for the work tree"])` and asserts `result.warnings == ["Path missing.txt doesn't exist. Proceeding with cherry picking all.", "Nothing staged for the work tree"]`.

### Module: tests.tools.dot.test_add_integration (new file)
- **Maps to capability**: all three, end to end
- **Responsibility**: Run `CommandAdd.execute` through the real `ShellAdapter` against a throwaway bare repo shaped like production (`<root>/.buvis` bare, `<root>` work tree, `status.showUntrackedFiles=no`) and assert both the returned `CommandResult` and the real index.
- **Exports**: none (tests)
- New symbols: `bare_root`, `test_untracked_file_from_nested_cwd_is_staged_whole`, `test_bracketed_name_beside_tracked_neighbour_stages_only_the_named_file`, `test_ignored_file_is_refused_with_rule_and_escape`, `test_tracked_file_without_changes_warns_nothing_staged`, `test_tracked_file_with_staged_changes_reports_them_as_currently_staged`, `test_directory_keeps_intent_to_add_flow`, `test_symlink_to_directory_is_staged_as_the_link`, `test_path_outside_the_work_tree_fails_without_staging`
- Module guards: `pytestmark = [pytest.mark.skipif(shutil.which("git") is None, reason="needs git"), pytest.mark.skipif(os.isatty(0), reason="git add -p would wait on the terminal; run without -s")]`. Under default pytest capture fd 0 is `/dev/null` (measured 2026-10-13: `os.isatty(0)` is `False` and a child `read` gets EOF), so every `add -p` exits at once with its hunks declined.
- Fixture `bare_root(tmp_path, monkeypatch)`: `monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)` and `monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")` so the developer's gpgsign, excludes file and hooks path cannot leak in; `root = tmp_path / "home"`; `git init --quiet --bare <root>/.buvis`; through `git --git-dir=<root>/.buvis --work-tree=<root>` (an argv-list `subprocess.run` helper with `check=True`, `cwd=root`): `config status.showUntrackedFiles no`, `config user.name t`, `config user.email t@example.com`; write `file1.txt` (`one\n`) and `.gitignore` (`*.log\n`); `add -- file1.txt .gitignore`; `commit --quiet -m init`; return `root`. Every test runs `CommandAdd(shell=ShellAdapter(suppress_logging=True), dotfiles_root=str(root), file_path=...).execute()` after `monkeypatch.chdir(root)` unless stated, and reads the index with `git diff --cached --name-only`.
- Cases:
  - `test_untracked_file_from_nested_cwd_is_staged_whole`: `.config/gh-agent/config.yml` written, `monkeypatch.chdir(root / ".config" / "gh-agent")`, `file_path="config.yml"`; `result.success is True`, `result.output == "Currently staged:\nA\t.config/gh-agent/config.yml"`, index lists exactly `.config/gh-agent/config.yml`.
  - `test_bracketed_name_beside_tracked_neighbour_stages_only_the_named_file`: write `file[1].txt` and modify `file1.txt`; `file_path=str(root / "file[1].txt")`; index lists exactly `file[1].txt`; `git diff --name-only` still lists `file1.txt`.
  - `test_ignored_file_is_refused_with_rule_and_escape`: `a.log`; `result.success is False`; `".gitignore:1:*.log" in result.error`; `"add -f --" in result.error`; index is empty.
  - `test_tracked_file_without_changes_warns_nothing_staged`: `file_path="file1.txt"`; `result.success is True`; `result.warnings == [f"Nothing staged for {root / 'file1.txt'}"]`; index is empty.
  - `test_tracked_file_with_staged_changes_reports_them_as_currently_staged`: write `two\n` to `file1.txt`, `git add -- file1.txt`, then write `two\nthree\n`; `file_path="file1.txt"`; `result.output == "Currently staged:\nM\tfile1.txt"`, `result.warnings == []`; `git diff --name-only` still lists `file1.txt`.
  - `test_directory_keeps_intent_to_add_flow`: `sub/new.txt` written, `file_path="sub"`; `result.success is True`; `git ls-files -- sub` prints `sub/new.txt` (the intent-to-add entry); `result.warnings == [f"Nothing staged for {root / 'sub'}"]`.
  - `test_symlink_to_directory_is_staged_as_the_link`: `real/q.txt` and `link -> real`; `file_path="link"`; index lists exactly `link`; `git ls-files -s -- link` starts with `120000`.
  - `test_path_outside_the_work_tree_fails_without_staging`: `tmp_path / "outside.txt"` written, `file_path=str(tmp_path / "outside.txt")`; `result.success is False`; `result.error` starts with `Could not determine whether`; index is empty.

### Module: docs and changelog
- **Maps to capability**: Staging (user-facing description)
- **Responsibility**: `docs/source/tools/dot.rst:124-132` describes the new behaviour; `CHANGELOG.md` gets a `### Fixed` bullet under `[Unreleased]`.
- **Exports**: none
- Final `dot add` section text:

```rst
dot add
~~~~~~~

Stage changes. A tracked file or a directory opens git's hunk picker
(``add -p``); a file the repository has never tracked is added whole. A path is
looked up relative to the current directory first, then relative to the
dotfiles root, and a symlink is staged as the link itself. An ignored file is
refused with the matching ignore rule and the ``git add -f`` command that
overrides it. Afterwards the command prints what is currently staged for the
path, or warns when nothing is.

.. code-block:: bash

    dot add                     # hunk picker over the whole tree
    dot add ~/.bashrc           # hunk picker for a tracked file
    dot add config.yml          # new file, relative to the current directory
```

- Changelog bullet (under `### Fixed` in `[Unreleased]`): `- **dot**: `dot add <file>` tracks a file the repository has never seen instead of answering `No changes.`; a path relative to the current directory resolves there before the dotfiles root; an ignored file is refused with the matching rule and the `git add -f` escape; paths are shell-quoted and matched literally, so `file[1].txt` no longer also stages `file1.txt`; afterwards the command prints what is currently staged for the path, or warns when nothing is.`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **dot.git.service**: `stage_interactive` returning `CommandResult`, `_literal`, `_staged_report`; unit tests in `test_git_service.py`.

### Core Layer (Phase 1)
- **dot.commands.add**: Depends on [dot.git.service] (consumes the `CommandResult`); tests in `test_add.py`.

### Integration Layer (Phase 2)
- **tests.tools.dot.test_add_integration**: Depends on [dot.git.service, dot.commands.add].
- **docs and changelog**: Depends on [dot.commands.add] (describes the finished behaviour).

## Implementation Phases

### Phase 0: Foundation
**Goal**: `stage_interactive` classifies from porcelain output, quotes every path literally, and returns what is staged.

**Tasks**:
- [ ] Rewrite `TestDotGitServiceStageInteractive` per the test table (no deps). Premise, re-checked at execution: `uv run pytest tests/tools/dot/test_git_service.py -k TestDotGitServiceStageInteractive --co -q` collects 13 tests and `rg -n "returned non-zero exit status" tests/tools/dot/test_git_service.py` hits only lines inside that class plus the `check_ignore` parametrization at `tests/tools/dot/test_git_service.py:1106-1119` (which stays). If the class differs, stop and report. Acceptance: the same `--co` command collects at least 19 tests; `uv run pytest tests/tools/dot/test_git_service.py -k untracked_file_is_added_whole -q` FAILS against the unchanged service with `interact` having been called (output quoted in the task log); no test outside the class changed.
- [ ] Implement `_literal`, `stage_interactive`, `_staged_report` in `src/tools/dot/git/service.py` with the final text above, and add the changelog bullet in the same commit (depends on: task 1). Acceptance: `uv run pytest tests/tools/dot/test_git_service.py -q` passes; `rg -n "non-zero exit status" src/tools/dot` prints nothing; `rg -c "Currently staged" CHANGELOG.md` prints 1.

**Exit Criteria**: `uv run pytest tests/tools/dot/test_git_service.py -q` green with the regression test present.

### Phase 1: Core
**Goal**: `CommandAdd` resolves from any cwd, keeps symlinks, and returns the service result.

**Tasks**:
- [ ] Add the three `test_add.py` tests and update `TestCommandAddExecute` to real `CommandResult` return values (depends on: Phase 0). Premise, re-checked at execution: `rg -c "    def test_" tests/tools/dot/test_add.py` prints 13; otherwise stop and report. Acceptance: the count prints at least 16; `uv run pytest tests/tools/dot/test_add.py -k "cwd_before or symlink" -q` FAILS before the `add.py` change (quoted in the task log).
- [ ] Apply the `add.py` final text (depends on: previous task). Acceptance: `uv run pytest tests/tools/dot/test_add.py -q` passes; `rg -n "\.exists\(\)" src/tools/dot/commands/add/add.py` prints nothing.

**Exit Criteria**: `uv run pytest tests/tools/dot/test_add.py tests/tools/dot/test_git_service.py -q` green.

### Phase 2: Integration
**Goal**: Real git proves the whole path and the docs describe it.

**Tasks**:
- [ ] Create `tests/tools/dot/test_add_integration.py` with the guards, fixture and eight cases above (depends on: Phase 1). Acceptance: `uv run pytest tests/tools/dot/test_add_integration.py -q -rs` reports 8 passed, 0 skipped; `uv run pytest tests/tools/dot/test_add_integration.py -q -s` reports 8 skipped when fd 0 is a terminal, 8 passed otherwise.
- [ ] Replace the `dot add` section in `docs/source/tools/dot.rst` with the final text (depends on: Phase 1). Acceptance: `rg -c "added whole" docs/source/tools/dot.rst` prints 1; `uv run sphinx-build -b html docs/source docs/build/html -q` exits 0.

**Exit Criteria**: `uv run pytest -m dot -q` green; `uv run mypy src/tools/dot` clean; `uv run ruff check src/tools/dot tests/tools/dot` clean.

## Test Strategy

### Critical Scenarios
- **Happy path**: untracked `config.yml` from `<root>/.config/gh-agent` -> Expected: `cfg add -- ':(literal)<abs path>'`, result output `Currently staged:\nA\t.config/gh-agent/config.yml`, index holds exactly that path.
- **Edge case**: untracked `file[1].txt` beside a modified tracked `file1.txt` -> Expected: only `file[1].txt` staged, `file1.txt` still unstaged.
- **Edge case**: tracked file with an earlier staged change, every new hunk declined -> Expected: `Currently staged:\nM\t<path>`, no warning, no claim of new staging.
- **Edge case**: symlink to a directory, or a dangling symlink -> Expected: file path (status), staged as a `120000` link entry.
- **Error case**: lookup failure (`fatal: ...` from status) -> Expected: `success=False`, `Could not determine whether <path> is tracked: fatal: ...`, nothing run after status.
- **Error case**: ignored file -> Expected: `success=False`, error names `.gitignore:<line>:<pattern>` and `git --git-dir=... --work-tree=... add -f -- <path>`, nothing added.
- **Error case**: untracked file that `cfg add` could not stage -> Expected: `success=False` with git's stderr, or `<path> was not staged` when the index stays empty.

## Risks

- **`add -p` reads stdin in the integration tests**: default pytest capture hands children `/dev/null` on fd 0 (measured), so hunks are declined and the process exits; `-s` or `--capture=sys` from a terminal would hang, which the `os.isatty(0)` skip guard prevents. Tests only ever assert the declined outcome.
- **Developer git config leaks into the fixture** (commit signing, a global excludes file, a global hooks path, an identity env var): `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1` are set on the fixture; identity is set on the repo.
- **Porcelain output quotes unusual names** (`?? "it's file.txt"`, measured): only `out[:2]` is read, the path itself is never parsed back.
- **A staged deletion plus an untracked file of the same name yields two status lines**: the first line decides; accepted edge, not covered by tests.
- **Non-English git locale**: no stderr text is matched anywhere; failure detection is `err` non-empty, state detection is the stable porcelain `XY` column.
- **Neighbouring dot PRDs (00090, 00091, 00095) add tests to `test_git_service.py`**: the premise pins the class's collected count and the file's `def test_` count of `test_add.py`, never a file or suite total for `test_git_service.py`.
