# klyreon C: operator asset install, refresh, and manifest

<!-- tasks; migrated from PRD 00076 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: The record and the payload.

**Tasks**:
- [ ] `assets/manifest.py`: typed manifest with `schema_version`, atomic write, loud rejection of an unknown version, `kind` field reserved for PRD D (no deps) - Acceptance: round-trip test; a manifest with `schema_version: 99` fails with a clear message; a missing manifest loads as empty.
- [ ] `assets/registry.py` plus the claude payload directory (no deps) - Acceptance: `resolve_target("claude")` honours `$CLAUDE_CONFIG_DIR` and falls back to `~/.claude`; an unknown operator lists the known ones; `payload_files` finds the packaged `SKILL.md` through `importlib.resources` from an installed wheel, not just from the source tree.
- [ ] Write the claude `SKILL.md` content: trigger-led frontmatter under 250 characters, the two species, closed vocabularies, claim and doubt rules, three conflict shapes, klyreon command surface (no deps) - Acceptance: the file states that klyreon's autonomous loop does not read it; a test asserts the frontmatter shape and that the referenced spec path exists.

**Exit Criteria**: The manifest round-trips and the payload resolves from a built wheel.

### Phase 1: Core
**Goal**: Install, refresh, and remove, without destroying user work.

**Tasks**:
- [ ] `assets/installer.py`: install with hash compare, backup-then-overwrite, and the report (depends on: Phase 0) - Acceptance: fresh install writes and records every file; a second install reports all current and changes no mtime; an edited file is backed up with a timestamped name and the displaced path appears in the report; a pre-existing untracked file at a target path is backed up too.
- [ ] `assets/installer.py`: refresh, status, and uninstall (depends on: Phase 0) - Acceptance: refresh re-installs exactly the operators in the manifest; status flags a file whose hash drifted and one whose recorded version is behind the CLI; uninstall removes matching files, keeps edited ones with a reason, drops the entries, and removes only directories it emptied.

**Exit Criteria**: Every installer branch is covered against a temp HOME.

### Phase 2: Integration
**Goal**: The commands and the setup path.

**Tasks**:
- [ ] `klyreon assets install|status|refresh|uninstall` wired through the CLI with `console.report_result` (depends on: Phase 1) - Acceptance: each subcommand exits 0 on the happy path and renders its report; an unknown `--operator` exits 1 naming the valid values.
- [ ] Extend `klyreon init` with the operator offer, `--operator`, and `--no-input`; extend `klyreon status` with the behind-the-CLI warning (depends on: Phase 1) - Acceptance: init with `--operator claude` installs without prompting; init with stdin not a TTY skips the offer and prints the follow-up command; status warns exactly once when a recorded version is behind.
- [ ] Docs section, CHANGELOG Added entry, mypy strict, ruff, coverage (depends on: Phase 1) - Acceptance: all gems gates green in CI.

**Exit Criteria**: Every Success Metric holds against a temp HOME, from a built wheel.
