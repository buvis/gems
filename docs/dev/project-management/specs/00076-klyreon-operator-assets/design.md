# klyreon C: operator asset install, refresh, and manifest

<!-- design; migrated from PRD 00076 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/klyreon/
├── assets/
│   ├── __init__.py
│   ├── manifest.py          # Maps to: Manifest store
│   ├── registry.py          # Maps to: Operator registry
│   ├── installer.py         # Maps to: assets install / refresh / uninstall
│   └── payload/
│       └── claude/
│           └── skills/klyreon/SKILL.md   # Maps to: Claude asset pack
└── commands/
    ├── assets.py            # Maps to: assets install/status/refresh/uninstall
    └── init.py              # extended: init offers asset installation
tests/tools/klyreon/assets/  # temp-HOME fixtures
docs/source/tools/klyreon.rst  # gains the assets section
```

### Module: klyreon.assets.manifest
- **Maps to capability**: Installed-artifact manifest
- **Responsibility**: Read and write the record of installed artifacts. Knows nothing about operators.
- **Exports**:
  - `Manifest` / `ManifestEntry` - typed, `schema_version`ed
  - `load_manifest()` / `save_manifest(m)` - atomic, loud on unknown version
  - `entries_for(kind, operator)` - filtered lookup, reused by PRD D for `kind: schedule`

### Module: klyreon.assets.registry
- **Maps to capability**: Operator asset packs
- **Responsibility**: The operator table and the package-data lookup.
- **Exports**:
  - `KNOWN_OPERATORS` - names, install roots, file lists
  - `resolve_target(operator)` / `payload_files(operator)`

### Module: klyreon.assets.installer
- **Maps to capability**: Install, refresh, uninstall
- **Responsibility**: The hash-compare, backup, write, remove logic. Pure filesystem, no console.
- **Exports**:
  - `install(operators) -> InstallReport` (written / current / displaced)
  - `refresh() -> InstallReport`
  - `status() -> list[AssetStatus]`
  - `uninstall(operators) -> UninstallReport` (removed / kept)

### Module: klyreon.commands.assets
- **Maps to capability**: Install, refresh, uninstall + Setup integration
- **Responsibility**: One command class per subcommand, returning `CommandResult`.
- **Exports**:
  - `CommandAssetsInstall`, `CommandAssetsStatus`, `CommandAssetsRefresh`, `CommandAssetsUninstall`

## Dependency Graph

### Foundation Layer (Phase 0)
External: 00074 must be in `done/` (settings, console wiring, `CommandResult`, XDG state directory, `atomic_write` through PRD A).

- **klyreon.assets.manifest**: no internal dependencies.
- **klyreon.assets.registry + the claude payload**: no internal dependencies.

### Core Layer (Phase 1)
- **klyreon.assets.installer**: depends on [assets.manifest, assets.registry]

### Integration Layer (Phase 2)
- **klyreon.commands.assets + cli**: depends on [assets.installer]
- **klyreon.commands.init** (extended): depends on [assets.installer]
- **klyreon.commands.status** (extended, PRD A): depends on [assets.installer.status]

## Test Strategy

### Critical Scenarios
- **Happy path**: install into an empty temp HOME → Expected: files written, manifest lists each with a hash and the running version, report names every file.
- **Idempotence**: install twice → Expected: second run reports all current, no file rewritten, no backup created.
- **Edge case**: the user edits `SKILL.md`, then a newer klyreon installs → Expected: a timestamped backup beside the file, the shipped version in place, the displaced path in the report, the manifest hash updated.
- **Edge case**: a file exists at a target path but is absent from the manifest → Expected: treated as the user's, backed up before the write.
- **Error case**: unknown operator name → Expected: exit 1 listing known operators; nothing written, manifest untouched.
- **Error case**: manifest with an unrecognised `schema_version` → Expected: loud failure, no install attempted, no file touched.

## Risks

- **Backup files accumulate in the operator's directory**: accepted in discovery Q18 as the price of never destroying an edit. `assets status` names every backup it created so the owner can clear them.
- **Operator install paths change upstream**: the registry is one table; a path change is one row. `$CLAUDE_CONFIG_DIR` is honoured so a non-default layout already works.
- **The pack drifts from the format spec**: the `SKILL.md` points at the spec as normative rather than restating it in full, and a test asserts the referenced path exists. A spec change that invalidates the pack still needs a human to notice.
- **Command-surface growth**: discovery listed seven commands; `assets` makes eight, the same way Q17 added `schedule`. It follows directly from the re-runnable-install requirement.
