# backup gem: config-driven tar-archive capability (git-src) v1

<!-- design; migrated from PRD 00082 flat file -->

## Implementation

### Dependency
- **PRD 00080 (pybase config directive-merge) is already implemented and in
  `dev/local/prds/done/`** (verified 2026-09-26: `_deep_merge` /
  `_apply_list_directives` in `loader.py`, 21 tests green). v1 models `excludes`
  as a plain list and relies on the shipped `excludes+` / `excludes-` directives
  for user-wide / machine-local layering — no blocker remains.

### Gem: src/tools/backup/
- **`config.py`** — Pydantic settings: a keyed map of capability instances
  (`instances: {git-src: {use: tar-archive, with: {...}, tags: [...]}}`) plus the
  global `excludes` list; `extra="forbid"`. Own schema, independent of sysup.
- **`runner.py`** — selects applicable instances (`--only` / `--tag`), invokes each
  capability, collects `StepResult`s. Own runner, independent of sysup.
- **`capabilities/tar_archive.py`** — the walk + filter + tarfile + chmod + size
  logic; consumes the resolved global excludes and per-repo `.bkpignore` rules.
- **`shared/bkpignore.py`** — parse a `.bkpignore` file and evaluate add / `!`
  un-ignore against a path, scoped to the file's directory.
- **`cli.py`** — Click entry with `buvis_options`, `--only/--tag/--list/--dry-run`;
  lazy-imports the capability inside handlers; renders `StepResult`s via `console`.
- **`default.yaml`** — the ~35 global excludes as a plain list + the git-src
  `tar-archive` instance.
- **`manifest.toml`, `__init__.py`, `__main__.py`, `settings.py`** — base layout.

### Tests
- **Location**: `tests/tools/backup/` mirroring the gem, class-based, marker
  auto-applied by path.
- Cover: `.bkpignore` add + `!` un-ignore path-scoping (a `!target` under one repo
  re-includes only that repo's `target/`); global-exclude layering via 00080
  (gem + `excludes+` + `excludes-` resolves correctly); walk/filter selects the
  expected file set; `--dry-run` writes nothing and reports accurate counts/bytes;
  atomic write leaves no partial archive on simulated failure; CLI renders results
  through `console` with no stray output.

### Packaging
- Add `backup` to the wheel's tool packages and to the extras list
  (`bim, bim-web, doc, dot, fren, ..., backup, all`).

## Provenance

Requirements elicited in a dashboard session on 2026-09-26, one decision at a time.
The user framed backup as its own gem that (like sysup in architecture only) runs
configured capabilities with arguments, first capability wrapping
`/Users/bob/.local/bin/backup-git`. Four decisions settled: (1) `.bkpignore` uses
gitignore-style `!` un-ignore, path-scoped, to add or cancel per-repo; (2) git-src
is a config instance of a generic `tar-archive` capability, not a bespoke class;
(3) archive selection is owned in Python via `os.walk` + `tarfile` (the only way
path-scoped un-ignore works), with `tar -T filelist` noted as a Phase-2 perf
escape hatch; (4) minimal CLI parity with sysup, `--dry-run` as the primary
exclude-composition verification surface. The user corrected an early conflation:
backup shares NO code/registry/schema with sysup — only the pattern. Depends on
PRD 00080 (directive-merge), already implemented and in `done/`. Grounded against the
`backup-git` script and the sysup capability layout as they stood on that date.
