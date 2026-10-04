# backup gem: config-driven tar-archive capability (git-src) v1

<!-- tasks; migrated from PRD 00082 flat file -->

## Tasks

### Phase 0: Gem scaffold + config
- [ ] Scaffold `src/tools/backup/` (base layout, manifest marker, wheel + extra) —
      Acceptance: `uv run backup --help` shows `buvis_options` + `--only/--tag/--list/--dry-run`.
- [ ] `config.py` settings (instances map + global `excludes` list, `extra="forbid"`)
      and `default.yaml` (35 excludes + git-src instance) — Acceptance: loads and
      validates; `--list` prints `git-src`.

### Phase 1: tar-archive capability + .bkpignore
- [ ] `shared/bkpignore.py` parse + path-scoped add / `!` un-ignore — Acceptance:
      `!target` in a repo re-includes only that repo's `target/`; a bare line adds
      only under that subtree.
- [ ] `capabilities/tar_archive.py` walk + filter + `w:gz` tarball + `chmod 600` +
      atomic `os.replace` + size — Acceptance: git-src instance reproduces the
      current script's archive contents (same excludes) on a fixture tree.
- [ ] `--dry-run` reports resolved out-path, file count, total bytes, applied
      excludes; writes nothing — Acceptance: no archive appears; counts match a
      real run's contents.

### Phase 2: fast-follow (not v1)
- [ ] Ad-hoc `--source` / `--out` overrides with documented precedence over config.
- [ ] `--show-excludes <instance> --for <path>` resolved-exclude introspection.
- [ ] Document the `tar -T filelist` perf escape hatch and gate it behind a config
      flag for large trees.
