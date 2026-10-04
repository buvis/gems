# dot: unify the git command layer behind one service

<!-- design; migrated from PRD 00053 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/dot/
├── git/
│   └── service.py        # Maps to: Shared git operations (DotGitService)
├── commands/             # thin: construct DotGitService, return its CommandResult
│   └── {status,add,...}/
└── tui/
    ├── git_ops.py        # removed or reduced to a thin shim over DotGitService
    └── screens/          # call DotGitService directly
```

### Module: dot.git.service
- **Maps to capability**: Shared git operations
- **Responsibility**: the single source of truth for dot's git behavior.
- **Exports**: `DotGitService` with `status/add/unstage/stage/commit/push/pull/rm/delete`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies — built first.
- **dot.git.service**: the unified service (seeded from `GitOps`). Design input: the seam contract in `dev/local/specs/all-interface-architecture.md` — the service returns `CommandResult` and the CLI/TUI adapters map it per that contract.

### Core Layer (Phase 1)
- **dot/commands/***: Depend on [dot.git.service] — become thin wrappers.

### Integration Layer (Phase 2)
- **dot/tui/***: Depend on [dot.git.service] — screens call the service; `git_ops.py` removed or shimmed.

## Test Strategy

### Critical Scenarios
- **Happy path**: commit through CLI and through TUI exercise the same service path → identical git commands issued.
- **Edge case**: pull with a dirty submodule follows one code path (relevant to the tracked pull-safety concern).
- **Error case**: a failing git verb returns `CommandResult(success=False)` surfaced correctly by both CLI and TUI.

## Risks

- **Interactive vs non-interactive divergence**: some CLI commands are interactive (`cfg add -p`); the service must expose a non-interactive core and let the CLI layer add prompting, not bake prompts into the service.
- **Behavior drift during the move**: lock current behavior with characterization tests before folding, so the unification preserves it.

---

<!-- folded from architecture/decisions/00053-dot-git-ops-unification-v1-design.md -->

# Design: dot: unify the git command layer behind one service

## Architecture fit

`dot` currently has three parallel git layers with no shared base:

- **CLI**: 10 command classes (`commands/{status,add,unstage,commit,push,pull,rm,delete,encrypt,run}/`), each independently resolving `DOTFILES_ROOT`, aliasing `cfg`, and building git subprocess strings via the injected `ShellAdapter`.
- **TUI core**: `tui/git_ops.py`'s `GitOps` class (15 public methods), constructed once in `tui/app.py:DotApp.__init__` and threaded through `MainScreen`/`BrowseScreen`/`SecretsScreen`.
- **TUI command modules**: `tui/commands/{browse,secrets}.py` — free functions that reach into `git_ops.shell.exe(...)` directly with their own `cfg ls-files`/`cfg check-ignore`/`cfg secret ...` strings, bypassing `GitOps` entirely.

This PRD collapses all three into one `DotGitService` (new `dot/git/service.py`), seeded from `GitOps` per the PRD's own call (`GitOps` already takes `dotfiles_root` and returns `CommandResult`). CLI command classes and TUI screens become thin callers; `tui/commands/{browse,secrets}.py` stop building `cfg` strings and call the service's primitives instead. This is the same shape as the accepted `dev/local/specs/all-interface-architecture.md` seam (command classes over a shared core, composition root owns wiring) applied inside a single tool rather than across CLI/TUI/API/WebUI.

## Module placement

**New:**
- `src/tools/dot/git/__init__.py` — empty package init.
- `src/tools/dot/git/models.py` — `BranchInfo`, `FileEntry` moved here from `tui/models.py` (see Interfaces & contracts note on why `git/service.py` cannot import from `tui/`).
- `src/tools/dot/git/service.py` — `DotGitService`, seeded from `tui/git_ops.py`, extended with the CLI commands' policy (rm/delete encryption-awareness, interactive staging, unstage-all) and the browse/secrets git primitives.

**Deleted:**
- `src/tools/dot/tui/git_ops.py` — fully superseded; `DotGitService` is a strict superset, so no shim is needed. Every `from dot.tui.git_ops import GitOps` becomes `from dot.git.service import DotGitService`.

**Edited (thin wrappers, construct `DotGitService` and return its `CommandResult`):**
- `src/tools/dot/commands/status/status.py`, `add/add.py`, `unstage/unstage.py`, `commit/commit.py`, `push/push.py`, `pull/pull.py`, `rm/rm.py`, `delete/delete.py`, `encrypt/encrypt.py` — each constructor gains a `dotfiles_root: str` parameter, builds `DotGitService(shell, dotfiles_root)` internally, and `execute()` calls one service method. CLI-only presentation logic that isn't a git verb (status's staged/unstaged label formatting; add's file-existence-check warning, see Interfaces) stays in the command class, now fed by the service's typed return instead of raw porcelain text.
- `src/tools/dot/cli.py` — extract the existing `dotfiles_root = os.environ.get("DOTFILES_ROOT", str(Path.home()))` line from `_launch_tui` (line 20) into a module-level `_dotfiles_root() -> str` helper; every subcommand handler calls it once and passes the result to its command class. This removes **nine** of the ten duplicated `if not os.environ.get(...): os.environ.setdefault(...)` blocks (one per command class, `run.py` excepted — see below) in favor of the one read-only pattern `cli.py` already uses correctly for the TUI launch path.
- `src/tools/dot/tui/app.py` — import + construct `DotGitService` instead of `GitOps`; attribute name `self._git_ops` stays unchanged (smallest diff — see Alternatives).
- `src/tools/dot/tui/models.py` — becomes a two-line re-export shim (`from dot.git.models import BranchInfo, FileEntry`) so the 9 existing TUI/test importers (`tui/screens/main.py`, `tui/widgets/{status_bar,file_list}.py`, and 6 test files) need no change.
- `src/tools/dot/tui/screens/main.py`, `screens/browse.py`, `screens/secrets.py` — type hints only (`git_ops: GitOps` → `git_ops: DotGitService`); call sites (`self._git_ops.stage(...)`, `.commit(...)`, etc.) are unchanged since method names/signatures are preserved on the service.
- `src/tools/dot/tui/commands/browse.py` — `_query_git_sets` AND `get_tracking_status` both call `git_ops.ls_files(...)` / `git_ops.check_ignore(...)` instead of building `cfg ls-files`/`cfg check-ignore` strings via `git_ops.shell.exe(...)` directly (both functions did this independently — see Interfaces). `list_directory`/`DirEntry`/`TrackingStatus` are unchanged in shape — they stay here (TUI presentation types), now sourced from the service primitives.
- `src/tools/dot/tui/commands/secrets.py` — `list_secrets`/`register_secret`/`unregister_secret`/`reveal_all`/`hide_all` become thin wrappers over `service.list_secrets()`/`service.register_secret()`/`service.unregister_secret()`/`service.reveal_secrets()`/`service.hide_secrets()`. The revealed/hidden presentation mapping in `list_secrets` (checking `(root / p).exists()`) stays here — it's TUI display logic, not a git verb.

**Not touched (explicit scope decision — see Alternatives):**
- `src/tools/dot/commands/run/run.py` — arbitrary passthrough (`cfg <user-supplied args>`), not a duplicated policy sequence; nothing to unify. It keeps its own `os.environ.setdefault("DOTFILES_ROOT", ...)` and its own `${DOTFILES_ROOT}`-based `cfg` alias, unchanged. This is a deliberate, accepted exception: the PRD's Phase 0 "no os.environ writes" acceptance criterion scopes to the service's own unit tests, and Phase 1's exit-criteria grep (`rg "cfg (commit|pull|rm|add)"`) doesn't cover `run`'s passthrough verb — so leaving `run.py` as-is does not violate either stated criterion, it just means `run.py` is the one command class that still resolves `DOTFILES_ROOT` the old way. Flagged explicitly so `/plan-tasks` doesn't count it in the "nine command classes migrated" task or try to force it through `DotGitService`.

## Interfaces & contracts

```python
# src/tools/dot/git/service.py
from __future__ import annotations

from pathlib import Path
from buvis.pybase.result import CommandResult
from buvis.pybase.adapters.shell.shell import ShellAdapter
from dot.git.models import BranchInfo, FileEntry

__all__ = ["DotGitService"]


class DotGitService:
    def __init__(self, shell: ShellAdapter, dotfiles_root: str) -> None:
        self.shell = shell
        self.dotfiles_root = dotfiles_root
        self.wd = Path(dotfiles_root)
        # dotfiles_root is interpolated directly, NOT via ${DOTFILES_ROOT} -
        # the service never writes os.environ, so nothing would expand the
        # old alias string. See Risks.
        self.shell.alias(
            "cfg",
            f"git --git-dir={dotfiles_root}/.buvis/ --work-tree={dotfiles_root}",
        )
        self._ensure_fetch_refspec()

    # -- queries (typed data, no CommandResult) --
    def status(self) -> tuple[list[FileEntry], str | None]: ...
    def diff(self, path: str, staged: bool = False) -> str: ...
    def branch_info(self) -> BranchInfo: ...
    def has_uncommitted_changes(self) -> bool: ...
    def has_unpushed_commits(self) -> bool: ...
    def ls_files(self, pathspec: str) -> set[str]: ...          # new: `cfg ls-files <pathspec>`, used by
                                                                  # both _query_git_sets and get_tracking_status
    def check_ignore(self, pathspec: str) -> set[str]: ...      # new: `cfg check-ignore <pathspec>`, ditto

    # -- mutations (CommandResult) --
    def stage(self, path: str) -> CommandResult: ...                       # cfg add <path>
    def stage_interactive(self, path: str | None = None) -> None: ...      # new: folds add.py's -p picker
                                                                             # (directory/intent-to-add/error-unmatch
                                                                             # heuristics only; the file-existence
                                                                             # check + warning stay in add.py's
                                                                             # __init__, same precedent as status's
                                                                             # label formatting — CLI-only, no
                                                                             # return channel through a void method)
    def unstage(self, path: str | None = None) -> CommandResult: ...       # signature widened: None = unstage all
    def commit(self, message: str) -> CommandResult: ...
    def push(self) -> CommandResult: ...
    def pull(self, passphrase: str | None = None) -> CommandResult: ...
    def rm(self, path: str) -> CommandResult: ...                         # REPLACED: now encryption-aware (00045)
    def delete(self, path: str) -> CommandResult: ...                     # new: folds delete.py
    def add_to_gitignore(self, pattern: str) -> CommandResult: ...
    def apply_patch(self, patch: str) -> CommandResult: ...
    def apply_patch_reverse(self, patch: str) -> CommandResult: ...
    def apply_reverse_to_worktree(self, patch: str) -> CommandResult: ...

    # -- secrets --
    def is_secret_tool_available(self) -> bool: ...                       # wraps shell.is_command_available("git-secret")
    def list_secrets(self) -> list[str]: ...                              # new: raw `cfg secret list` paths
    def register_secret(self, path: str) -> CommandResult: ...            # new: folds tui/commands/secrets.py
    def unregister_secret(self, path: str) -> CommandResult: ...          # new
    def reveal_secrets(self, passphrase: str | None = None) -> CommandResult: ...  # new
    def hide_secrets(self) -> CommandResult: ...                          # new: `cfg secret hide` (explicit action)
    def encrypt_and_stage(self, path: str) -> CommandResult: ...          # new: folds encrypt.py's add+hide+stage sequence

    # -- private, unchanged from GitOps --
    def _ensure_fetch_refspec(self) -> None: ...
    def _hide_changed_secrets(self) -> str | None: ...   # renamed from _hide_secrets; `cfg secret hide -m`
    def _has_unpushed_commits(self) -> bool: ...
    def _run_patch(self, patch: str, flags: str) -> CommandResult: ...
```

Key behavioral deltas vs. today's `GitOps` (every downstream caller gets these for free, no call-site changes):

- **`rm(path)` becomes encryption-aware.** `GitOps.rm` today is `cfg rm <path>` unconditionally — the TUI's rm action (`main.py:216`) has never had the 00045 encrypted-file safety behavior CLI's `CommandRm` has. The service's `rm` is `CommandRm`'s full logic verbatim: detect via `list_secrets()`, `--cached` + `shlex.quote` for the normal path, `secret remove` + `--cached <path>.secret` + re-stage `.gitsecret/` for the encrypted path, including the "do not simply retry" restore-mapping error message.
- **`unstage(path=None)` accepts no path.** `GitOps.unstage` doesn't exist today (TUI never unstages-all); folding CLI `CommandUnstage`'s `path is None -> cfg reset HEAD` branch in gives the TUI that capability at no extra cost.
- **`branch_info()`'s ahead/behind fallback.** CLI `status.py`'s own `_get_ahead_behind` (no `origin/<branch>` fallback when there's no upstream) is dropped; `CommandStatus.execute()` calls `service.branch_info()` instead, which already has the `origin/{branch}` fallback `GitOps.branch_info` has always had. This fixes a latent CLI-only gap as a side effect of unification — call it out in the characterization tests (Test Strategy).
- **`_has_unpushed_commits()` reconciles a genuine behavioral conflict, not just a copy.** `commands/push/push.py:39-54` returns `True` (assume unpushed, attempt the push) when `cfg rev-list --count @{u}..HEAD` errors — e.g. no upstream tracking ref configured. `GitOps._has_unpushed_commits` instead falls back to `cfg rev-list --count origin/{branch}..HEAD`, and if THAT also errors or is unparseable, returns `False` (assume nothing to push, skip silently). Adopting `GitOps` verbatim would flip CLI `dot push` from "always attempts push when it can't tell" to "silently no-ops when it can't tell" in that scenario — a real behavior change, not a refactor. The service keeps `GitOps`'s `origin/{branch}` fallback attempt (it's a strict accuracy improvement when no upstream is configured but `origin/<branch>` exists), but changes the final "both attempts failed" case to return `True` (fail open — attempt the push), matching `push.py`'s safer default: a needless `git push` on a clean branch is a harmless no-op, while a silently skipped push leaves the user's commits stranded without them knowing. This is the one merge point in this design where neither source implementation is adopted verbatim; needs a dedicated characterization test (see Test strategy).

## Data flow

**CLI:** `cli.py` subcommand handler -> `_dotfiles_root()` (read-only env lookup) -> construct `ShellAdapter` -> construct command class with `(shell, dotfiles_root, ...)` -> command class builds `DotGitService(shell, dotfiles_root)` internally -> calls one service method -> command class shapes the `CommandResult` (or, for `status`, converts `list[FileEntry]` into the CLI's staged/unstaged label lines) -> `console.report_result(...)`.

**TUI:** `DotApp.__init__` constructs one `ShellAdapter` + one `DotGitService` for the process lifetime -> passed into `MainScreen`/`BrowseScreen`/`SecretsScreen` constructors -> screens call service methods directly on user actions (keystroke bindings) -> `CommandResult` / typed return mapped to widget updates (unchanged screen-side logic).

Both interfaces now run every git verb through the exact same `DotGitService` instance shape (a fresh instance per CLI invocation, one long-lived instance per TUI session) — no more independently-built `cfg` aliases or independently-branched secret/submodule policy.

## Reuse inventory

- `tui/git_ops.py::GitOps` — base for ~10 of the 20 service methods, copied near-verbatim (`status`, `diff`, `stage`, `commit`, `push`, `pull`, `add_to_gitignore`, `apply_patch*`, `branch_info`, `has_uncommitted_changes`, `has_unpushed_commits`, `_ensure_fetch_refspec`, `_run_patch`).
- `commands/rm/rm.py::CommandRm` — encrypted/normal branching folded into `DotGitService.rm` (see Interfaces).
- `commands/delete/delete.py::CommandDelete` — encrypted/normal branching folded into `DotGitService.delete`.
- `commands/add/add.py::CommandAdd` — directory/intent-to-add/`--error-unmatch` heuristics folded into `DotGitService.stage_interactive`.
- `commands/unstage/unstage.py::CommandUnstage` — optional-path-means-all folded into `DotGitService.unstage`'s widened signature.
- `commands/encrypt/encrypt.py::CommandEncrypt` — register+hide+stage sequence folded into `DotGitService.encrypt_and_stage`.
- `tui/commands/secrets.py` — revealed/hidden presentation mapping (`(root / p).exists()`) reused as-is in the thinned module, now sourced from `service.list_secrets()`.
- `cli.py:20`'s `os.environ.get("DOTFILES_ROOT", str(Path.home()))` — the one already-correct (read-only) resolution pattern in the codebase, promoted to a shared `_dotfiles_root()` helper instead of writing a new one.
- `buvis.pybase.result.CommandResult`, `buvis.pybase.adapters.shell.shell.ShellAdapter`, `buvis.pybase.adapters.console` — unchanged, no new dependency.
- `tests/tools/dot/test_git_ops.py`'s `MagicMock` shell fixture pattern (constructs the class directly with an explicit `dotfiles_root`, no env var) — reused as the test double pattern for `test_service.py` (renamed from `test_git_ops.py`).
- Searched for an existing in-repo "unify N implementations behind one service" precedent beyond `GitOps` itself: `bim`'s `ACTION_HANDLERS` registry + command classes + `bim/dependencies.py` composition root (`dev/local/project-capsule.md` Evolution roadmap) is the closest architectural precedent, but it's a cross-tool, HTTP-facing registry — not reusable code (cross-tool imports prohibited by AGENTS.md), precedent only. Greps tried for a literal reusable base class: `rg -n "class.*Service\b" src/` (hits are zettel-domain services, unrelated business logic, not git/shell-facing) — nothing found to reuse beyond what's listed above.

## Alternatives considered

1. **Keep `tui/git_ops.py` as a thin shim re-exporting `DotGitService`** (what the PRD's Structural Decomposition diagram suggests as one option: "removed or reduced to a thin shim"). Rejected as the chosen path in favor of straight deletion: `DotGitService` is a strict superset with identical method names/signatures for every method `GitOps` already had, so a shim would just be `GitOps = DotGitService` — dead indirection with no behavior difference, and the PRD's own Exit Criteria ("no second git implementation remains") reads more cleanly against zero `tui/git_ops.py` references than against an aliasing shim. Smallest-diff version of this PRD's idea, and the size doesn't grow from taking it.
2. **Rename `self._git_ops` to `self._git_service` across `app.py`/screens.** More accurate name, but touches every call site (`main.py` has 15+ references) for a cosmetic win with no behavior change. Rejected — smallest-diff wins; the attribute still refers to "the thing that does git operations," which stays true.
3. **Fold `commands/run/run.py` into the service too**, since Phase 1's task text says "`dot/commands/*`" (a wildcard covering it). Rejected: `run` is an intentional escape hatch for arbitrary user-supplied git args (`dot run <anything>`) with no policy to unify — there is no TUI equivalent and no duplicated sequence. Forcing it through a `DotGitService.run(args)` method would just relocate the passthrough, not remove duplication, and it would need to special-case "no `cfg` validation" in a class whose whole point is owning git *policy*. Named explicitly as out-of-scope so `/plan-tasks` doesn't try to force-fit it under the wildcard.

## Risks & edge cases

- **`${DOTFILES_ROOT}` alias expansion depended on the env mutation this PRD removes.** The old alias string was literally `git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}` — it only resolved because every constructor called `os.environ.setdefault("DOTFILES_ROOT", ...)` first. `ShellAdapter._expand_environment_variables` (`os.path.expandvars`) leaves an unset `${DOTFILES_ROOT}` literally unexpanded rather than substituting empty string; the actual failure happens one hop later when `subprocess.run(..., shell=True, env=os.environ.copy())` hands that still-literal text to the OS shell, which performs its own unset-variable-to-empty substitution. Net effect either way: removing the mutation without changing the alias silently breaks every `cfg` invocation. Fixed by interpolating `dotfiles_root` directly into the alias string at construction time (see Interfaces) instead of relying on env expansion — this is the one correctness-critical change in an otherwise mechanical unification. Needs its own characterization test that exercises `shell.exe`/`subprocess` end-to-end (not just `_expand_environment_variables` in isolation, which wouldn't actually exercise the real failure path) with `DOTFILES_ROOT` unset in the test environment.
- **Interactive vs. non-interactive divergence** (PRD's own Risk). `stage_interactive`'s `shell.interact(...)` call is fire-and-forget (no `CommandResult`, matches today's `CommandAdd.execute()` which always returns `CommandResult(success=True)` regardless of what the interactive picker actually did). The service must not attempt to synchronously capture interactive-picker output; keep the void return so the CLI layer's existing "assume success unless the shell itself errors" posture is preserved, not silently upgraded to something the interactive path can't actually observe.
- **Test signature churn.** Every `commands/*` test file currently relies on `conftest.py`'s `dotfiles_root` fixture (which `monkeypatch.setenv`s `DOTFILES_ROOT`) and constructs command classes with only `shell=`. All eight command test files (`test_status.py`, `test_add.py`, `test_unstage.py`, `test_commit.py`, `test_push.py`, `test_pull.py`, `test_rm.py`, `test_delete.py`) plus `test_encrypt.py` must now also pass `dotfiles_root=` to the constructor. Mechanical (mirror the fixture's existing `Path` value into the constructor call), but a real per-file touch — sized here so `/plan-tasks` doesn't undercount it as "just move some code."
- **Next likely changes this design should not box in:** (1) `dot run` staying a raw passthrough means a future "add git-secret-safe guardrails to `dot run`" change has nowhere to hang — acceptable, since that would be new policy, not a unification; (2) a future API/WebUI interface for `dot` (per AGENTS.md's all-interface rule) would want `DotGitService` constructed once per request behind a composition root — the current "CLI/TUI each own construction" split is fine for two interfaces but would want a shared factory (`dot/dependencies.py`, mirroring bim's) if a third interface arrives; not needed now, flagging so the module boundary (`git/service.py` as a standalone importable unit, no CLI/TUI imports inside it) is kept clean for that future.

## Test strategy outline

- **New `tests/tools/dot/test_service.py`** (renamed from `test_git_ops.py`): every `DotGitService` verb exercised against a `MagicMock` shell, constructed directly with an explicit `dotfiles_root` (no env var) — extends the existing `TestGitOpsStatus`-style test classes with new cases for `rm` (encrypted vs. normal), `delete`, `unstage(None)`, `stage_interactive`, `encrypt_and_stage`, `ls_files`/`check_ignore`, and the secret methods. Assert the `cfg` alias string embeds the literal `dotfiles_root`, not `${DOTFILES_ROOT}` (locks in the alias-expansion fix).
- **Characterization tests before folding** (PRD's own Risk: "lock current behavior with characterization tests before folding"): for `rm`, assert the TUI path (previously naive `cfg rm <path>`) now goes through the same encrypted-branch logic as the CLI path — a regression test that would have caught the pre-existing TUI gap. For `push`, assert the "both rev-list attempts fail" case now attempts the push (`True`/fail-open) rather than silently no-op'ing (see Key behavioral deltas).
- **Existing `commands/*` test files**: updated in place to pass `dotfiles_root=` (mechanical, see Risks); assertions on `CommandResult` shape stay the same since method behavior at the CLI boundary is unchanged (except the `rm`/`push`/ahead-behind deltas above, which get their own new assertions).
- **`tests/tools/dot/test_browse_commands.py`, `test_secrets_commands.py`**: NOT a mechanical update — both currently mock at the `shell.exe` level and assert on raw `cfg ...` command strings (`shell.exe.call_args`). Once `tui/commands/{browse,secrets}.py` route through `DotGitService`'s typed methods instead of building `cfg` strings themselves, these assertions no longer apply and the tests are rewritten to mock `DotGitService`'s methods directly (`ls_files`, `check_ignore`, `register_secret`, etc.) and assert on the wrapper's call-through, not the git command text.
- **`tests/tools/dot/test_tui_snapshots.py`, `test_tui_app.py`, `test_browse_screen.py`, `test_secrets_screen.py`**: constructor/import updates only (`GitOps` -> `DotGitService`); no behavior assertions should need to change since screen-facing method signatures are preserved.
- **Edge case**: pull with a dirty submodule — already covered by `test_pull.py`'s submodule reset/init/update sequence assertions; carry forward unchanged since `pull`'s body doesn't change.
- **Error case**: a failing git verb returns `CommandResult(success=False)` — already the pattern throughout; add one assertion per new method (`delete`, `encrypt_and_stage`, secret methods) that a shell error propagates as `success=False` with the error text preserved.

## Review log

- Non-blocking (addressed as a side effect of the blocker-4 fix, not left open): `get_tracking_status` in `tui/commands/browse.py` independently built `cfg ls-files`/`cfg check-ignore` strings via `shell.exe` directly, the same duplication pattern the design claims to close at the architecture-fit level. Now routed through `ls_files`/`check_ignore` alongside `_query_git_sets` (Module placement).
- Question (recorded, not fixed — resolved by the `stage_interactive` doc comment added above): whether `add.py`'s file-existence-check warning folds into the service or stays CLI-side. Resolved: stays in `add.py`'s `__init__`, same precedent as `status`'s label formatting.
- Question (recorded, not fixed — resolved by rewording the Risk bullet above): the `${DOTFILES_ROOT}` failure-mode explanation named the wrong layer (`_expand_environment_variables` leaves it unexpanded; the OS shell does the empty-string substitution one hop later via `subprocess.run`). Conclusion and fix were already correct; wording corrected.

dispatch 1 (claude): cardinal-sin 0, blocker 4, non-blocker 1, question 2
