# Design: 00095 dot pull divergence report

PRD: `docs/dev/project-management/prds/backlog/00095-dot-pull-divergence-report-v1.md`.
Premise checked: `rg -n "def fetch|def has_upstream" src/tools/dot/git/service.py`
returns 2 hits (00090 merged).

## Architecture fit

All divergence logic lives in `DotGitService.pull`, the one pull implementation
that CLI (`dot pull` -> `CommandPull`) and TUI (`MainScreen.action_pull` ->
`CommandPull`) already share. No new command class, no new interface. The
location and pending-count logic is a tiny shared module `dot.divergence` read
by `CommandStatus` (CLI) and `MainScreen.refresh_status` (TUI).

## Interfaces

### `src/tools/dot/divergence.py` (new)

```python
def divergence_dir(root: str | Path) -> Path:
    return Path(root) / ".local/share/dot/divergence"

def pending_patch_warning(root: str | Path) -> str | None:
    d = divergence_dir(root)
    n = len(list(d.glob("*.patch"))) if d.is_dir() else 0
    return f"{n} divergence patch(es) pending in {d}" if n else None
```

### `DotGitService.pull(passphrase=None, *, exclude: Iterable[str] = (), fetched: bool = False)`

Sequence:

1. `fetched` false -> `self.fetch()`; error -> `CommandResult(False, error="Fetch failed: <err>")`.
2. `warnings: list[str] = []`. If `self.has_upstream()`:
   1. `_select_divergent(exclude) -> tuple[list[str], str | None]`: three
      `shell.exe` calls, NUL split, empty items dropped:
      - `cfg diff --name-only --no-renames -z HEAD...@{u}` (incoming)
      - `cfg diff --cached --name-only --no-renames --ignore-submodules=all -z` (staged)
      - `cfg diff --name-only --no-renames --ignore-submodules=all -z` (unstaged)
      Any error -> `divergence check failed: <err>`.
      `selected = sorted(p for p in (staged | unstaged) & incoming if not any(p == e or p.startswith(e + "/") for e in exclude))`.
      `mixed = sorted(set(selected) & staged & unstaged)` non-empty ->
      `pull stopped: <a>, <b> have both staged and unstaged changes; commit or unstage them first`.
   2. `selected` non-empty -> `_save_divergence(selected) -> tuple[Path | None, str | None]`:
      - `cfg rev-parse HEAD`, `cfg rev-parse @{u}` via `shell.exe` (text is fine,
        40-hex ids); error or empty -> failure.
      - `patch = divergence_dir(self.wd) / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.patch"`.
      - `patch.parent.mkdir(parents=True, exist_ok=True)`; `patch.exists()` -> failure `<patch> already exists`.
      - binary capture: `subprocess.run(["git", f"--git-dir={root}/.buvis", f"--work-tree={root}", "--literal-pathspecs", "diff", "--binary", "--full-index", "--no-renames", "HEAD", "--", *selected], cwd=self.wd, capture_output=True, text=False, check=False)`;
        nonzero return -> failure with decoded stderr (`errors="replace"`).
      - `atomic_write_bytes(patch, header.encode() + proc.stdout)` where header is
        `# dot divergence patch\n# base: <head>\n# upstream: <up>\n# host: <socket.gethostname()>\n\n`.
      - Any `OSError` in mkdir/run/write -> failure `str(exc)`.
      Failure -> `CommandResult(False, error="could not save divergence patch: <reason>")`, nothing reset.
      Success -> `warnings.append(f"divergence patch saved: {patch}")`.
   3. For each `path` in the same `selected` list:
      `cfg --literal-pathspecs restore --source=HEAD --staged --worktree -- <shlex.quote(path)>`;
      error -> `CommandResult(False, error="reset failed for <path>: <err>", warnings=list(warnings))`;
      ok -> `warnings.append(f"reset to HEAD, local edit in patch: {path}")`.
3. Existing pull, submodule, reveal steps unchanged except every
   `CommandResult` (failures and the final success) carries `warnings=warnings`.

No upstream -> step 2 skipped: no diff commands, plain pull (today's behavior).
Nothing selected -> no patch, no restore, `warnings` empty: output unchanged.

`subprocess` imported at module level in `dot/git/service.py` so tests patch
`dot.git.service.subprocess.run`; `atomic_write_bytes` imported from
`buvis.pybase.filesystem` at module level so tests can patch
`dot.git.service.atomic_write_bytes` for call-order checks.

### `CommandPull.execute`

```python
targets = [l.target for l in (*plan.moves, *plan.duplicates, *plan.collisions)]
pull_result = self.dot_git_service.pull(passphrase=passphrase, exclude=targets, fetched=True)
```

`fetched=True` is always right: `execute` either calls `self.plan()` (which
fetches) or gets a plan the caller built with `plan()`. Failure ->
`CommandResult(False, error=..., warnings=list(pull_result.warnings))` (rescued
sources suffix kept). Success -> `warnings = [*pull_result.warnings, *rescue_result.warnings, *mat_result.warnings]` (+ `plan.skipped`).

Ordering (00090 risk): rescue moves run in `apply_rescue` before the service
call, so a moved target shows as a local deletion; `exclude` keeps divergence
from restoring `HEAD` bytes over it.

### Status surfaces

- `CommandStatus.execute`: after `check_hooks`, before the "No modifications"
  check: `if (pending := pending_patch_warning(self.dotfiles_root)): warnings.append(pending)`.
- `StatusBar.update_info(info, error=None, link_problems=0, pending=None)`;
  render `f"  {pending}"` style `bold yellow` right after the secrets segment.
- `MainScreen.refresh_status`: `pending=pending_patch_warning(self._dotfiles_root) if self._dotfiles_root else None`.
- `MainScreen.action_pull`: both result branches render
  `"\n".join([result.output or result.error or "Pull complete", *result.warnings])`.
- CLI `dot pull`: no change; `console.report_result` already prints warnings.

## Reuse

- 00090: `fetch`, `has_upstream`, `plan_rescue`/`RescuePlan`/`apply_rescue`,
  `CommandLocalize`, two-host helpers.
- pybase: `atomic_write_bytes`, `CommandResult.warnings`.
- Repo test-helper pattern: `from tests.tools.<tool>.conftest import ...`
  (klyreon, postup). Move `_git`, `_run`, `_setup_bare_host`,
  `_disable_git_secret` and the `two_host_setup` fixture from
  `test_pull_two_hosts.py` into `tests/tools/dot/conftest.py`; both two-host
  files import the helpers from there. No assertion in `test_pull_two_hosts.py` changes.

## Test plan

- `test_divergence.py`: missing dir, one patch, non-patch ignored, deleted -> None.
- `test_pull_divergence.py` (mock shell with a command->response router,
  patched `subprocess.run` and `atomic_write_bytes` attached to one parent mock
  for call order): every PRD Phase 1 case, exact command strings and argv.
- `test_git_service.py`: existing `TestDotGitServicePull` tests call
  `pull()` with the default `fetched=False`, which now adds `fetch` and
  `has_upstream` shell calls ahead of their `side_effect` sequences and
  `call_count` pins. An autouse class fixture stubs `git_service.fetch` -> `""`
  and `git_service.has_upstream` -> `False` on the instance, so their shell call
  sequences and every assertion stay byte-identical. New tests cover the
  `fetched=False` fetch call and its failure message.
- `test_pull.py`: the one `pull.assert_called_once_with(passphrase=None)`
  becomes `(passphrase=None, exclude=[], fetched=True)`; new tests: exclude
  carries move/duplicate/collision targets, and a service failure's warnings
  come out of `execute`.
- `test_status.py`, `test_status_bar.py`, `test_tui_app.py`, CLI test: per PRD Phase 2.
- `test_pull_divergence_two_hosts.py`: PRD cases 1-6 with real git;
  `core.autocrlf=false` forced for every git process via `GIT_CONFIG_COUNT`/
  `GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0` env (monkeypatch), and byte I/O.

## Alternatives rejected

- Capture via `ShellAdapter.exe`: text mode translates CRLF (PRD forbids).
- `git stash` instead of a patch: stash lives in the repo, gets dropped by
  `git stash clear`, and cannot be shipped to another host; PRD wants a file.
- Selection in `CommandPull`: would split pull logic across layers and miss the
  `fetched=False` path for other callers of `DotGitService.pull`.

## Risks

- Fetch-to-pull window: accepted per PRD.
- Untracked files that incoming commits add: not in staged/unstaged lists, git
  aborts as today; out of PRD scope.
- Same-second second pull with a selection: patch exists -> failure, nothing
  reset (PRD rule); user retries a second later.

## Design review dispositions (independent review, Fable, 2026-10-16)

No CRITICAL or HIGH findings.

1. MEDIUM, accepted (deviation from PRD text): a path untracked with
   `git rm --cached` but kept on disk is staged-deleted, so it is selected;
   the patch records a deletion and the reset writes `HEAD` bytes over the
   kept file. Fourth detection list
   `cfg diff --cached --name-only --no-renames --diff-filter=D -z`; a selected
   path in it that still exists on disk stops the pull before any save:
   `pull stopped: <p> untracked but kept on disk; commit the removal or re-add first`.
   A real deletion (file gone) is still saved; its patch is faithful.
2. MEDIUM, deferred: plaintext edits to git-secret files never show in the
   staged/unstaged lists (pull does not run `secret hide` first), so
   `cfg secret reveal -f` overwrites them, exactly as before this PRD. Not a
   regression; candidate follow-up PRD ("dot pull: save divergent secret
   plaintext").
3. LOW, rejected: `exclude` is materialized with `tuple(exclude)` before the
   selection generator, so a generator argument works.
4. LOW, accepted (argv deviation from PRD text): capture adds
   `--no-ext-diff --no-textconv --no-color --src-prefix=a/ --dst-prefix=b/` so
   user diff config (textconv drivers, `diff.noprefix`, color) cannot produce
   a patch `git apply` rejects.
5. LOW, accepted: one unstubbed test pins the full default command sequence.
6. LOW, noted: tests patch `dot.git.service.subprocess.run`, which is the
   global `subprocess.run`; safe because those tests use a mocked shell.
7. LOW, already covered: docs and changelog task is in the implementation.

## Implementation review dispositions (Sonnet + Fable, 2026-10-16)

Both: nothing blocks, no CRITICAL or HIGH. Reviewers ran extra real-git
probes (hostile names, symlink typechange, mode-only change, staged add that
upstream also adds, deletions); every patch rebuilt B's state at its base id.

- Accepted: divergence dir created `0o700` (patches hold private dotfile
  bytes); `cannot read HEAD/upstream: empty output` instead of an empty reason;
  single `rescued` list in `CommandPull`; no pre-declared empty warnings;
  pending-status test sets up its own mock.
- Rejected: same-second concurrent pull race (PRD fixes the name format; two
  concurrent pulls on one host within a second); renaming the moved two-host
  helpers (keeps the 00090 test file diff to its import line).
- Noted, not changed: `pull.rebase=true` with unrelated dirty files resets
  the selected files and then `cfg pull` refuses (no bytes lost, the patch
  holds them; the owner's config has `pull.rebase=false`); `.gitattributes`
  eol rules normalize the patch the way a commit would; very large selections
  could hit ARG_MAX; rescue moves stay applied when divergence stops the pull
  (PRD ordering, error lists the rescued paths).
