# Decision Audit Log: 00088-dot-host-links-materialize-v1

PRD: `00088-dot-host-links-materialize-v1.md`
Started: 2026-10-12T19:13:23Z
Completed: 2026-10-12T19:13:23Z
Autonomous: 9  |  Deferred: 1  |  Doubts: 0

### [autonomous] 2026-10-12T19:13:23Z

**Decision**: design approach for 00088

**Choice**: pure hostlinks package + CommandMaterialize/CommandLinkStatus; optional git_service kwarg lets TUI reuse its DotGitService; reconcile_links abspaths root; absolute check adds PureWindowsPath.root

**Rationale**: design-solution reviewed 3 dispatches, 2 codex blockers fixed, 9 non-blockers and 2 questions recorded in Review log

### [autonomous] 2026-10-12T19:13:23Z

**Decision**: review cycle 1 decision gate: 15 findings, 0 critical/high

**Choice**: converged; discarded R1 (out-of-scope uncommitted postup build churn), R2/R8/R9/R10/R12 (match reviewed design contract), R7 (test placement only); deferred R11; tail-swept R3 R4 R5 R6 R13 R14 R15

**Rationale**: cycle 1: no unresolved critical/high and the doubt-roster constraint gate exited 0; settled items recorded in the ledger

### [autonomous] 2026-10-12T19:13:23Z

**Decision**: `README.md` has only a one-line mention of `host-links` (line 95). The spec says both docs describe the manifest format, `dot materialize`, the hooks and the Windows Developer Mode note. `docs/source/tools/dot.rst` covers all four. The literal `rg host-links` check passes.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T19:13:23Z

**Decision**: `_read_link` strips `\\?\` with a plain `removeprefix`. A junction target of `\\?\UNC\server\share` becomes the relative-looking `UNC\server\share`, so the link would be reported as "links to elsewhere". Design review item d3 flagged this and it was never addressed. Map `\\?\UNC\` to `\\` first.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T19:13:23Z

**Decision**: If writing a later hook raises `OSError`, `install_hooks` loses the "installed hook <name>" lines for hooks already written, because the exception propagates and the caller only adds `hooks: <exc>`. Design review item d3 flagged this and it is not addressed. Either collect lines before re-raising, or accept and document it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T19:13:23Z

**Decision**: The docs say existing hook files are never changed. They do not warn that a pre-existing non-dot `post-checkout`, `post-merge` or `post-rewrite` hook silently stops relinking, and dot never reports it. This was design question d1. Add one sentence to the Host-specific config section.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T19:13:23Z

**Decision**: Documentation tells users to keep host files "in the repo," recreating the cross-host sharing this feature prevents. State that the manifest is tracked and host-local sources remain untracked. (format warning)

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T19:13:23Z

**Decision**: Directory-link tests require `is_symlink()`, but Windows deliberately creates junctions, which fail that assertion. Assert directory accessibility and resolved destination across platforms; check symlink type only on POSIX. (format warning)

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-12T19:13:23Z

**Decision**: The TUI test checks only the first mocked display call, so it cannot establish that the materialize message survives `refresh_status()`. Run a TUI test with a nonempty file list and an unmocked DiffView; press L, await refresh, and assert the final displayed message contains `linked <target>`. (format warning; VERIFY bucket, not queued: names no single runnable command)

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [deferred] 2026-10-12T19:13:23Z

**Decision**: install_hooks checks the hook is missing then atomic_write_text does os.replace; a hook created in between would be silently replaced (tiny window)

**Choice**: deferred to batch end

**Rationale**: cycle 1: microsecond race on the user own hooks dir; exclusive-create would drop the atomic_write invariant
