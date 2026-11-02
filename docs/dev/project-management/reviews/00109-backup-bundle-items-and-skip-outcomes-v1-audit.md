# Decision Audit Log: 00109-backup-bundle-items-and-skip-outcomes-v1

PRD: `00109-backup-bundle-items-and-skip-outcomes-v1.md`
Started: 2026-11-02T09:56:25Z
Completed: 2026-11-02T09:56:25Z
Autonomous: 9  |  Deferred: 2  |  Doubts: 0

### [autonomous] 2026-11-02T09:56:25Z

**Decision**: Attended recovery of held 00109: completion review never ran

**Choice**: Restored preserved build-state snapshot (work base 5a3ab34d, task provenance unchanged), moved PRD hold->wip, phase-done tasks_done; cycle-1 review ran on a worktree pinned at build end 7f4b462f

**Rationale**: Handoff 202610292344-review-20261102 authorizes recovery; suite blocker was environment-only and resolved by unchanged 00111 isolation runner

### [autonomous] 2026-11-02T09:56:25Z

**Decision**: An inaccessible item can become a successful skip: `os.path.lexists()` returns false for permission errors, so an unreadable parent directory is reported as missing. Existing tests inject errors only after presence succeeds. Distinguish absence from access errors and add an inaccessible-parent test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T09:56:25Z

**Decision**: Permission-denied `source` is a silent successful skip ("source not found") on Python 3.14 (`Path.is_dir()`/`exists()` return False under EACCES, probed) but a failed step on 3.11-3.13 (PermissionError propagates to the Runner); CI runs all four, and an unreadable source exits 0 on 3.14. The `plan` preview uses the same is_dir/exists check and must match.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T09:56:25Z

**Decision**: `items` given as a non-list (a bare YAML string `items: .gitconfig`, or `items:` null) goes through `_as_str_tuple`, becomes `()`, and fails with the misleading "items must not be empty". `bundle = "items" in kwargs` also treats an explicit null as an empty bundle rather than "omitted". Consider a specific "items must be a list of strings" message

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T09:56:25Z

**Decision**: `_normalize_items` rejects any item whose first component merely starts with `..`, so a valid literal filename such as `..hidden` or `..foo/bar` fails with "must be a relative path inside the source". The check should be `relative.parts[0] == ".."`

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T09:56:25Z

**Decision**: On the skip path for "all items absent or excluded", the message "no selected items to archive" names neither source, out, nor label, so the warning cannot be attributed in a multi-instance run

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T09:56:25Z

**Decision**: `docs/source/tools/backup.rst` was not updated for the rework. Line 144 still says "paths beginning with `..` are errors", but `..hidden` is now valid and only a leading `..` component is rejected. The docs also don't say that non-list `items` fails, that `items: null` means omitted, or that an unreadable source or item fails rather than skips.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T09:56:25Z

**Decision**: Plan-side rework behavior is untested: `_plan_items` returning `fail` on an `OSError` from an inaccessible item, `plan` with non-list `items` (`items must be a list of relative paths`), `plan` with `items=None` giving `run`, and `plan` accepting a `..name` item. The positive `..notes` case was dropped from the plan parametrization without a replacement.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T09:56:25Z

**Decision**: Simplification: `_item_present` calls `os.path.lexists` and then `os.lstat` again to separate absence from access errors. A single `try: os.lstat(path)` with `except (FileNotFoundError, NotADirectoryError): return False` and `return True` behaves the same. Note: test_file_vanishing_after_presence_check_fails_instead_of_skipping in tests/tools/backup/test_bundle_items.py monkeypatches `os.path.lexists` and must move to `os.lstat`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [deferred] 2026-11-02T09:56:25Z

**Decision**: A bundle whose `out` lies under `source` but under no selected item is rejected by the unconditional containment check, blocking the PRD's headline case (`source: ~`, items `.gitconfig`/`.npmrc`, `out` under the default `~/.local/backup`)

**Choice**: deferred

**Rationale**: deferred by review-close

### [deferred] 2026-11-02T09:56:25Z

**Decision**: PRD says `WalkResult` gains `missing`. The implementation instead returns `tuple[WalkResult, list[str]]` from `_select_items` and threads `missing` as a separate local in `run`. Either add `missing` to `WalkResult` per the PRD or record the deviation

**Choice**: deferred

**Rationale**: deferred by review-close
