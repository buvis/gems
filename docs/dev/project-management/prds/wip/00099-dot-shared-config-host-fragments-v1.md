---
default_model: opus
model_tier_rationale: byte-preserving round-trip equivalence and shared Git filter integration across checkout, pull and patch paths
---

# dot shared config with host-value filters

Source: docs/dev/project-management/intake/processed/00099-dot-shared-config-host-fragments/discovery.md

## Overview

### Problem Statement
Tools rewrite absolute home paths in otherwise shared configuration. Tracking raw values causes host-to-host conflicts; plain localize stops sharing the whole file. Preserve shared content while Git stores home placeholders and tools continue reading and writing real files.

### Target Users
Dot operators sharing configuration across POSIX hosts with different home directories, including tools that rewrite absolute paths. Windows spelling normalization is supported within Windows; Windows/POSIX sharing is outside v1.

### Success Metrics
- Named tests below cover discovery R1–R13, including real Git checkout, tool rewrites, two-host pull, divergence recovery and hunk revert.
- Byte-level tests prove both POSIX round trips, safe boundaries, token refusal, CRLF/BOM/non-UTF-8 preservation and Windows spelling normalization.
- Plain localize retains its existing behavior. No new dependency, live dotfile migration, TUI binding or library change.

## Functional Decomposition

### Capability: Portable home values
Convert bytes at Git's index/work-tree boundary without changing file layout.

#### Feature: Byte-safe clean and smudge
- **Description**: Pure Python byte transforms substitute the single reserved token `@HOME@`.
- **Inputs**: File bytes and the host home value, obtained from GIT_WORK_TREE made absolute against cwd, otherwise DOTFILES_ROOT, otherwise Path.home(); strip trailing separators.
- **Outputs**: Cleaned bytes containing tokens; smudged bytes containing this host's home; replacement count for shared opt-in.
- **Behavior**: On both sides of a home match require start/end of input or a byte outside `[A-Za-z0-9_.-]`. Match `/Users/bob/x`, quoted `/Users/bob`, `=/Users/bob` and `file:///Users/bob`; reject `/Users/bobby`, `/Users/bob.bak`, `/Users/bob-old` and `/opt/Users/bob`. Smudge replaces tokens with home bytes. Preserve all bytes outside replacements, including newline, encoding and BOM. For token-free raw POSIX input y, smudge(clean(y)) equals y; for x produced by clean, clean(smudge(x)) equals x. Windows clean accepts native backslashes, doubled JSON backslashes and forward slashes, comparing only the drive letter case-insensitively; smudge uses forward slashes for the home prefix and preserves suffix separators. Windows spelling normalization intentionally has no byte-identical raw round-trip requirement.

#### Feature: Reserved-token plumbing
- **Description**: Hidden `dot filter clean <path>` and `dot filter smudge <path>` expose the pure transforms to Git.
- **Inputs**: Binary stdin, action and Git-supplied path used for diagnostics.
- **Outputs**: Only converted bytes on stdout; clean refusal exits 1 with `dot filter: <path> already contains @HOME@; the token is reserved` on stderr.
- **Behavior**: Clean refuses any raw input containing the token before emitting output. Use binary streams; never console rendering or text decoding on the payload. Mark the sanctioned direct stdout/stderr writes with a comment citing discovery R12; normal dot output continues through console. Filter dispatch never constructs DotGitService or runs Git, preventing recursive filter invocation. Git's configured invocation disables auto-update before CLI startup.

### Capability: Shared-file opt-in
Register one tracked regular file without moving or linking it.

#### Feature: Driver registration
- **Description**: Install the per-host dot-host driver when the clean key is unset.
- **Inputs**: DotGitService construction and bare-repo configuration.
- **Outputs**: `filter.dot-host.clean = BUVIS_AUTO_UPDATE=false dot filter clean %f`, `filter.dot-host.smudge = BUVIS_AUTO_UPDATE=false dot filter smudge %f`, `filter.dot-host.required = true`.
- **Behavior**: Add `_ensure_filter_driver` beside the existing constructor self-heal calls. If clean is set, change none of these keys. Setup constructs the service before checkout, so initial checkout uses smudge. Keep shell quoting for the configured command values. Once configured, a missing dot executable must cause Git to fail loudly.

#### Feature: Shared localize action
- **Description**: `dot localize --shared <path>` invokes a separate CommandShare class behind the same command/service seam.
- **Inputs**: Root-relative or absolute-under-root file path, tracked registry and work-tree bytes.
- **Outputs**: CommandResult with `shared <path>: <n> host value(s) replaced`, or `no host value found in <path>; filter active for future writes` when n is zero, plus `staged .gitattributes` after successful staging.
- **Behavior**: Normalize under the dotfiles root; resolve and confine input-derived reads/writes there and reject links. Before mutation refuse missing/untracked paths (name `dot add`), directories, host-links targets, git-secret files, `.gitattributes` itself, an existing dot-host line for the path, reserved-token bytes and paths requiring attribute quoting (whitespace, `#`, `!`, `[`, backslash); Reject glob-bearing paths as well; directory/glob opt-in is unsupported. Reject `--shared` combined with `--to` before mutation. Keep plain localize's refusal set and behavior. Append the anchored literal line `/<path> filter=dot-host` to root `.gitattributes`, creating it as needed, with the atomic writer and existing append_entry newline convention. Dry clean the original work-tree bytes for n; leave those bytes and location unchanged. Run `cfg add --renormalize -- <path>` through the service's `renormalize` method using a literal pathspec, then stage `.gitattributes`. Renormalize failure restores prior attribute content atomically (or removes only the newly created registry), reports the error and preserves unrelated content. Attribute stage failure keeps the shared registration/index and returns a warning containing `run 'dot add .gitattributes'`. Expected filesystem/Git errors return CommandResult failures; no custom control-flow exceptions.

#### Feature: Git lifecycle compatibility
- **Description**: Existing Git operations consume the driver without a second rendering pipeline.
- **Inputs**: Shared attributes, tokenized index and host-local work-tree values.
- **Outputs**: Clean status after same-host tool rewrites and checkout; another host's paths after pull; applicable divergence patches and reverse hunks.
- **Behavior**: Prove with real Git that A shares, commits and pushes, then B pulls into a different resolved work-tree root: index retains tokens, B's file holds B's home and status is clean. Permit only the documented one-time saved divergence patch. Exercise save_divergence_patch and DotGitService.apply_reverse_to_worktree with actual shared-content edits and home-bearing context. Do not assume Git applies filters correctly merely because a command exits 0; assert final bytes and index content. Keep the existing service implementation unless these scoped tests demonstrate a required compatibility fix.

Scope excludes structural overlays, variables other than HOME, overrides, unshare automation, raw-index drift warnings, herdr plugin tracking, glean changes and migration of the user's live files. Naming and attribute-write placement are resolved here: separate class beside localize, atomic write in that command, Git execution through the service. No human decisions or manual verification remain in implementation.

## Structural Decomposition

### Repository Structure

```text
src/tools/dot/
├── hostfilter.py
├── cli.py
├── git/
│   └── service.py
└── commands/localize/
    └── share.py
tests/tools/dot/
├── test_hostfilter.py
├── test_filter_cli.py
├── test_git_service_filter.py
├── test_share.py
└── test_shared_real_git.py
docs/source/tools/dot.rst
README.md
AGENTS.md
CHANGELOG.md
```

### Module: Home transforms
- **Maps to capability**: Portable home values
- **Location**: src/tools/dot/hostfilter.py, tests/tools/dot/test_hostfilter.py
- **Responsibility**: Pure byte substitution, root selection, boundary checks, token guard and replacement count; stdlib only. Private return shapes are chosen in design from the specified behavior.
- **Exports**: Shared pure transforms used by plumbing and opt-in.
- New symbols: `src/tools/dot/hostfilter.py`, `tests/tools/dot/test_hostfilter.py`.

### Module: Git service
- **Maps to capability**: Shared-file opt-in
- **Location**: src/tools/dot/git/service.py, tests/tools/dot/test_git_service_filter.py
- **Responsibility**: Self-heal driver configuration and expose renormalization through the existing shared service; retain patch behavior unless real-Git coverage proves a defect.
- **Exports**: Existing `DotGitService`; new constructor helper `_ensure_filter_driver`; new `renormalize` method taking a root-relative path and returning `CommandResult` after running cfg add --renormalize with a literal pathspec after the double dash.
- New symbols: `_ensure_filter_driver`, `renormalize`, `tests/tools/dot/test_git_service_filter.py`.

### Module: Share action
- **Maps to capability**: Shared-file opt-in
- **Location**: src/tools/dot/commands/localize/share.py, tests/tools/dot/test_share.py
- **Responsibility**: Validation, dry clean count, atomic registry mutation, renormalize, stage and rollback. Reuse `read_manifest`, `atomic_write_bytes` or `atomic_write_text`, and service methods.
- **Exports**: `CommandShare`, returning `CommandResult` from execute; lazy import by CLI without changing the plain localize package exports.
- New symbols: `CommandShare`, `src/tools/dot/commands/localize/share.py`, `tests/tools/dot/test_share.py`.

### Module: CLI adapters
- **Maps to capability**: Portable home values; Shared-file opt-in
- **Location**: src/tools/dot/cli.py, tests/tools/dot/test_filter_cli.py
- **Responsibility**: Hidden binary filter group and visible shared flag; all share logic stays in the command; normal messages use console.report_result.
- **Exports**: Existing CLI with additive commands/options.
- New symbols: `tests/tools/dot/test_filter_cli.py`.

### Module: Integration and guidance
- **Maps to capability**: Portable home values; Shared-file opt-in
- **Location**: tests/tools/dot/test_shared_real_git.py, docs/source/tools/dot.rst, README.md, AGENTS.md, CHANGELOG.md
- **Responsibility**: Temporary-root real-Git scenarios and complete operator documentation.
- **Exports**: Headless regression scenarios and user guidance.
- New symbols: `tests/tools/dot/test_shared_real_git.py`.

## Dependency Graph

### Foundation Layer (Phase 0)
- **Home transforms**: No new-module dependencies; built first.
- **Git service**: No new-module dependencies; registration and renormalization.

### Core Layer (Phase 1)
- **Share action**: Depends on [Home transforms, Git service].
- **CLI adapters**: Depends on [Home transforms, Share action].

### Integration Layer (Phase 2)
- **Integration and guidance**: Depends on [Home transforms, Git service, Share action, CLI adapters].

## Implementation Phases

### Phase 0: Foundation
**Goal**: Establish pure transforms and Git driver configuration.

**Tasks**:
- [ ] Implement src/tools/dot/hostfilter.py and tests/tools/dot/test_hostfilter.py (no deps). Acceptance: `uv run pytest tests/tools/dot/test_hostfilter.py -q` covers every R3 positive/negative example, both boundaries including token context, repeated matches/counts, POSIX round trips, non-UTF-8/CRLF/BOM, reserved-token refusal, all three Windows spellings, drive-letter case versus remaining case, suffix preservation and GIT_WORK_TREE/DOTFILES_ROOT/home precedence including GIT_WORK_TREE set to dot against cwd.
- [ ] Extend src/tools/dot/git/service.py; add tests/tools/dot/test_git_service_filter.py (no deps). Acceptance: `uv run pytest tests/tools/dot/test_git_service_filter.py tests/tools/dot/test_git_service.py tests/tools/dot/test_git_service_hooks_path.py tests/tools/dot/test_setup.py -q` proves the exact three config values are written only when clean is unset, existing driver keys are preserved, renormalize uses a shell-safe literal pathspec after `--`, and the existing construction, hooks-path and setup tests stay green with the added constructor config calls.

**Exit Criteria**: Foundation task tests pass without touching a real home or invoking maintenance operations.

### Phase 1: Core
**Goal**: Expose validated opt-in and binary filter plumbing.

**Tasks**:
- [ ] Add src/tools/dot/commands/localize/share.py and tests/tools/dot/test_share.py (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/dot/test_share.py -q` verifies every refusal leaves file/registry/index unchanged, absolute-under-root normalization and confinement, count/zero messages, anchored attributes with existing/missing trailing newline, no move/link/manifest change, operation order, exact prior registry restoration on renormalize failure and preserved registration plus recovery warning on stage failure. Test failures of reads and atomic writes; return failures without traceback. All service calls are mocked.
- [ ] Extend src/tools/dot/cli.py and add tests/tools/dot/test_filter_cli.py (depends on: Share action). Acceptance: `uv run pytest tests/tools/dot/test_filter_cli.py tests/tools/dot/test_localize.py -q` covers shared dispatch, rejection of shared with to, unchanged plain dispatch, hidden filter help, byte-exact stdout for both actions, token error exit 1 with only its single stderr line and empty stdout, and absence of Git/console/update invocation from filters under configured BUVIS_AUTO_UPDATE=false. Additive tests leave existing localize tests intact.

**Exit Criteria**: Command and plumbing tests pass; expected errors remain controlled and payload bytes never pass through console.

### Phase 2: Integration
**Goal**: Prove actual Git behavior and document operation/recovery.

**Tasks**:
- [ ] Add tests/tools/dot/test_shared_real_git.py (depends on: Phase 1). Acceptance: `uv run pytest tests/tools/dot/test_shared_real_git.py -q` proves index tokens, same-host rewrites clean, checkout smudge, setup self-heal before checkout, two-host push/pull and clean B status, anchored attributes excluding same-named nested files, shell-safe path handling, missing-dot required-filter failure, divergence-patch application and reverse-hunk restoration with correct host paths. Use temporary bare repos/origin, resolved roots, isolated Git config and PATH prefixed with the active interpreter bin; never access the user's bare repo. If R11 exposes a filter compatibility defect, fix only src/tools/dot/git/service.py and rerun this file plus tests/tools/dot/test_git_service.py and tests/tools/dot/test_pull_divergence.py.
- [ ] Update docs/source/tools/dot.rst, README.md, AGENTS.md and CHANGELOG.md (depends on: real-Git integration). Document `--shared` versus plain localize, all refusals, unchanged work-tree layout, tracked attributes, per-host self-heal, token reservation/diffs, count/zero messages, Windows forward-slash normalization, unchanged suffixes, no Windows/POSIX promise, missing-dot failure, run `dot status` once after upgrade, expected one-time divergence and unshare by removing the attribute line then renormalizing. Explain undefined-driver risk and recovery: save edits first, run dot to install the driver, remove only the affected file, then `dot run checkout -- <path>`; never imply recovery preserves unsaved edits automatically. Add one sentence to the Console methods list in AGENTS.md naming the dot filter binary plumbing (payload bytes on stdout, one error line on stderr) as the sanctioned exception to the console-only rule, citing discovery R12. Add an Added **dot** changelog entry. Acceptance: `uv run sphinx-build -b html docs/source docs/build/html`, `rg -c "dot filter" AGENTS.md` printing 1, and `python3 -c 'from pathlib import Path; d=Path("docs/source/tools/dot.rst").read_text(); r=Path("README.md").read_text(); c=Path("CHANGELOG.md").read_text().split("## [", 2)[1]; assert all(s in d for s in ("--shared", "@HOME@", ".gitattributes", "BUVIS_AUTO_UPDATE=false", "renormalize", "dot status", "checkout", "Windows")); assert "--shared" in r and "@HOME@" in r; assert "### Added" in c and "**dot**:" in c'` pass.

**Exit Criteria**: `uv run pytest -m dot -q`, `uv run mypy src/tools/dot` and `uv run ruff check src/tools/dot tests/tools/dot` pass; run the full project suite `uv run pytest` once after all tasks.

## Test Strategy

### Critical Scenarios
- **Happy path**: Share a tracked file, then a tool rewrites this host's paths → index tokens and clean status, with unchanged work-tree bytes.
- **Edge case**: Host A's new attributes arrive with its shared file on B → B gets local home values in the same checkout; tokens remain in the index.
- **Edge case**: Windows spellings converge to one token representation; smudge writes forward-slash home while leaving suffix separators alone.
- **Edge case**: Git starts the driver with GIT_WORK_TREE equal to dot → home resolves against filter cwd without recursively creating the service.
- **Error case**: Token already in raw input → exact stderr line, exit 1 and no partial stdout or index mutation.
- **Error case**: Renormalize fails → prior attribute bytes restored; stage fails afterward → registration retained with actionable warning.
- **Regression**: Shared-content edits survive divergence recovery and TUI reverse-hunk operations, including home-bearing context; assert bytes as well as return codes.

## Risks

- **Undefined driver before first dot command**: Git treats it as a no-op; document upgrade initialization and saved-edit recovery. Test configured-but-unavailable driver failures separately.
- **Reserved token**: Intentional literal content cannot use this filter; refuse before output or opt-in mutation.
- **Filter recursion/output contamination**: Pure plumbing never creates the service; configured environment disables auto-update, and binary subprocess tests pin stdout.
- **Git apply semantics**: R11 is a real-Git gate, not an assumed property; any necessary fix remains within the shared service and named tests.
- **Filter startup cost**: Accept per-file CLI startup for a few files; defer persistent process protocol or thin entry point until measured need.
- **External dotfiles**: Implementation tests use temporary repositories; operator opt-in on live hosts remains a post-release action outside this PRD.
