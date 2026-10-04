# bim doc migrate-layout: ship the promised legacy-zettel migration

<!-- requirements; migrated from PRD 00056 flat file -->

## Problem

`bim doc audit` reports `legacy_layout_zettels` — zettels still at the pre-v1 flat path instead of the per-issuer subfolder — and both the README and docs call it "the input contract for the forthcoming migration command" (`README.md:121-123`, `docs/source/tools/bim.rst`). That command was never shipped. So every audit run permanently reports the same legacy list as `non_clean`: the flagship report can never reach a clean baseline, and a user who hand-moves the files breaks the `file-path` frontmatter link or the per-issuer pairing. This is an unshipped promise and the #2 user-facing win.

## Solution

Ship `bim doc migrate-layout`: consume the latest audit's `legacy_layout_zettels`, and for each, move the zettel into its per-issuer subfolder and rewrite the frontmatter to the v1 shape — atomically (via the 00041 shared helper), dry-run by default, skipping and reporting any file whose frontmatter is too divergent to migrate safely.

## Requirements

### Must have
- `bim doc migrate-layout` reads the legacy list (from a fresh audit or the latest audit JSON) and migrates each zettel: move to `<vault>/<doc-subdir>/<issuer-slug>/<basename>.md` and rewrite frontmatter to the v1 shape using the existing writers/validators in `commands/doc/shared/`.
- **Dry-run by default**: prints the planned moves/rewrites; `--apply` (or `--no-dry-run`) performs them.
- Each file's move+rewrite is atomic (00041 `atomic_write_text`); on any per-file uncertainty (unparseable/too-divergent frontmatter), **skip and report**, never partially migrate.
- After a successful apply, a re-run of `bim doc audit` shows those zettels no longer in `legacy_layout_zettels`.
- Tests: dry-run lists correctly and changes nothing; apply migrates a fixture; a divergent-frontmatter fixture is skipped-and-reported; the frontmatter link stays valid post-migration.
- Command returns `CommandResult`; CLI layer renders it (no `sys.exit`/`console.panic` in the command class).

### Nice to have
- Register the command as a serve action too, honoring the all-interface seam (`dev/local/specs/all-interface-architecture.md`) — optional here, can follow.

## Success Criteria

- `bim doc audit` can reach a clean baseline after migration.
- No partial/atomic-unsafe rewrite; bim doc tests green; docs updated.
