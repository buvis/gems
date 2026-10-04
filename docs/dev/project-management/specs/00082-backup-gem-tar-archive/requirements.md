# backup gem: config-driven tar-archive capability (git-src) v1

<!-- requirements; migrated from PRD 00082 flat file -->

## Problem

`/Users/bob/.local/bin/backup-git` is a standalone bash script that tars
`~/git/src` into a timestamped `~/.local/backup/git-src-*.tar.gz`, dropping ~35
reproducible-artifact directories via hardcoded `tar --exclude` flags, then
`chmod 600`s the archive and prints its size. It works, but:

- **The exclude list is baked into the script.** Adding, removing, or overriding
  an exclude means editing bash. There is no gem default, no user-wide override,
  no machine-specific override, and no way to keep a default in one place and
  layer deltas on top.
- **There is no per-repository control.** A repo whose `target/` (or `dist/`,
  `build/`) is real, non-reproducible source is archived without it, and there is
  no way to say "for this one repo, keep `target/`".
- **It is a one-off script, not part of the toolkit.** It shares no structure
  with the config-driven runner pattern the gems are converging on (sysup 00079),
  so it can't grow to a second backup target without another bespoke script, and
  it carries a macOS/Linux `stat` portability split (`stat -f%z` vs `-c%s`).

The user wants a `backup` gem that, like sysup in *architecture only*, runs a set
of configured **capabilities** with arguments. Its first capability wraps the
git-src backup, with excludes that ship as gem defaults, are overridable user-wide
and machine-specifically, and are further controllable per-repo via a `.bkpignore`
file that can both add repo-specific excludes and cancel an inherited default.

> **Relationship to sysup:** backup borrows sysup's *pattern* — a config-driven
> runner over a registry of capabilities with `with:` inputs, dry-run, and a
> structured per-step result — but is an entirely independent gem. It shares **no
> code, no capability registry, and no config schema** with sysup. git-src is
> backup's own first capability.

## Solution

A new gem `src/tools/backup/` structurally analogous to sysup (own `config.py`,
`runner.py`, `capabilities/`, `cli.py`, `default.yaml`, `manifest.toml`), with a
single generic capability shipped in v1:

- **`tar-archive` capability** — tars a source directory tree into a compressed,
  timestamped, `chmod 600` archive, applying a composed exclude set. It is
  parameterized (`source`, `out` pattern), so **git-src is a config *instance* of
  `tar-archive`**, not a bespoke class. A future non-tar backup (a DB dump, an
  rsync mirror) would be its own capability; a future tar target is just more
  config.

### Exclude composition — two layered mechanisms

**1. Config-layer excludes (global), via 00080 directive-merge.** The gem's
`default.yaml` ships the ~35 patterns from the current script as a plain
`excludes:` list. User-wide and machine-specific config layers add and remove with
the `excludes+` / `excludes-` directives introduced by **PRD 00080** (hard
dependency):

```yaml
# gem default.yaml
excludes: [node_modules, .next, __pycache__, .venv, target, dist, build, .DS_Store, ...]

# ~/.config user-wide — add a personal scratch dir everywhere
excludes+: [scratch-notes]

# machine-local — this box archives Rust target dirs by policy
excludes-: [target]
```

This fully covers "defaults shipped by the gem, overridable user-wide and/or
machine specific" with **no bespoke merge code** — it rides on 00080.

**2. Per-repository `.bkpignore` (local), gitignore-style.** A `.bkpignore` file
inside a repo controls excludes for **that repo's subtree only**:

- a bare `pattern` line **adds** a repo-specific exclude;
- a `!pattern` line **cancels** an inherited global default for that subtree
  (un-ignore), so a repo whose `target/` is real source keeps it.

`.bkpignore` lives on disk next to the code and is discovered during the walk — it
is **outside** the config-load stack entirely, and its `!` un-ignore is
**path-scoped**: `!target` in `~/git/src/foo/.bkpignore` re-includes `target/`
only under `foo/`, never globally.

### Archive production — `tarfile` + owned walk

Because path-scoped `.bkpignore` un-ignore **cannot** be expressed as global
`tar --exclude` flags, the capability owns file selection: it `os.walk`s the
source tree, applies the merged global excludes plus per-directory `.bkpignore`
rules to decide each path, and adds surviving files to a
`tarfile.open(mode="w:gz")`. This makes `.bkpignore` scoping a trivial
per-directory decision, is cross-platform (no `stat` split), deterministic, and
unit-testable without a real `tar` binary. On very large trees in-process gzip is
slower than system `tar`; a documented perf escape hatch (walk in Python, hand the
resulting file list to `tar -czf out -T filelist`) is noted for a future phase and
NOT built in v1.

### CLI surface — minimal parity with sysup

Single Click entry via `buvis_options` (`--version/--config/--log-level/--debug/--update`
automatic), plus:

- **`backup`** (no args) — run all configured capability instances.
- **`--only <name>`** — run one named instance (e.g. `git-src`).
- **`--tag <t>`** — run instances carrying a tag.
- **`--list`** — print configured instances and exit.
- **`--dry-run`** — walk + report what *would* be archived (resolved out-path,
  file count, total bytes, and which excludes / `.bkpignore` rules applied) WITHOUT
  writing an archive. This is the primary verification surface for the layered
  exclude composition.

Source/out come from config, not positional args. Ad-hoc `--source/--out`
overrides and a `--show-excludes` introspection command are deferred to Phase 2.

## Requirements

### Must have

- New gem `src/tools/backup/` following the tool base layout, mapped to top-level
  `backup` in the wheel (hatch package), with a `backup` extra.
- A `tar-archive` capability: given `source` + `out` pattern + a resolved exclude
  set, walk the tree, filter, write a `w:gz` tarball, `chmod 600` it, and return a
  structured result (out-path, file count, byte size).
- git-src ships as a `tar-archive` config instance in `default.yaml`
  (`source: ~/git/src`, timestamped `out`), reproducing the current script's
  behaviour.
- Global excludes ship in `default.yaml` as a plain `excludes:` list and layer via
  00080's `excludes+` / `excludes-` across gem → user-wide → machine config.
- `.bkpignore` per-repo file: bare line adds an exclude; `!pattern` cancels an
  inherited default; both **path-scoped** to the file's own subtree.
- Archive selection owned in Python (`os.walk` + `tarfile`), so path-scoped
  un-ignore works; no reliance on global `tar --exclude` semantics.
- CLI: `--only`, `--tag`, `--list`, `--dry-run` + automatic `buvis_options`; a good
  `--dry-run` reporting resolved out-path, counts, bytes, and applied excludes.
- `CommandResult` / `StepResult` discipline: capability returns a result; the CLI
  renders it via `console` (`report_result` / `success` / `failure` / `panic`).
  No `print`, no `sys.exit` inside command/capability classes.
- Atomic archive write: write to a temp path, `fsync`, `os.replace` to the final
  name (never a partial `.tar.gz` left on crash/ENOSPC).

### Nice to have

- Manifest-registered pytest marker `backup` (scaffold convention).
- `--dry-run` prints a short per-repo summary when a `.bkpignore` altered the set.

### Out of scope (v1)

- Ad-hoc `--source` / `--out` CLI overrides (Phase 2).
- `--show-excludes <instance> --for <path>` resolved-exclude introspection
  (Phase 2).
- The `tar -T filelist` perf path for large trees (documented escape hatch only).
- Any backup capability other than `tar-archive` (DB dumps, rsync mirrors,
  encryption, retention/rotation, remote upload).
- Scheduling — the gem produces an archive on invocation; cron/launchd is the
  user's concern.

## Success Criteria

- `backup --only git-src` produces a `chmod 600` timestamped `git-src-*.tar.gz`
  matching the current script's exclusions, driven entirely by config.
- Adding a global exclude needs only `excludes+: [x]` in a user/machine config
  (no re-listing defaults); removing one needs only `excludes-: [x]`.
- A repo with `!target` in its `.bkpignore` has `target/` archived while every
  other repo's `target/` stays excluded.
- `--dry-run` accurately previews the archive without writing it.
- No bash script in the loop; no `stat` portability split; capabilities/CLI honour
  `CommandResult`/`console` discipline and atomic write.
