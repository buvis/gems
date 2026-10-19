# Design: dot shared config with host-value filters

## Architecture fit

Lands entirely inside `src/tools/dot/`, following the existing layering:
`cli.py` (adapters) -> `commands/<name>/` (command classes returning
`CommandResult`) -> `git/service.py` (`DotGitService`, the sole seam onto the
bare `cfg` repo). This PRD adds one new layer-0 module (`hostfilter.py`, pure
stdlib byte transforms, no git/CLI dependency) that both the hidden CLI filter
commands and the new `CommandShare` command import — it has no upward
dependency on either. `DotGitService` gains a constructor self-heal plus six
small reader/writer methods (`renormalize`, `filter_driver_configured`,
`check_attr_filter`, `capture_index_entry`, `restore_index_entry`, and a
tracked-mode reader used by `CommandShare`'s regular-file check) beside its
existing self-heal calls (`_ensure_fetch_refspec`, `_ensure_hooks_path`),
keeping "one action, one implementation" intact: there is still exactly one
place dot talks to git.

The PRD's own "Console methods" exception (binary filter stdout/stderr) is the
one deliberate departure from the `AGENTS.md` console-only rule, and is scoped
to the two new `dot filter clean|smudge` commands only — `CommandShare` and
everything else keeps using `CommandResult` / `console.report_result`.

## Module placement

New files:
- `src/tools/dot/hostfilter.py` — pure transforms (`clean`, `smudge`,
  `resolve_home`), stdlib only.
- `src/tools/dot/commands/localize/share.py` — `CommandShare`.
- `tests/tools/dot/test_hostfilter.py`
- `tests/tools/dot/test_git_service_filter.py`
- `tests/tools/dot/test_share.py`
- `tests/tools/dot/test_filter_cli.py`
- `tests/tools/dot/test_shared_real_git.py`

Edited files:
- `src/tools/dot/git/service.py` — add `_ensure_filter_driver` (called from
  `__init__` beside the other self-heal calls), `filter_driver_configured`,
  `check_attr_filter`, `renormalize`, `capture_index_entry` and
  `restore_index_entry`.
- `src/tools/dot/git/models.py` — add the `IndexEntry` frozen dataclass
  (`mode: str`, `sha: str`) beside the existing `FileEntry`/`BranchInfo`.
- `src/tools/dot/cli.py` — add hidden `dot filter clean <path>` /
  `dot filter smudge <path>` commands and a `--shared` option on the existing
  `localize` command.
- `docs/source/tools/dot.rst`, `README.md`, `AGENTS.md`, `CHANGELOG.md` —
  documentation (Phase 2).

No existing file moves, no new top-level package, no new dependency.

## Interfaces & contracts

### `src/tools/dot/hostfilter.py`

```python
from __future__ import annotations

TOKEN = b"@HOME@"

_POSIX_BOUNDARY = ...  # byte-class check, see Behavior below
_WIN_DRIVE_RE = ...    # compiled regex, module-level

def resolve_home(work_tree_arg: str | None, cwd: str) -> str:
    """Resolve this host's home value.

    Precedence: ``GIT_WORK_TREE`` (made absolute against ``cwd`` if relative)
    > ``DOTFILES_ROOT`` env var > ``Path.home()``. Trailing path separators
    are stripped from the result (``/`` and, on the Windows-spelling path,
    ``\\``).

    Args:
        work_tree_arg: The value of the ``GIT_WORK_TREE`` env var, or ``None``.
        cwd: The process working directory, used to make a relative
            ``GIT_WORK_TREE`` absolute.

    Returns:
        The host home value as a plain string (POSIX-style, forward slashes).
    """

def clean(data: bytes, home: str) -> bytes:
    """Replace every home occurrence in ``data`` with ``TOKEN``.

    Args:
        data: Raw file bytes (any encoding; transform is byte-level).
        home: This host's home value (see ``resolve_home``), trailing
            separators already stripped.

    Returns:
        ``data`` with every boundary-matched occurrence of ``home`` (POSIX
        form, and the three accepted Windows spellings — native backslash,
        doubled JSON backslash, forward slash — compared case-insensitively
        only on the drive letter) replaced by ``TOKEN``. Bytes outside a
        match, including newline style, encoding and any BOM, are untouched.
        A match requires a byte outside ``[A-Za-z0-9_.-]`` (or start/end of
        input) on both sides of the matched span.

    Raises:
        ValueError: ``data`` already contains ``TOKEN`` before any
            replacement — the token is reserved. Callers needing the
            dedicated CLI error text catch this and re-raise/report it
            themselves (see ``dot filter clean``'s contract below); this
            function raises the bare condition only.
    """

def smudge(data: bytes, home: str) -> bytes:
    """Replace every ``TOKEN`` occurrence in ``data`` with ``home`` bytes.

    Args:
        data: Cleaned bytes (containing zero or more ``TOKEN`` occurrences).
        home: This host's home value. Always written with forward slashes
            (even when ``home`` was resolved from a Windows-spelled path);
            whatever separator followed the token in the cleaned bytes is
            preserved unchanged (suffix separators are never rewritten).

    Returns:
        ``data`` with every ``TOKEN`` replaced by ``home``'s bytes. Bytes
        outside a token are untouched.
    """

def count_home(data: bytes, home: str) -> int:
    """Count boundary-matched home occurrences in ``data`` without replacing them.

    Used by ``CommandShare`` for the dry-clean replacement count (the share
    output line), so sharing a file is non-destructive to inspect first.
    """
```

Round-trip contracts (proved in `test_hostfilter.py`, not re-derived here):
for token-free raw POSIX bytes `y`, `smudge(clean(y, home), home) == y`; for
bytes `x` produced by `clean`, `clean(smudge(x, home), home) == x`. The
Windows-spelling path has no byte-identical raw round-trip requirement
(normalization is intentionally lossy on spelling, not on content).

### `src/tools/dot/cli.py` — hidden filter group

```python
@cli.group("filter", hidden=True, help="Git clean/smudge filter plumbing (internal)")
def filter_group() -> None: ...

@filter_group.command("clean")
@click.argument("path")
def filter_clean(path: str) -> None: ...

@filter_group.command("smudge")
@click.argument("path")
def filter_smudge(path: str) -> None: ...
```

Behavior (both commands):
- Read `sys.stdin.buffer.read()` in full (binary; no text decoding).
- Resolve home via `hostfilter.resolve_home(os.environ.get("GIT_WORK_TREE"), os.getcwd())`.
- `clean`: call `hostfilter.clean(data, home)`. On the reserved-token
  `ValueError`, write exactly
  `f"dot filter: {path} already contains @HOME@; the token is reserved\n"`
  to `sys.stderr`, write nothing to `sys.stdout`, and `sys.exit(1)` — never
  construct a `CommandResult` or touch `console` for this path (the PRD's
  sanctioned direct-write exception). On success, write the returned bytes to
  `sys.stdout.buffer` and exit 0.
- `smudge`: call `hostfilter.smudge(data, home)`, write result to
  `sys.stdout.buffer`, exit 0. Smudge never raises on reserved-token content
  (clean already refused it at commit time) and has no refusal path.
- Neither command constructs `DotGitService`, calls `_dotfiles_root()`, or
  imports anything from `dot.git` — this is what prevents recursive filter
  invocation (Git never re-triggers Git from inside a filter driver run by
  Git). `path` is accepted only for inclusion in the clean-refusal message;
  it is never opened or stat'd.
- `filter_group` and its two commands are declared in `cli.py` directly (not
  lazy-imported like the other commands), because they must never import
  `DotGitService`-bearing modules even transitively; `hostfilter` is the only
  import.

### `src/tools/dot/git/service.py` — `DotGitService` additions

```python
def _ensure_filter_driver(self) -> None:
    """Install the dot-host clean/smudge/required filter config when unset.

    Reads ``filter.dot-host.clean``; if it is already set, changes none of
    the three keys (an operator's own configuration, or a prior run, wins).
    Otherwise writes, in this order, checking each write's error before the
    next:

        filter.dot-host.clean    = BUVIS_AUTO_UPDATE=false dot filter clean -- %f
        filter.dot-host.smudge   = BUVIS_AUTO_UPDATE=false dot filter smudge -- %f
        filter.dot-host.required = true

    The ``--`` before ``%f`` is required: Git substitutes the literal
    repo-relative path for ``%f`` with no quoting of its own, and
    ``dot filter clean``/``smudge`` are plain Click commands — a shared
    path beginning with ``-`` (e.g. ``-settings``) would otherwise be parsed
    as an option by Click instead of as the positional ``path`` argument.

    ``required`` is written LAST and only when both prior writes succeeded —
    it is Git's own hard-fail switch (PRD: "a missing dot executable must
    cause Git to fail loudly"), so a host must never observe
    ``required = true`` with ``clean``/``smudge`` unset or partially written.
    If ANY of the three writes fails (including ``required`` itself, after
    ``clean``/``smudge`` already succeeded), unset every one of the three
    keys that is currently set (``cfg config --unset filter.dot-host.<key>``
    for each, ignoring an already-unset error), so a failed self-heal always
    leaves the filter fully inert — never ``clean``/``smudge`` set with
    ``required`` missing, which is exactly the half-configured state a
    caller cannot distinguish from "fully configured but not yet needing a
    required check." `DotGitService.__init__` does not raise on this
    failure (it is a self-heal, like the existing two), but the next
    construction retries it from the same unset state. Called from
    ``__init__`` beside ``_ensure_fetch_refspec`` and ``_ensure_hooks_path``,
    so every ``DotGitService`` construction self-heals the driver —
    including the construction ``CommandSetup`` performs before the first
    checkout, which is why that checkout already smudges correctly.
    """

def filter_driver_configured(self) -> bool:
    """Report whether all three dot-host filter keys are set to their expected values.

    Reads ``filter.dot-host.clean``, ``.smudge`` and ``.required`` and
    returns ``True`` only when all three are present — ``clean``/``smudge``
    hold any value (an operator may have customized them) and ``required``
    reads exactly ``"true"``. Checking only ``clean`` would pass on the
    partially-failed state ``_ensure_filter_driver`` is designed to never
    leave behind in the first place, but checking all three here means a
    caller never has to trust that invariant blindly — ``CommandShare``'s
    precondition (check 11) calls this, not a private re-derivation.
    """

def check_attr_filter(self, path: str) -> str | None:
    """Report the effective ``filter`` attribute Git computes for one path.

    Args:
        path: Root-relative **pathname** — ``shlex.quote``d directly, never
            wrapped in a ``:(literal)`` pathspec operator; ``git check-attr``
            takes pathnames, not pathspecs, and a pathspec-wrapped argument
            silently matches nothing, which would make every effective-
            attribute check falsely report "no filter".

    Returns:
        The ``value`` field of ``cfg check-attr -z filter -- <path>``'s
        ``path\\0attr\\0value\\0`` record (``None`` when Git reports
        ``unspecified``), reflecting Git's own full ``.gitattributes``
        precedence resolution (nested files beat the root file; a
        ``$GIT_DIR/info/attributes`` entry beats every tracked file) — not a
        re-derivation of that precedence from file contents this service
        would otherwise have to parse itself.
    """

def renormalize(self, path: str) -> CommandResult:
    """Re-run the configured filter over one tracked path and stage the result.

    Args:
        path: Root-relative path, passed through ``_literal`` (the same
            ``:(literal)<path>`` shlex-quoted pathspec helper every other
            ``DotGitService`` method uses) so the pathspec never glob-expands.

    Returns:
        The outcome of ``cfg add --renormalize -- <literal-path>``: success
        with no output, or failure with git's stderr as ``error``.
    """

def capture_index_entry(self, path: str) -> IndexEntry | None:
    """Capture one path's current index mode and blob sha, for later exact restore.

    Args:
        path: Root-relative path.

    Returns:
        ``IndexEntry(mode, sha)`` (a small frozen dataclass next to
        ``FileEntry``/``BranchInfo`` in ``git/models.py``) parsed from
        ``cfg ls-files -s -- <literal-path>`` (fields: mode, sha, stage,
        path — space-separated, tab before path), or ``None`` when the path
        has no index entry at all (never tracked, or already removed).

        Only a **stage-0** record is captured. A conflicted path has no
        stage 0: ``ls-files -s`` prints three records for it, at stages 1
        (base), 2 (ours) and 3 (theirs), and blindly reading the first
        line's fields would capture stage 1 and later "restore" it as a
        stage-0 entry — silently resolving a merge conflict to its base and
        discarding both sides. So the parse requires the stage field to read
        exactly ``0`` and returns ``None`` otherwise, and a conflicted path
        is refused before any mutation by check 12 below rather than rolled
        back afterwards.
    """

def restore_index_entry(self, path: str, entry: IndexEntry | None) -> CommandResult:
    """Restore a path's index entry to exactly what ``capture_index_entry`` captured.

    Args:
        path: Root-relative path.
        entry: The previously captured entry, or ``None`` to mean "had no
            index entry before" (restoring to that state removes it again).

    Returns:
        Success from ``cfg update-index --add --cacheinfo <mode>,<sha>,<path>``
        when ``entry`` is not ``None``. ``--add`` is REQUIRED, not optional:
        verified empirically 2026-10-19, ``--cacheinfo`` without it refuses a
        path that is not currently in the index with ``error: <path>: cannot
        add to the index - missing --add option?`` and exits 128 — which is
        precisely the restore case, since the mutation being rolled back may
        have dropped the entry. With ``--add`` both paths work: re-creating a
        removed entry and replacing an existing entry's mode both exit 0.
        The whole comma triple is one
        ``shlex.quote``d shell token, and its third field is a **pathname**,
        NOT a ``:(literal)`` pathspec: ``git update-index --cacheinfo`` takes
        ``<mode>,<object>,<path>`` (git's own usage string), so a pathspec
        operator there would register an index entry for a file literally
        named ``:(literal)<path>`` — the same pathname-vs-pathspec confusion
        ``check_attr_filter`` above warns about. The ``rm --cached`` branch
        below keeps the literal pathspec, because ``git rm`` does take
        pathspecs. Or from
        ``cfg rm --cached --ignore-unmatch -- <literal-path>`` when it is
        ``None`` (the path is dropped from the index, work-tree untouched —
        same flag ``untrack`` already uses). Either way this touches ONLY
        the index; it never reads or writes the work-tree file, which is
        what makes it an exact, content-independent restore rather than a
        reconstruction through the clean filter (renormalize re-derives the
        index from current work-tree bytes, which is only safe when the two
        are already known to match — this method needs no such precondition
        at all, since it writes the captured sha directly).
    """
```

Config values use `self.shell.exe(f"cfg config filter.dot-host.clean {shlex.quote(cmd)}", self.wd)` for each
of the three keys, matching the existing `_ensure_hooks_path` call shape.
`check_attr_filter`, `capture_index_entry` and `restore_index_entry` are the
only other `DotGitService` additions this PRD needs.

### `src/tools/dot/commands/localize/share.py`

```python
class CommandShare:
    """Register one tracked regular file for the dot-host clean/smudge filter."""

    def __init__(
        self,
        shell: ShellAdapter,
        dotfiles_root: str,
        path: str,
        *,
        git_service: DotGitService | None = None,
    ) -> None: ...

    def execute(self) -> CommandResult: ...
```

- **Normalization**: same root-relative normalization as `CommandLocalize`
  (`Path(path)`; if absolute, `relative_to(root)`, else used as given under
  the root).
- **Refusal checks** (all before any mutation, in this order — first match
  wins, matching `CommandLocalize._check_preconditions`'s single-error-string
  shape):
  1. not tracked (`git_service.ls_files(target)` empty) — `f"{target} not tracked; run dot add first"`.
  2. untracked-but-exists is covered by (1); missing-from-disk entirely is
     also covered by (1) since an absent, never-added path is never tracked.
  3. target is a directory — `f"{target} is a directory; directory opt-in is unsupported"`.
  4. target is a git-secret file (`target in git_service.list_secrets()`) — `f"{target} is a git-secret file; shared opt-in refused"`.
  5. target matches an existing host-links manifest entry (`read_manifest`, reuse `dot.hostlinks.manifest.read_manifest`) — `f"{target} already listed in host-links manifest"`.
  6. `target == ".gitattributes"` — `"refused: .gitattributes itself cannot be shared"`.
  7. an existing `dot-host` attribute line for this exact path already exists in `.gitattributes` — `f"{target} already has a dot-host filter line"`.
  8. raw work-tree bytes already contain `hostfilter.TOKEN` — `f"{target} contains the reserved @HOME@ token"`. Reading the bytes for this check can itself raise `FileNotFoundError` (check 1 only proves the path is *tracked*, not that it still exists on disk — a tracked-then-deleted-from-disk file passes check 1); that case is its own refusal, checked immediately before this one: `f"{target} is tracked but missing from disk; run dot add or restore it first"`.
  9. path contains a glob metacharacter (`*`, `?`, `[`) — `f"{target} looks like a glob pattern; glob opt-in is unsupported"`.
  10. path needs attribute quoting (whitespace, `#`, `!`, `[`, backslash) — `f"{target} needs attribute-file quoting, which is unsupported"`.
  11. the dot-host filter driver is not actually and fully configured on this host (`git_service.filter_driver_configured() -> bool`, reading all three of `filter.dot-host.clean`/`.smudge`/`.required` — not just `clean` — since a self-heal that wrote the first two and failed on `required` is just as inert a half-configuration as one that wrote none) — `f"dot-host filter driver is not configured; a prior self-heal write may have failed. Re-run 'dot status' to retry, then 'dot localize --shared {target}' again"`. Without this check, a host whose `_ensure_filter_driver` self-heal failed silently (Interfaces & contracts above) would let `CommandShare` "succeed" via Git's own no-op passthrough on an unconfigured filter — the index would be byte-identical to the work tree, not tokenized, and the reported replacement count would be a lie about what the index actually holds.
  12. the target is a symlink, or its tracked index entry's mode is not a plain regular-file mode (`100644`/`100755`) — checked via `Path(target_path).is_symlink()` (not-following) and `git_service`'s existing `status()`/`ls_files` surface extended with one `cfg ls-files -s -- <literal-path>` call to read the mode field — `f"{target} is not a plain tracked file (symlink or special mode); shared opt-in refused"`. This is checked before check 8's byte read, so a FIFO or other special file is refused before anything ever attempts to read it (which could hang); a symlink is refused rather than silently sharing its target's content under the link's own path. The same check refuses `target` whenever `capture_index_entry(target)` returns `None`, with `f"{target} has no readable stage-0 index entry (untracked, conflicted, or git could not read it); shared opt-in refused"`. `None` conflates three states — no index entry, a conflicted path (stages 1/2/3 only), and a failed `ls-files` read — and `target` must be a tracked regular file in all of them, so all three are refusals here. Refusing on `None` for `target` is what keeps the rollback safe: `restore_index_entry(target, None)` drops the path from the index, so mutating a `target` whose capture returned `None` would discard its conflict stages, or the entry of a tracked path whose read merely failed transiently. Only `.gitattributes`, where not-yet-tracked is the genuinely expected state, may treat a `None` capture as absence and let the rollback remove it.

**Task 3 must ship a test for this refusal** (per-task review of task 2, raised twice by the reviewer and accepted as a precondition rather than a signature change): a `target` whose `capture_index_entry` returns `None` — conflicted or unreadable — must be refused by check 12 and must never reach `restore_index_entry(target, None)`. The obligation is a docstring contract in `filter_driver.py` and therefore unenforceable in task 2's own code; this test is what makes it real. Without it the conflated `None` silently discards conflict stages, or a tracked entry whose `ls-files` read failed transiently.
  (Checks 9 and 10 overlap on `[`; check 9's glob message wins when both match, since it is tested first. Checks 11-12 run after 1-10 since they need git/filesystem round-trips the string-only checks above do not. There is deliberately no "no staged changes" refusal — unlike an earlier draft of this design, the mutation sequence below restores index state by captured sha rather than by reconstructing it from work-tree bytes, so a staged difference on `target` is no longer a hazard and need not be refused.)
- **Mutation sequence** (mirrors `CommandLocalize._mutate`'s ordered-steps +
  reverse rollback shape, but there is no move/link step here — only an
  attribute append + renormalize + stage. Every rollback below restores
  state by captured index entry, never by re-deriving content through the
  filter, which is what makes each restore exact regardless of what the
  work tree currently holds):
  1. Dry-clean the current work-tree bytes: `n = hostfilter.count_home(raw_bytes, home)`. This does not touch the file.
  2. Capture rollback state, nothing mutated yet: `target_entry = git_service.capture_index_entry(target)` and `attrs_entry = git_service.capture_index_entry(".gitattributes")` (either may be `None`; `.gitattributes` commonly has no entry yet), plus the current `.gitattributes` work-tree text (`""` if the file does not exist).
  3. Read `.gitattributes`, append the literal line
     `f"/{target} filter=dot-host\n"` (anchored with a leading `/` so a
     same-named file in a subdirectory is not also matched), preserving the
     existing-newline convention `append_entry` already uses (blank line
     inserted only if the existing content is non-empty and lacks a trailing
     newline). Write with `atomic_write_text`.
  4. **Effective-attribute check, immediately after the write, before any
     git mutation**: `git_service.check_attr_filter(target) -> str | None`
     (new method, backed by `cfg check-attr -z filter -- <path>` — the
     **plain shell-quoted pathname**, not a `:(literal)` pathspec:
     `git check-attr` takes pathnames, and wrapping one in a pathspec
     operator makes Git look for a file literally named `:(literal)<path>`,
     which silently never matches — parsing the `-z`-delimited
     `path\0attr\0value\0` record for the `value` field) must return
     exactly `"dot-host"`. Git resolves `.gitattributes` by directory
     precedence (deepest wins) plus `$GIT_DIR/info/attributes` last, so
     appending the line to the root file does not guarantee it is the line
     that actually governs `target` — a nested `.gitattributes` or
     `info/attributes` entry could already claim that path for a different
     filter (or `-filter`, explicitly unsetting it). Checking this **before**
     touching git at all (nothing has been renormalized or staged yet) means
     a mismatch needs only the cheapest possible rollback: restore
     `.gitattributes`' work-tree text to step 2's captured value (or delete
     the file if it did not exist before), with no index to touch — return
     `CommandResult(success=False, error=f"{target} is governed by a conflicting attribute entry (effective filter: {effective!r}); check nested .gitattributes files and $GIT_DIR/info/attributes for a prior rule on this path")`.
  5. `git_service.renormalize(target)`. On failure: restore `.gitattributes`'
     work-tree text to step 2's captured value (same as step 4's rollback —
     nothing has reached the index yet on this failure path either), return
     `CommandResult(success=False, error=f"renormalize failed: {result.error}")`.
  6. `git_service.stage(".gitattributes")`. On failure: roll back by
     **exact index restore**, not by re-renormalizing: call
     `git_service.restore_index_entry(target, target_entry)` to undo step
     5's renormalize, restore `.gitattributes`' work-tree text to step 2's
     captured value, and — since `stage` never reached the index on this
     failure — there is no `.gitattributes` index entry to restore. If
     `restore_index_entry` itself fails, do not claim "rolled back":
     return `CommandResult(success=False, error=f"could not stage .gitattributes: {stage_result.error}; ROLLBACK FAILED ({restore_result.error}); {target}'s index entry may still be tokenized — run 'cfg status' and 'dot run diff --cached -- {target}' before retrying")`.
     On a successful rollback, return
     `CommandResult(success=False, error=f"could not stage .gitattributes: {stage_result.error}; share rolled back, retry 'dot localize --shared {target}'")`.
     Rollback is mandatory here, not advisory: an unrolled-back partial share
     would let `.gitattributes` omit the `filter=dot-host` line while the
     index already holds tokenized content, so a later `dot commit` ships a
     tokenized blob with no filter registered for it — host B's pull would
     then smudge-skip that path and silently receive literal `@HOME@` bytes
     instead of its own home, with no error at any step. A share operation
     must therefore be all-or-nothing from the caller's point of view.
  7. On full success:
     `CommandResult(success=True, output=(f"shared {target}: {n} host value(s) replaced" if n else f"no host value found in {target}; filter active for future writes"), info=["staged .gitattributes"])`.
- Every rollback branch above restores the `target` index entry via
  `restore_index_entry` using the value `capture_index_entry` read in step 2
  — never via a second `renormalize` call. This is what closes the
  divergence hazard a reviewer raised against an earlier draft (work-tree
  bytes need not equal the pre-mutation index entry — a renormalize-based
  rollback would silently stage whatever the work tree currently holds
  instead of restoring what was there before): `restore_index_entry` writes
  the captured mode+sha directly and never reads the work-tree file, so it
  is correct independently of whatever the work tree contains at rollback
  time.
- No exception-based control flow beyond catching `OSError` around the
  filesystem steps.
- `--to` is never accepted by `CommandShare`; the CLI rejects `--shared`
  combined with `--to` before constructing either command class (see CLI
  adapters below), so `CommandShare.__init__` has no `source` parameter at
  all — there is nothing to misuse.

### `src/tools/dot/cli.py` — `localize --shared`

```python
@cli.command("localize", help="Make a file or directory host-specific")
@click.argument("path")
@click.option("--to", "source", help="Source path (default: .local/<path>)")
@click.option("--shared", is_flag=True, help="Register a host-value filter instead of moving the file")
def localize(path: str, source: str | None = None, *, shared: bool = False) -> None:
    if shared and source is not None:
        console.panic("--shared cannot be combined with --to")
        return
    shell = ShellAdapter(suppress_logging=True)
    if shared:
        from dot.commands.localize.share import CommandShare
        console.report_result(CommandShare(shell=shell, dotfiles_root=_dotfiles_root(), path=path).execute())
        return
    from dot.commands.localize.localize import CommandLocalize
    console.report_result(CommandLocalize(shell=shell, dotfiles_root=_dotfiles_root(), path=path, source=source).execute())
```

Plain `localize` (no `--shared`) is byte-for-byte unchanged behavior; the new
option only branches before either command class is imported, so neither
import path changes for the existing case.

## Data flow

**Author host, first share:** `dot localize --shared <path>` → `CommandShare`
validates → reads current bytes for the dry-clean count → appends
`.gitattributes` line → `cfg add --renormalize -- <path>` (git invokes the
clean filter on the *index* content — the smudge filter never runs here,
since renormalize re-stages from the work-tree through clean) → stages
`.gitattributes`. The work-tree file itself is untouched throughout; only the
index now holds tokenized bytes.

**Commit + push (author host):** ordinary `dot commit` / `dot push` — no
filter-specific code; git invokes clean again on any subsequent `add` of that
path (e.g. after a tool rewrites it), tokenizing before the object reaches the
index.

**Pull (second host):** `dot pull` → `cfg pull` triggers git's own checkout
machinery, which runs the smudge filter — `dot filter smudge <path>` — on the
incoming tokenized blob, writing real host B bytes to host B's work-tree.
`DotGitService.__init__`'s `_ensure_filter_driver` has already configured the
driver on host B before this pull runs (every `DotGitService` construction
self-heals it, same as the hooks path).

**Tool rewrite + status:** a tool on host B rewrites the file with host B's
absolute paths (identical bytes to what smudge produced, if the tool is
idempotent) → `cfg status` diffs working tree against the clean-filtered
index view (git's own `clean` comparison), so unchanged content reads clean
even though the on-disk bytes differ from the token-bearing blob.

**Filter subprocess itself:** stdin bytes → `hostfilter.clean`/`smudge` → 
stdout bytes, no git/CLI object touched in-process — this is the leaf of the
data flow, deliberately decoupled from the `DotGitService`/`CommandResult`
pipeline everything else in dot flows through.

## Reuse inventory

- `buvis.pybase.filesystem.atomic_write_text` / `atomic_write_bytes`
  (`src/lib/buvis/pybase/filesystem/atomic_write.py`) — reused by
  `CommandShare` for the `.gitattributes` write/rollback, same as
  `hostlinks/manifest.py:append_entry` already does for the host-links
  manifest.
- `dot.hostlinks.manifest.read_manifest` / `_validate_path` — reused directly
  for `CommandShare`'s "already listed in host-links manifest" refusal
  (check 5); no duplicate manifest-reading logic.
- `DotGitService._literal` / `shlex.quote` shell-safe-pathspec helper
  (`git/service.py:22`) — reused by the new `renormalize` method exactly as
  every existing path-taking method (`stage`, `diff`, `ls_files`, …) already
  uses it.
- `DotGitService.ls_files`, `.list_secrets`, `.stage` — reused by
  `CommandShare` instead of writing new git-status/secret-check code; same
  pattern `CommandLocalize._check_preconditions` already uses for tracked/
  secret checks.
- `CommandLocalize._check_preconditions` / `_mutate` / `_rollback` shape
  (single-error-string refusal list, then an ordered mutation with inline
  rollback) — `CommandShare` follows the same structure rather than
  inventing a different validation/rollback idiom.
- `buvis.pybase.result.CommandResult` — every command-layer return, no new
  result type.
- `buvis.pybase.configuration.settings.GlobalSettings.auto_update` /
  `BUVIS_AUTO_UPDATE` env gate (`configuration/settings.py:47`,
  `updater/__init__.py:47`) — already exists and already does exactly what
  the configured filter command's `BUVIS_AUTO_UPDATE=false` prefix needs; no
  new update-suppression mechanism required, confirming the PRD's filter
  command string is correct as specified.
- Greps tried (verb/noun synonyms, each proved against a known hit first):
  `atomic_write|atomic_write_text|atomic_write_text\(` (hit: manifest.py),
  `renormalize|re-?normalize` (no existing hits — new), `clean.*filter|smudge`
  (no existing hits — new, confirms this is genuinely new plumbing, not a
  rename of something that already exists), `gitattributes|\.gitattributes`
  (no existing hits outside this design), `shlex.quote|_literal\(` (hits
  throughout `git/service.py` — the pattern to reuse), `GIT_WORK_TREE` (no
  existing hits — new env read), `BUVIS_AUTO_UPDATE|auto_update` (hit:
  `configuration/settings.py`, `updater/__init__.py` — confirms existing gate).

## Alternatives considered

1. **Smallest-diff version — shell out to `git config` and hand-roll the
   token substitution inline inside `cli.py`'s filter commands, with no
   separate `hostfilter.py` module.** Rejected: the PRD requires exhaustive
   byte-level unit coverage (POSIX/Windows boundaries, CRLF/BOM, round-trips)
   that is far easier to drive against a pure, dependency-free module than
   against Click command functions wired to stdin/stdout. The module is ~40
   lines of substitution logic plus boundary/regex helpers — not an
   abstraction for its own sake, since the CLI commands, `CommandShare`'s
   dry-clean count, and the test suite all need the same three functions
   independently of Click or git.
2. **Persistent filter process (git's long-running filter protocol,
   `filter.dot-host.process`) instead of per-invocation `dot filter
   clean/smudge %f`.** Rejected per the PRD's own Risk: per-file CLI startup
   cost is accepted; the persistent protocol is materially more complex
   (a stateful server loop, packet framing) for a dotfiles repo with at most
   a handful of shared files. Deferred explicitly until measured need, not
   designed around speculatively.
3. **Chosen: three config keys + a stateless `%f`-driven filter command +
   one new command class, mirroring `CommandLocalize`'s existing shape.**
   Matches the codebase's existing "one seam, one command class per action"
   pattern exactly, keeps the filter subprocess trivially simple (one read,
   one transform, one write, matching the PRD's explicit anti-recursion
   requirement), and needs no new dependency.

## Risks & edge cases

- **Undefined driver before first `dot` invocation on a fresh clone.** Git
  treats an unconfigured `filter.dot-host.*` as a no-op passthrough, so a
  tokenized blob checks out containing literal `@HOME@` bytes until some
  `dot` command runs and `_ensure_filter_driver` self-heals the config —
  covered by `test_shared_real_git.py`'s "missing dot executable" and setup
  self-heal scenarios; documented recovery path in Phase 2.
- **Reserved token already present in content a user wants to share
  literally.** `CommandShare` refuses at share time (check 8); `dot filter
  clean` refuses the same way at commit time for already-shared files whose
  content later changes to include the literal token — both refusals are
  intentional dead ends, not bugs to work around.
- **Likely next change 1 — sharing a directory, not just one file.** This
  design's directory refusal (check 3) and the PRD's explicit "directory
  opt-in is unsupported" scope exclusion mean a future directory-share PRD
  would need its own attribute-line-per-file (or a directory pattern)
  decision; nothing here blocks that, since `.gitattributes` already
  supports directory patterns independently of this PRD's one-line-per-file
  choice.
- **Likely next change 2 — variables other than `HOME`.** `hostfilter.py`'s
  single-token design (`TOKEN = b"@HOME@"`) would need generalizing to a
  token-to-resolver mapping; out of scope here, but the pure-function shape
  (`clean(data, value)` / `smudge(data, value)`) does not bake in HOME
  specifically at the substitution-algorithm level, only at the `resolve_home`
  call site — so that generalization is additive, not a rewrite.
- **Likely next change 3 — raw-index drift detection (noticing a shared file
  whose index content no longer round-trips).** Out of scope per the PRD;
  this design's `renormalize` method is the building block such a check
  would call, so it is not precluded.
- **`cfg add --renormalize` semantics are asserted, not assumed.** Per PRD
  R11/Git lifecycle compatibility: `test_shared_real_git.py` checks final
  index/work-tree bytes after every git operation, never just exit codes.

## Test strategy outline

- `test_hostfilter.py`: pure unit tests, no git/filesystem — boundary
  matching (both sides, including token-adjacent context), repeated
  matches/counts, POSIX round-trip property pair, non-UTF-8/CRLF/BOM
  preservation, reserved-token `ValueError`, all three Windows spellings,
  drive-letter case-insensitivity with path-case preservation, suffix
  separator preservation, and `resolve_home`'s
  `GIT_WORK_TREE`/`DOTFILES_ROOT`/`Path.home()` precedence (including
  relative `GIT_WORK_TREE` resolved against a supplied `cwd`).
- `test_git_service_filter.py` (+ existing `test_git_service.py`,
  `test_git_service_hooks_path.py`, `test_setup.py` re-run green): the three
  config values are written only when `filter.dot-host.clean` is unset,
  existing keys untouched when already set, a failure on any one of the
  three writes unsets every key that did get set (including the
  `required`-fails-after-clean-and-smudge-succeed case), `renormalize`
  builds a shell-safe literal pathspec after `--`, `check_attr_filter` is
  called with a plain shell-quoted pathname (never a `:(literal)` pathspec)
  and correctly parses a `-z`-delimited record including an `unspecified`
  value as `None`, `capture_index_entry` parses `ls-files -s` output
  including the no-entry case, and `restore_index_entry` issues
  `update-index --cacheinfo` for a captured entry versus `rm --cached` for
  `None`.
- `test_share.py`: every refusal (all 12 checks) leaves file/registry/index
  unchanged (fully mocked `DotGitService`); count/zero output messages;
  operation order including the capture-before-mutate step; an
  effective-attribute mismatch (checked right after the `.gitattributes`
  write, before any git call) rolls back with only the work-tree text
  restore and returns the conflicting-filter error, proving no renormalize
  or stage call happens on that path; exact `.gitattributes` work-tree
  restoration on renormalize failure (both pre-existing-content and
  file-did-not-exist-before cases); a staging failure rolls back via
  `restore_index_entry` called with the captured pre-mutation entry (proving
  it is the captured value staged back, not a re-derived one) and returns
  the rolled-back error; a failed `restore_index_entry` during that rollback
  returns the distinct "ROLLBACK FAILED" error rather than a false
  "rolled back" claim; no move/link/manifest mutation ever happens.
- `test_filter_cli.py` (+ `test_localize.py` re-run green): `--shared`
  dispatch, `--shared` + `--to` rejection, unchanged plain-localize dispatch,
  hidden filter group not listed in `--help`, byte-exact stdout for clean and
  smudge, reserved-token exit 1 with the single pinned stderr line and empty
  stdout, and proof (via mock/spy) that the filter commands never construct
  `DotGitService`, call `console`, or check `BUVIS_AUTO_UPDATE`.
- `test_shared_real_git.py`: real temporary bare repo + separate clone
  ("host B"), isolated `HOME`/`GIT_CONFIG_GLOBAL`/PATH (interpreter bin
  prefixed) — index-token assertions, same-host tool-rewrite-then-status,
  checkout smudge, setup self-heal-before-checkout ordering, two-host
  push/pull producing B's own home in B's work-tree with clean status,
  anchored attribute line excluding a same-named nested file, shell-unsafe
  path handling, missing-`dot`-binary required-filter hard failure, and the
  existing divergence-patch / reverse-hunk scenarios re-run with shared,
  home-bearing content to prove `save_divergence_patch` and
  `apply_reverse_to_worktree` need no change.

## Review log

- Non-blocking: `GIT_WORK_TREE` as the primary home-resolution signal for filter subprocesses is asserted from the PRD, not independently verified against real Git behavior; `Path.home()` fallback covers the ordinary case regardless. `test_shared_real_git.py` should assert the `GIT_WORK_TREE`-driven branch explicitly, not rely on the fallback.
- Non-blocking: `_ensure_filter_driver`'s config writes (post-fix) check `err` where the pre-existing `_ensure_hooks_path`/`_ensure_fetch_refspec` self-heals do not — an intentional, narrower deviation justified by `required=true`'s hard-fail consequence (see Interfaces & contracts above), not a style inconsistency to "fix" in the older methods.
- Non-blocking: every `DotGitService` construction now pays one additional `git config` read (and occasionally up to 3 writes) — additive overhead on an already-accepted self-heal pattern (hooks path, fetch refspec).
- Non-blocking: a raw `git clone`/`cfg checkout` performed outside `dot setup`/`dot materialize` bypasses `_ensure_filter_driver` and checks out literal `@HOME@` bytes; mitigation is the documented Phase 2 recovery procedure, not a code-level guard — accepted for a dotfiles CLI, not a production service.
- Question (resolved by inspection, no doc change needed): the parent `cli` Click group's `buvis_options`/update-check processing runs before Click dispatches into `filter clean`/`filter smudge`, but that processing goes through `console`/`click.echo`, never raw stdout — and the acceptance tests assert byte-exact stdout, which would catch any contamination. No separate guard needed.
- dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 4, question 2
- Non-blocking (dispatch 2): tracked-regular-file enforcement did not previously reject symlinks/special modes — fixed via check 12 above.
- Non-blocking (dispatch 2): `dot filter clean/smudge %f` lacked an option terminator for leading-dash filenames — fixed by configuring `-- %f` above.
- Non-blocking (dispatch 2): installing the filter driver does not retroactively rewrite files already checked out with literal `@HOME@` bytes from before the driver existed; this is the documented Phase 2 recovery procedure (save edits, run `dot`, remove and re-checkout the affected file), not a code-level auto-repair — accepted as-is for a dotfiles CLI.
- Question (dispatch 2, recorded, not resolved — out of scope per PRD): smudge always writes a forward-slash home, so Windows-spelled shared content checked out on a POSIX host keeps its Windows path separators past the home prefix (e.g. `C:\Users\Alice\settings` → `/home/bob\settings`). The PRD explicitly scopes Windows/POSIX cross-sharing out of v1 ("Windows spelling normalization is supported within Windows; Windows/POSIX sharing is outside v1") — this is that exact exclusion observed at the byte level, not a new gap.
- dispatch 2 (codex): cardinal-sin 0, blocker 3, non-blocker 4, question 1
- dispatch 3 (codex): verification pass found all 3 prior fixes incomplete — check-11's "no staged diff" precondition didn't prove work-tree==index, only index==HEAD; `filter_driver_configured` checked only `clean`, not `required`; `check_attr_filter` passed a `:(literal)` pathspec to a command that takes pathnames, so the check always read "unspecified"; and the effective-attribute rollback reused the renormalize-based reconstruction that has the same divergence problem as the original rollback. Resolved by redesigning the rollback mechanism entirely: `capture_index_entry`/`restore_index_entry` replace every renormalize-based "undo" with an exact index-sha restore that needs no work-tree/index-equality precondition at all, which let the "no staged diff" refusal (old check 11) be deleted rather than fixed; `filter_driver_configured` now reads all three keys; `check_attr_filter` now takes a plain pathname; the effective-attribute check now runs immediately after the `.gitattributes` write and before any git mutation, so its own rollback is the cheapest one (work-tree text only) rather than reusing the index-touching rollback. No dispatch 4 (3-dispatch ceiling reached); the fixes above were re-verified against this session's own line-by-line reading of Git's `check-attr`/`update-index`/`ls-files` contracts rather than a further codex call.
- dispatch 3 (codex): cardinal-sin 0, blocker 4, non-blocker 0, question 0
