# Discovery: dot host-specific config links

## Classification

Depth: comprehensive | Date: 2026-10-12

Source: `idea.md` and `qa-log.md` beside this file.

## Problem

Some config sits where a tool expects it but differs per machine
(`~/.config/gita/repos.csv`, `~/.config/buvis/buvis-postup.yaml`,
`~/.config/buvis/buvis-bim.yaml`, `~/.config/klyreon/`, a `~/bin` script bound
to one volume). Tracked, one host's values leak to every host. Untracked, the
file has no home in dotfiles and glean keeps asking about it. dot has no way
to say "this path is per host" and no way to set up a fresh machine, so the
pre-commit gate (`core.hooksPath`, untracked bare-repo config) is missing on
any machine nobody wired by hand.

## Requirements

### Must have

- **M1 Manifest**: one tracked file in the dotfiles repo lists host-specific
  paths, one entry per line, both sides `$HOME`-relative:
  `<target> => <source>`. Target = where the tool looks (becomes a link).
  Source = the host-local real file or dir (never tracked). Blank lines and
  `#` comments allowed. Invalid lines (no `=>`, absolute path, `..` escaping
  `$HOME`, duplicate target) are reported, not guessed.
- **M2 Materialize**: `dot materialize` creates each missing link
  target -> source. Runs from `post-checkout`, `post-merge` and
  `post-rewrite` hooks, and by hand.
- **M3 Never clobber**: target exists and is not the expected link (tracked
  file, real file, link elsewhere) -> report and skip. Never delete or
  overwrite user data.
- **M4 Missing source**: entry listed but no source on this host -> report
  "no host file", create nothing.
- **M5 Idempotent and quiet**: all links current -> no change, no output.
  Dangling links (source removed) are reported, never deleted.
- **M6 Link kind**: symlink for files and dirs on macOS/Linux. Windows:
  symlink; junction for dirs; refused file symlink -> report "enable
  Developer Mode" and skip. No copy or hardlink fallback.
- **M7 Status**: `dot status` and the TUI show link problems (M3/M4/M5
  reports) through the same command class.
- **M8 Localize**: `dot localize <path> [--to <source>]` moves the file/dir
  to its source (default `.local/<path>`), appends the manifest line, links,
  untracks it if tracked (`rm --cached`, keeps disk copy), stages the
  manifest. Refuses when the source already exists or the path is a link.
- **M9 Pull rescue**: `dot pull` fetches first, reads the incoming manifest,
  and for each manifest target the incoming commits delete, moves the local
  file to its source (only when the source is missing) before merging. Then
  materialize links it. Without this, untracking on host A deletes host B's
  real file on pull.
- **M10 hooksPath self-heal**: `DotGitService` init sets
  `core.hooksPath=~/.config/buvis/hooks` when unset (same pattern as the
  fetch refspec) and warns when the hooks dir or `pre-commit` is missing.
- **M11 dot setup**: clone the bare repo, check out into `$HOME`, set
  hooksPath, run materialize. Checkout conflicts with existing files are
  reported, not overwritten.
- **M12 All-interface**: materialize, localize and link status are command
  classes returning `CommandResult`; hook, CLI and TUI call the same class.
- **M13 Glean**: links settle in glean (add each source parent, or `~/.local`,
  to glean `link_roots` in the glean config; no glean code change needed).

### Nice to have

- `dot unlocalize <path>`: reverse M8 (move back, drop manifest line).
- Hook prints one line per change, so a pull shows "linked
  .config/gita/repos.csv".

### Out of scope

- Backing up the host-local sources (Kopia/Backblaze cover `~/.local`; verify,
  don't build).
- Copy, hardlink or drift-sync fallbacks on Windows.
- Making raw `git pull` safe (git has no pre-pull hook); documented only.
- Templating or merging host values into a shared file.
- Pull divergence reporting (intake 00089).

## Constraints

- Hook bodies are Python or call `dot`; no POSIX-only shell logic (Windows).
- A hook must never fail a checkout/merge: if `dot` is missing it warns and
  exits 0.
- No new dependencies; `pathlib`/`os.symlink` cover links (junctions via
  `_winapi.CreateJunction` or `mklink /J`).
- `.local/` stays blocked by `glean check-staged` (R6, already enforced); the
  manifest itself must sit outside `.local/`.
- Writes to the manifest use `pybase.filesystem.atomic_write`.

## Codebase Context

- **Relevant code**: `src/tools/dot/git/service.py` (`DotGitService`, bare-repo
  wrapper, `_ensure_fetch_refspec` self-heal at init, `pull()`, `rm()`),
  `src/tools/dot/cli.py` (Click group, lazy imports), `src/tools/dot/commands/*`
  (one dir per verb), `src/tools/dot/commands/status/status.py`,
  `src/tools/dot/tui/` (screens/commands).
- **Conventions**: one `commands/<verb>/<verb>.py` class per verb returning
  `CommandResult`; CLI renders with `console.report_result`; git via the
  `cfg` alias through `ShellAdapter`; tests mock the shell.
- **Integration points**: `DotGitService.__init__` (M10), `pull()` (M9 fetch
  before merge), `CommandStatus.execute` (M7), new `materialize`, `localize`,
  `setup` verbs; tracked hooks in `~/.config/buvis/hooks/` (dotfiles repo, not
  gems) gain `post-checkout`, `post-merge`, `post-rewrite`.
- **Existing gate**: `~/.config/buvis/hooks/pre-commit` (sh, runs
  `glean.py check-staged`); `core.hooksPath` is set on this host only.
- **Glean**: `glean.py` settles a symlink when it resolves under a
  `link_roots` entry (`scripts/glean.py:187-194`); junctions are not
  `is_symlink()`, so Windows dir links will show as candidates.

## Approach

- **Chosen**: explicit tracked manifest of `target => source` lines; dot
  owns linking, moving, rescue on pull, and bootstrap. Split into 3 PRDs:
  1. **A** manifest + `dot materialize` + three hooks + link status (CLI/TUI).
  2. **B+C** `dot localize` + `dot pull` rescue, shipped together so localize
     never exists without the deletion guard.
  3. **D** hooksPath self-heal + `dot setup`.
- **Why**: the manifest makes host-specific paths explicit and identical on
  every host; only listed paths are touched, so no scan rules or collisions
  with real XDG dirs under `~/.local`.
- **Rejected alternatives**:
  - Scan a mirror root (`~/.local/<rel>` -> `~/<rel>`): collides with
    `~/.local/bin|share|state`, implicit rules.
  - Fixed mirror root + target list: cannot express `bin/backup =>
    .local/bin/backup` style sources.
  - Copy/hardlink fallback on Windows: two copies drift; atomic-save editors
    break hardlinks silently.
  - Per-host manual localize before push: one forgotten host loses data.

## Success Criteria

- Fresh temp `$HOME` test: manifest with a file and a dir entry, sources
  present -> `dot materialize` creates both links; second run prints nothing.
- Target is a real file -> reported, file bytes unchanged.
- Source missing -> reported, no link created.
- Two clones (host A, host B) in tests: A localizes a tracked file and pushes;
  B `dot pull` -> B's original bytes now at the source, target is a link to
  them.
- New clone via `dot setup` -> `core.hooksPath` set, links present; a
  `dot run checkout` fires post-checkout and relinks.
- On this machine: `~/.config/gita/repos.csv` localized; glean reports no
  candidate for it.

## Risks

- **Raw `git pull` bypasses rescue**: document in dot docs; the deleted file
  is recoverable from git history only as the committing host's version.
- **00089 also changes `dot pull`**: sequence B+C and 00089 so they don't
  collide; whichever lands second rebases on the other's fetch-then-merge
  shape.
- **`dot setup` into a non-empty `$HOME`**: checkout refuses on existing
  files; report the conflicting paths and stop, don't force.
- **Windows junctions invisible to glean link settling**: accept for now or
  file a glean change; flagged, not solved here.
- **Hook runs before dot is installed** (fresh machine, first checkout): hook
  warns and exits 0; `dot setup` runs materialize itself.

## Open Questions

- Manifest location and name. Default proposal:
  `~/.config/buvis/host-links` (next to the hooks, plain text, matches the
  `=>` format). create-prd should confirm.
- Should the manifest allow `~`-free sources outside `$HOME` (external
  volume)? Current answer: no, both sides `$HOME`-relative; a volume path
  goes through a `$HOME`-side link the user manages.
- `dot setup` input: remote URL as an argument, or read from a setting?
- Is the `~/.local/bin/<script>` example in `idea.md` meant as `~/bin/<script>`
  (the target)? `~/.local/bin` is itself never tracked.

## Discovery Log

### Q1: Where does the mirror root live?
**Answer**: Reframed by user: the tracked dotfiles repo should register which
paths are host-specific, via a mapping file, and links follow from it. Mirror
location becomes a detail of that mapping, not a scan rule over `~/.local`.

### Q2: What shape does the manifest take?
**Answer**: An explicit per-entry map, both sides `$HOME`-relative, e.g.

```text
.config/gita/repos.csv => .local/.config/gita/repos.csv
bin/backup => .local/bin/backup
```

Left = where the tool looks (link). Right = host-local real file (never
tracked). No fixed mirror root; each entry names its own source.

### Q3: Dir entries, and the link kind on Windows?
**Answer**: Symlink everywhere; files and dirs both allowed. Windows: symlink,
junction for dirs; if a file symlink is refused, report "enable Developer
Mode" and skip. No copy or hardlink fallback.

### Q4: Should dot move a file into host-local storage?
**Answer**: Yes, `dot localize <path>`: move file, write manifest line
(default source `.local/<path>`, `--to` override), link, untrack if tracked,
stage the manifest. Refuses when the source already exists; never overwrites.

### Q5: How do other hosts survive the untrack on pull?
**Answer**: `dot pull` rescues first: fetch, read the incoming manifest, and
for each listed target the incoming commits delete, move the local file to
its source path (when the source is missing) before merging; materialize then
links it. Raw `git pull` stays unsafe; document it.

### Q6: How does a fresh machine get `core.hooksPath`?
**Answer**: Both. `DotGitService` init sets `core.hooksPath` when unset (like
the fetch refspec) and warns when the hook file is missing. New `dot setup`:
clone bare repo, checkout, set hooksPath, materialize.

### Q7: One PRD or several?
**Answer**: 3 PRDs: A (manifest + materialize + hooks + status), B+C
(localize + pull rescue together), D (self-heal + setup).

### Inferred (not asked)
- R6 gate: already enforced by glean `check-staged` built-ins; no work here.
- R7 glean: `link_roots` already settles symlinks; config entry only (M13).
- Backup of sources: out of scope; existing backups cover `~/.local`.
- Hook failure policy: never block git; warn and exit 0 (constraint).
