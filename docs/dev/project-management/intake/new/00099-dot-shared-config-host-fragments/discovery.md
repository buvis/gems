# Discovery: dot shared config: host-value placeholders via git clean/smudge

## Classification
Depth: comprehensive | Date: 2026-10-17
Source: `idea.md` beside this file.
Priority: next autopilot batch (Q3).

## Problem

Some tracked config is almost entirely shared, but a few values in it differ
per machine, and tools rewrite those values on their own. Tracked as is, every
sync flips the file between hosts; localized (00090), the shared 95% stops
being shared. The live case: `~/.claude/settings.json` (20 lines with
`/Users/bob`) and `~/.codex/hooks.json` (22 lines). The herdr agent-activity
plugin rewrites its hook entries with absolute paths on every start, so a hand
edit to `$HOME` is undone within minutes and the tracked files flip on every
sync. Until fixed, every `dot pull` on the second host conflicts or saves a
divergence patch for these two files.

## Requirements

### Must have
- **R1 Filter driver `dot-host`**: `dot filter clean <path>` and
  `dot filter smudge <path>` (hidden Click subcommands) read the file bytes
  from stdin and write the converted bytes to stdout. Clean replaces this
  host's home path with the token `@HOME@`; smudge replaces the token with
  this host's home path. Byte-safe: no newline, encoding or BOM changes;
  bytes outside a match are untouched. `clean(smudge(x)) == x` for tokenized
  `x`; `smudge(clean(y)) == y` for raw POSIX `y`.
- **R2 Home value**: the work-tree root, resolved as `GIT_WORK_TREE` (git
  exports it to filter processes when run with `--work-tree`), else
  `DOTFILES_ROOT`, else `Path.home()`; trailing separator stripped. On
  Windows the drive letter compares case-insensitively.
- **R3 Safe matching**: a match needs a boundary on both sides: the byte
  before and the byte after the home path are not `[A-Za-z0-9_.-]`, or the
  match touches the start or end of the input. So `/Users/bob/x`,
  `'/Users/bob'`, `"/Users/bob"`, `=/Users/bob`, `file:///Users/bob` match;
  `/Users/bobby`, `/Users/bob.bak`, `/Users/bob-old`, `/opt/Users/bob` do not.
  Tests cover each listed case.
- **R4 Windows spellings (Q1)**: clean recognizes `C:\Users\bob`,
  `C:\\Users\\bob` and `C:/Users/bob`; smudge always writes `C:/Users/bob`.
  On POSIX the three spellings collapse to one, so files tokenized on either
  platform smudge correctly on the other.
- **R5 Token guard**: clean exits 1 with one stderr line
  (`dot filter: <path> already contains @HOME@; the token is reserved`) when
  the raw input holds the literal token, so a lossy round trip never reaches
  the index. With `required = true` git aborts the command and shows the line.
- **R6 Driver self-heal**: `DotGitService.__init__` writes, when
  `filter.dot-host.clean` is unset, the three keys into the bare repo config:
  `clean = BUVIS_AUTO_UPDATE=false dot filter clean %f`,
  `smudge = BUVIS_AUTO_UPDATE=false dot filter smudge %f`,
  `required = true`. Same pattern and placement as `_ensure_hooks_path`
  (`src/tools/dot/git/service.py:53`). A set value is never changed. This
  also covers `dot setup`: the service is built before `cfg checkout`
  (`commands/setup/setup.py:38-46`), so the first checkout smudges.
- **R7 Opt-in: `dot localize --shared <path>` (Q2)**: with the flag, localize
  does not move or link anything. It appends `/<path> filter=dot-host` to the
  tracked `<root>/.gitattributes` (atomic write; created when missing;
  leading `/` anchors the pattern so `settings.json` cannot match other
  files of that name), runs `cfg add --renormalize -- <path>` so the index
  holds tokens, and stages `.gitattributes`. Info lines:
  `shared <path>: <n> host value(s) replaced` (n from a dry clean of the
  work-tree bytes; `n == 0` gives `no host value found in <path>; filter
  active for future writes`), `staged .gitattributes`. Renormalize failure
  removes the appended line and returns the error; stage failure keeps
  everything and warns `run 'dot add .gitattributes'`, like localize.
- **R8 Refusals for `--shared`** (nothing changed): path missing; path not
  tracked (`ls_files` empty; message names `dot add`); path is a link; path
  is a directory (files only in v1); path listed in the host-links manifest;
  path registered with git-secret; path is `.gitattributes`; path already
  has a `filter=dot-host` line; work-tree bytes already contain `@HOME@`;
  path needs quoting in `.gitattributes` (whitespace, `#`, `!`, `[`, `\`).
  Plain localize (no flag) keeps its current refusal set and behavior.
- **R9 Tool writes are a no-op**: after sharing, rewriting the file with this
  host's absolute home paths (any accepted spelling) leaves `dot status`
  clean. Real-git test.
- **R10 Two-host round trip**: host A shares a file, commits, pushes; host B
  (different root) runs `dot pull`: B's work-tree file holds B's home, the
  index blob holds tokens, `dot status` is clean. Real-git test modeled on
  `tests/tools/dot/test_pull_two_hosts.py`.
- **R11 Patch paths keep working**: a divergence patch (00095) and a TUI hunk
  revert (`DotGitService.apply_reverse_to_worktree`) on a shared file apply
  cleanly; `git apply` runs clean on the work-tree side and smudge when
  writing, so no dot change is expected, but a real-git test proves it.
- **R12 Filter output discipline**: `dot filter` writes only file bytes to
  stdout and never goes through `console` (it writes to stdout,
  `adapters/console/console.py:56`). Its single error line is the one
  sanctioned `sys.stderr` write in dot, marked with a comment naming this
  requirement. The config command sets `BUVIS_AUTO_UPDATE=false` so the
  update check (`configuration/click_integration.py:131`) can never re-exec
  inside a filter.
- **R13 Docs and changelog**: `docs/source/tools/dot.rst` (localize section
  gains `--shared`; new section on sharing: `.gitattributes`, driver config,
  the token, diffs show `@HOME@`, Windows forward slashes, raw git without
  `dot` on PATH fails loudly), `README.md`, `CHANGELOG.md` Added entry.

### Nice to have
- `dot status` warning when a path carries `filter=dot-host` but its index
  blob still holds this host's raw home (not renormalized, e.g. after a hand
  edit of `.gitattributes`). The index self-corrects on the next commit from
  a host with a different home, so v1 skips it.
- Undo (`--unshare`): remove the line and renormalize. v1 documents the two
  manual steps instead.

### Out of scope
- Layer 2 structural overlay (base + host overlay deep merge): only when a
  host-only key exists.
- Variables other than `HOME` (`USER`, `HOST`) and per-host override files.
- herdr `plugins.json`: stays untracked with the `plugins.txt` sysup sync.
- Directory or glob patterns for `--shared`.
- Changing `glean check-staged` (lives in agent-skills, not gems) to block
  raw home paths in shared files.
- A TUI binding: localize has none (`src/tools/dot/tui/` has no localize
  call), and the filter itself needs none; git runs it for the TUI too.
- Sharing the two live files on the user's hosts: manual follow-up after
  release (config outside gems, same as the 00088/00090 glean settling).

## Constraints
- Python 3.11+ filter body, stdlib only (`re` on bytes); no `sed`, no new
  dependency. One command class per action behind the CLI (all-interface
  rule); `dot filter` is plumbing that wraps the same pure functions.
- `.gitattributes` is tracked at the work-tree root (`~/.gitattributes`,
  currently untracked in `~/.buvis`); the driver config is per host in the
  bare repo, like `core.hooksPath`.
- `required = true` is deliberate: a missing `dot` fails the git command
  rather than committing raw host values. `dot` resolves on PATH in agent
  sandboxes too (`mise which dot` -> pipx install), so `git status` on
  `~/.buvis` from a session keeps working.
- Cold `dot` start is about 130 ms (measured 2026-10-17, best of 3, with
  `BUVIS_AUTO_UPDATE=false`; bare python 14 ms). Two or three shared files
  add well under half a second to `git status`, `diff` and TUI refresh.
  `# ponytail:` ceiling: a thin `dot-filter` entry point or the
  `filter.<driver>.process` protocol if the list of shared files grows.
- Git 2.56 on this host; `add --renormalize` needs 2.16+.

## Codebase Context
- **Relevant code**: `src/tools/dot/git/service.py` (self-heal pattern
  `_ensure_fetch_refspec`/`_ensure_hooks_path`, `stage`, `ls_files`,
  `list_secrets`, `apply_reverse_to_worktree`, `pull` with divergence save);
  `src/tools/dot/commands/localize/localize.py` (path normalization,
  precondition table, rollback shape, `MANIFEST_PATH` check);
  `src/tools/dot/hostlinks/hooks.py` (`BUVIS_AUTO_UPDATE=false` precedent for
  a git-spawned dot process); `src/tools/dot/cli.py` (`localize` command,
  lazy imports); `src/tools/dot/divergence.py` (patch from `git diff`, applied
  later with `git apply`).
- **Conventions**: command classes return `CommandResult`, CLI renders via
  `console.report_result`; info/warning line formats mirror localize; tests
  are class-based under `tests/tools/dot/`, mocked `ShellAdapter` for command
  strings plus real-git tests (`test_setup_real_git.py` prefixes `PATH` with
  `Path(sys.executable).parent` so git-spawned hooks find `dot`;
  `test_pull_two_hosts.py` builds origin + two bare clones with work-trees).
  Real-git tests on macOS must `resolve()` tmp roots: `/var` vs
  `/private/var` would make the literal home match fail.
- **Integration points**: `DotGitService.__init__` (new `_ensure_filter_driver`),
  `cli.py` `localize` (new `--shared` flag, dispatch to the share command
  class) and a hidden `filter` group, new pure module for clean/smudge (e.g.
  `src/tools/dot/hostfilter.py`), new command module beside localize, docs.
- **Similar implementations**: 00091 self-heal + `check_hooks` (config keys
  written once, never overwritten); 00090 localize (opt-in command that edits
  a tracked registry file and stages it); git's own `ident` filter
  (`$Id$`) is the model for a reserved token.

## Approach
- **Chosen**: git clean/smudge filter driver with one reserved token
  (`@HOME@`), opted in per file through a tracked `.gitattributes`, driver
  config self-healed per host, surfaced as `dot localize --shared <path>`.
- **Why**: tool writes survive (clean maps them back to the token, so the
  index never changes); the real file stays where the tool expects it; git
  runs the filter on every checkout and pull with no extra dot step; diffs
  show the shared change. Token `@HOME@` over `{{HOME}}`: autoconf style,
  unlikely in dotfiles, and `{{...}}` collides with Jinja-style templates
  that may live in the repo; the token guard (R5) makes the reservation
  enforceable either way.
- **Rejected alternatives**:
  - Render from template on pull: overwrites tool writes on the next pull
    or needs a capture step.
  - Layer 2 overlay now: arrays (hook lists) make the base/overlay split
    ambiguous; no host-only key exists yet.
  - Hand-written `$HOME`: herdr rewrites it to an absolute path on start.
  - Localize plus manual sync, per-host branches: drop shared content or
    need a merge per host.
  - Format-aware Windows smudge: an extension table for a case with no
    Windows host today (Q1).
  - A `dot status` "driver missing" warning (idea R4): the self-heal in
    `DotGitService.__init__` makes it unreachable from dot; raw git before
    the first dot run is documented instead.

## Success Criteria
- Pure filter tests pass for every R3 boundary case, the three Windows
  spellings, the token guard, CRLF and non-UTF-8 bytes unchanged.
- Real-git: share a file, rewrite it with raw home paths -> `dot status`
  clean; `cfg checkout -- <path>` restores this host's path; `cat-file` of
  the index blob shows the token and no home path.
- Two-host real-git (R10) passes; B's `dot pull` reports at most the
  expected one-time divergence patch for that file.
- Hunk revert and divergence patch apply on a shared file (R11).
- `uv run pytest -m dot` and `uv run mypy src/tools/dot` pass; docs name
  `--shared` and the token.

## Risks
- **Raw git before the first dot run on a host**: after `.gitattributes`
  lands but before any dot command self-heals the driver, raw `git status`
  shows the file modified and raw `git add` would commit host paths.
  Mitigation: docs say "run `dot status` once after upgrading"; dot's own
  pull self-heals before merging. Low: both hosts pull through dot.
- **Attribute ordering inside one checkout**: git reads `.gitattributes`
  from the index during checkout (`GIT_ATTR_CHECKOUT` direction), so the new
  line applies to files written in the same merge. The two-host test
  confirms it.
- **One-time divergence noise on host B**: B's work-tree may differ from
  its index before the first pull (its own raw paths); 00095 saves a patch
  and resets, then the pull smudges B's home back. Expected, documented.
- **Filter cost per file per git call**: about 130 ms each; fine at two or
  three files. Upgrade path named in Constraints.
- **`required = true` with `dot` off PATH** (GUI git clients, cron): checkout
  and add fail loudly. Accepted by design; documented.
- **Token appearing in real content**: guard refuses at clean time, so the
  failure is loud and names the file.

## Open Questions
- Module and class naming for the share action behind `localize --shared`
  (separate `CommandShare` beside localize, or a `shared=True` branch inside
  `CommandLocalize`): create-prd decides; the discovery leans to a separate
  class because the precondition set and mutation differ entirely.
- Whether the `.gitattributes` line should be written through the git
  service (to keep the file edit and the stage together) or with
  `atomic_write_text` like the host-links manifest: either is fine; mirror
  `append_entry` unless design finds a reason not to.

## Discovery Log

### Inferred from idea.md (not asked)
- **Problem validation**: specific pain point hit on 2026-10-16: `~/.claude/settings.json` (20 lines with `/Users/bob`) and `~/.codex/hooks.json` (22 lines) flip between hosts because the herdr agent-activity plugin rewrites absolute hook paths on every start.
- **Approach**: Layer 1 (git clean/smudge filter with placeholders) chosen; Layer 2 (structural overlay) deferred until a host-only key exists; hand-written `$HOME`, localize+sync and per-host branches rejected.
- **Variables**: `HOME` only. `USER` and `HOST` wait for a real case; the username inside a home path is already covered by `HOME`. Per-host override files for variable values dropped (no case).
- **Token**: `@HOME@` (rationale in Approach); the open question in the idea is closed by the token guard, which makes any choice safe.
- **Constraints**: Python filter body (no `sed`), one command class behind CLI (all-interface rule), macOS/Linux/Windows.
- **herdr `plugins.json`**: stays untracked with the `plugins.txt` sync; it churns on `installed_unix_ms`, which no placeholder fixes.
- **Idea R4 (setup + status warning)**: replaced by the `DotGitService.__init__` self-heal, which runs inside `dot setup` before checkout and on every dot command; renormalize happens in the opt-in command, not in setup.

### Brownfield findings (code answered, not asked)
- No `.gitattributes` is tracked in `~/.buvis` (checked with `ls-tree -r HEAD` against known-tracked controls).
- `localize` has no TUI binding; parity needs none for `--shared`.
- Cold `dot` start 130 ms; the update check runs on every root invocation unless `BUVIS_AUTO_UPDATE=false`.
- `console` writes to stdout, so the filter cannot use it (R12).
- `dot` resolves on PATH inside the agent sandbox via the mise pipx install.

### Q1: Windows spelling contract (native `C:\Users\bob`, JSON-escaped `C:\\Users\\bob`, Git Bash `C:/Users/bob`): one token with forward-slash smudge, format-aware smudge, or defer Windows?
**Answer**: One token, forward-slash smudge. Clean maps all three spellings to `@HOME@`; smudge writes `C:/Users/bob` on Windows. A tool that rewrites it to backslashes cleans back to the same token, so the index never flips.

### Q2: Name for the opt-in command (`dot share`, `dot template`, `dot portable`, or a flag on `dot localize`)?
**Answer**: `dot localize --shared <path>`. No new command. The flag changes what localize does: it adds the `.gitattributes` line and renormalizes, and does not move or link the file. Help text and docs must say so, and the refusal set differs from plain localize (R8).

### Q3: When does this need to land?
**Answer**: Next autopilot batch. The pain is live: both files flip on every sync and each herdr start re-breaks a hand fix.

### Contradiction check
Q2 picks a flag on a command whose plain form moves and links, while the flag does neither; not a contradiction but a help-text duty (R7). No other answers conflict with the idea or each other.
