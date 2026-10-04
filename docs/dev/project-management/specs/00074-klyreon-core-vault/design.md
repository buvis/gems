# klyreon A: gem scaffold, spec engine, vault contract, git layer

<!-- design; migrated from PRD 00074 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/klyreon/
├── __init__.py
├── __main__.py
├── manifest.toml            # interfaces: cli
├── cli.py                   # Maps to: every command (Click group, staleness warning)
├── settings.py              # Maps to: Klyreon settings
├── spec/
│   ├── __init__.py
│   ├── model.py             # Maps to: Document model and round-trip
│   ├── enums.py             # Maps to: closed vocabularies (spec 6, 7, 8)
│   ├── parser.py            # Maps to: Document model (YAML loader, H1 split)
│   ├── writer.py            # Maps to: Document model (serialize + atomic_write)
│   └── validator.py         # Maps to: File-level + vault-level validation
├── vault/
│   ├── __init__.py
│   ├── config.py            # Maps to: Root discovery
│   ├── paths.py             # Maps to: Root discovery (resolve/confine)
│   ├── ids.py               # Maps to: new command (collision rule)
│   ├── git.py               # Maps to: Git layer and autonomy gate
│   └── state.py             # Maps to: staleness ($XDG_STATE_HOME state.json)
└── commands/
    ├── __init__.py
    ├── init.py              # Maps to: init command
    ├── validate.py          # Maps to: validate command
    ├── new.py               # Maps to: new command
    ├── export_claims.py     # Maps to: export-claims command
    └── status.py            # Maps to: status command
tests/tools/klyreon/         # mirrors the above, plus fixtures/valid + fixtures/invalid
docs/source/tools/klyreon.rst
docs/reference/klyreon/zettel-format-specification.md   # gains section 3.3
```

### Module: klyreon.spec
- **Maps to capability**: Spec engine
- **Responsibility**: The only code that knows the file format. Pure: no console, no Click, no git.
- **Exports**:
  - `parse_file(path, kind)` / `serialize(doc)` - lossless read and write, unknown fields preserved
  - `SourceDocument` / `Zettel` / `AuxFile` - typed documents
  - `validate_file(doc, path)` / `validate_vault(root)` - lists of `SpecError(path, rule, message)`

### Module: klyreon.vault
- **Maps to capability**: Vault contract + Git layer and autonomy gate
- **Responsibility**: Where the vault is, how paths resolve, how klyreon commits, whether autonomy is allowed.
- **Exports**:
  - `resolve_root()` / `resolve_path(root, rel)` - root discovery and confinement
  - `allocate_id(notes_dir, now)` - collision-bumped 14-digit ID
  - `commit(root, paths, subject)` / `is_git_vault(root)` / `require_git_for_autonomy(root)` / `is_human_authored(root, path)`
  - `read_state()` / `write_state()` - `$XDG_STATE_HOME/klyreon/state.json`

### Module: klyreon.commands
- **Maps to capability**: Vault contract, Authoring and export, Vault status
- **Responsibility**: One command class per CLI command, each returning `CommandResult`. No `console.panic`, no `sys.exit`.
- **Exports**:
  - `CommandInit`, `CommandValidate`, `CommandNew`, `CommandExportClaims`, `CommandStatus`

## Dependency Graph

### Foundation Layer (Phase 0)
External: 00041 (`pybase.filesystem.atomic_write`) must be in `done/`.

- **klyreon scaffold + settings**: no internal dependencies, built first.
- **klyreon.spec.enums + klyreon.spec.model**: no internal dependencies, built first.

### Core Layer (Phase 1)
- **klyreon.spec.parser / writer**: depends on [spec.model, spec.enums]
- **klyreon.spec.validator**: depends on [spec.parser, spec.model]
- **klyreon.vault.config / paths / ids / git / state**: depends on [settings]

### Integration Layer (Phase 2)
- **klyreon.commands.init / new**: depends on [vault, spec.writer]
- **klyreon.commands.validate / status / export_claims**: depends on [spec.validator, vault]
- **klyreon.cli**: depends on [commands, vault.state]

## Test Strategy

### Critical Scenarios
- **Happy path**: `init` an empty dir, `new` three zettels, `validate` → Expected: exit 0, clean report, `status` counts three.
- **Edge case**: ten zettels created inside one second → Expected: ten unique consecutive IDs, each agreeing with its own `created`.
- **Edge case**: a file carrying unknown frontmatter keys is parsed and rewritten → Expected: the unknown keys survive in their original order.
- **Edge case**: the vault has a human's uncommitted edit while klyreon commits two other files → Expected: the human's edit is still modified and unstaged afterwards.
- **Error case**: root config points at a directory that does not exist → Expected: loud failure naming the config path and the missing root; nothing created.
- **Error case**: a zettel's `links.to` points outside the root via `..` → Expected: `validate` exits 1 with the confinement rule id.

## Risks

- **Reimplementing what `pybase.zettel` already does**: deliberate. The bim zettel model is a different contract (different ID rules, different frontmatter, different layout); coupling klyreon to it would drag bim's schema into klyreon's validator and vice versa. klyreon reuses console, `CommandResult`, settings, `atomic_write`, and the updater, and owns its format engine. Revisit only if the two formats converge.
- **YAML round-trip surprises**: the sexagesimal and string-`id` traps are known and tested from day one; comment preservation is explicitly not promised (the spec does not require it), which keeps PyYAML sufficient and adds no dependency.
- **00041 not landed when this PRD starts**: hard blocker. The atomic-persistence invariant forbids bare writes; do not inline a private copy.
- **Spec section 3.3 conflicts with what PRD B and PRD D want to write into trails**: 3.3 fixes only the frontmatter contract (`id`, `title`, `created`, `kind`) and leaves the body free, so the trail journal's sections can grow without another spec edit.
