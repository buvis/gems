# backup gem: Phase-2 CLI + perf enhancements v1

<!-- requirements; migrated from PRD 00083 flat file -->

## Problem

The `backup` gem shipped in v1 (PRD 00082, merged) with a deliberately minimal
surface: config-driven instances, `--only/--tag/--list/--dry-run`, and a
`tarfile`-owned walk. Three enhancements were explicitly deferred from v1 as
fast-follow, each independently useful but none required for the core capability:

1. **No ad-hoc override.** Source/out come only from config; there is no way to
   back up an arbitrary tree once without editing a config file — the original
   `backup-git` script took `$1`/`$2` positional args for exactly this.
2. **Layered excludes are not directly inspectable.** `--dry-run` shows the
   *effect* (what would be archived), but not the *resolved exclude set* — the
   gem default `excludes` plus every `excludes+`/`excludes-` layer plus the
   `.bkpignore` rules that would apply under a given path. When a file is
   unexpectedly included or excluded, there is no single command that explains
   why.
3. **In-process gzip is slow on very large trees.** v1 streams through Python's
   `tarfile` (chosen so path-scoped `.bkpignore` un-ignore works). On a large
   `~/git/src` this is meaningfully slower than system `tar`; a documented
   escape hatch exists in the 00082 PRD but is not implemented.

## Solution

Three additive changes to the existing gem, no breaking changes to the v1
surface. Each is independently shippable; grouped here because they share the
gem and CLI and would land together.

### 1. Ad-hoc `--source` / `--out` overrides

Optional CLI flags that override the *selected* instance's `source` / `out` for a
one-shot run. Precedence: explicit flag > config value. Requires exactly one
selected instance (via `--only`), so the override is unambiguous; overriding
with multiple instances selected is a usage error routed through `console`.

### 2. `--show-excludes <instance> --for <path>` introspection

Prints the fully resolved exclude set for an instance: the gem-default
`excludes`, the result after every `excludes+` / `excludes-` config layer, and —
because `.bkpignore` is path-dependent — the `.bkpignore` add / `!` un-ignore
rules that would apply under the given `--for <path>`. Read-only, writes no
archive. `--for` is required (a resolved exclude set is meaningless without a
path, since `.bkpignore` scoping depends on it).

### 3. `tar -T filelist` perf path (opt-in)

A config flag on the `tar-archive` capability (e.g. `engine: system-tar`,
default `python-tarfile`) that, when set, still walks + filters in Python to
produce the exact include list, then hands it to system `tar -czf out -T
filelist` for speed on large trees. Selection logic (and thus `.bkpignore`
path-scoping) stays in Python; only the archiving step shells out. Must handle
the BSD (macOS) vs GNU `tar` `-T` semantics difference — verify `-T` file-list
behavior on both, and fall back to the Python engine with a `console.warning` if
the platform's `tar` is unavailable or incompatible.

## Requirements

### Must have

- `--source PATH` / `--out PATH` override the single selected instance; explicit
  flag wins over config; >1 selected instance with an override is a `console`
  usage error, not a silent pick.
- `--show-excludes <instance> --for <path>` prints the resolved global exclude set
  (post-`excludes+`/`excludes-`) and the `.bkpignore` rules effective under
  `<path>`; writes nothing; `--for` required.
- `engine: system-tar` opt-in on `tar-archive`: Python owns selection, `tar -T`
  archives; default stays `python-tarfile`; incompatible/missing `tar` falls back
  to Python with a warning.
- No change to the v1 default behavior: with no new flags and no `engine` set, the
  gem behaves exactly as it does post-00082.

### Nice to have

- `--show-excludes` without `--for` prints the global set only, with a note that
  `.bkpignore` rules are omitted (path-dependent).
- A short per-repo summary in `--show-excludes` output when a `.bkpignore` alters
  the set.

### Out of scope

- Retention / rotation of old archives.
- Remote upload, encryption.
- New capabilities beyond `tar-archive`.

## Success Criteria

- A one-shot `backup --only git-src --source /some/dir --out /tmp/x.tgz` archives
  the ad-hoc tree without config edits.
- `backup --show-excludes git-src --for ~/git/src/somerepo` explains exactly which
  patterns are active and why (config layers + `.bkpignore`).
- `engine: system-tar` measurably speeds up a large-tree backup while producing the
  same contents as the default engine; the default engine and v1 behavior are
  untouched.
