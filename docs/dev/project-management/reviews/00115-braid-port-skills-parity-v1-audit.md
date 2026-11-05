# Decision Audit Log: 00115-braid-port-skills-parity-v1

PRD: `00115-braid-port-skills-parity-v1.md`
Started: 2026-11-05T10:49:24Z
Completed: 2026-11-05T10:49:24Z
Autonomous: 9  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-11-05T10:49:24Z

**Decision**: 00115 design approach

**Choice**: domain/model.py+kiro.py+engine.py split (import-cycle break); ComposeRequest resolved inside CommandCompose; Console.out rendering (no wrap); parameter objects instead of lint suppressions; OSError mapped to exit 2

**Rationale**: design-solution reviewed 3/3 dispatches, 0 open blockers; open non-blockers: KeyboardInterrupt loses buffered BACKUP report, Windows test isolation via USERPROFILE, __all__ in braid/__init__.py

### [autonomous] 2026-11-05T10:49:24Z

**Decision**: 00115 task order vs pre-commit tool-wiring hook and test-first port

**Choice**: tests-first order: task 2 (engine tests) -> 1 (engine + scripts/packages wiring) -> 4 (CLI tests) -> 3 (CLI) -> 5 (docs)

**Rationale**: pre-commit check_tool_wiring rejects src/tools/braid/__init__.py without scripts+packages lines, so task 1 carries them; the PRD's ported suites are the spec, so they land first and the implementation tasks use the work skill's earlier-task-tests path (Tess skipped, Devon and red-check kept)

### [autonomous] 2026-11-05T10:49:24Z

**Decision**: 00115 step-7 full suite not fully green

**Choice**: handed off to review with the failure recorded; no braid change made for it

**Rationale**: 6645 passed, 16 skipped, 1 xfailed, 10 errors at b8254fa5; all 10 are setup errors in tests/tools/dot/test_pull_divergence_two_hosts.py (two_host_setup: git commit exits 128; the fixture sets its own identity, so likely sandbox-denied commit signing), the file also errors and hangs when run alone, and the branch changes nothing under src/tools/dot, tests/tools/dot or src/lib; braid suite 85 passed, mypy clean, ruff check src tests tools clean (repo-wide ruff flags a pre-existing E501 in reports/00105-verification-runner.py from b5d1c173)

### [autonomous] 2026-11-05T10:49:24Z

**Decision**: UnicodeDecodeError (a ValueError, not an OSError) from read_text on a non-UTF-8 sources.d file, .braidignore or SKILL.md escapes `except (BraidError, OSError)`. The user sees a traceback and the buffered report lines are dropped. This matches the reference, but AGENTS.md says raw exceptions must never reach the user. `_load_state` already maps UnicodeDecodeError. Fix: widen the catch in CommandCompose.execute to include UnicodeDecodeError, or wrap those reads in BraidError, and add one test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-05T10:49:24Z

**Decision**: The Windows junction fallback passes filesystem paths through cmd.exe. subprocess argument-list quoting does not escape cmd metacharacters: a source directory such as C:\skills&calc& can execute calc when symlink privileges are unavailable. A future change should use junction creation without command-shell parsing. This is outside the parity port’s permitted changes because its contract explicitly requires create_directory_link to remain verbatim.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-05T10:49:24Z

**Decision**: R2 HIGH: cmd.exe metacharacter injection in create_directory_link junction fallback

**Choice**: fix in cycle-1 rework despite the design's verbatim-port rule

**Rationale**: a skill dir name from a third-party source repo (e.g. x&calc&) runs as a command when symlink rights are missing; verbatim parity does not justify shipping a known injection; the same bug lives in agent-skills braid and needs an upstream fix too

### [autonomous] 2026-11-05T10:49:24Z

**Decision**: R1/R5 MEDIUM: UnicodeDecodeError escapes the exit-2 contract

**Choice**: fix via R1 task; R5 discarded as duplicate

**Rationale**: Alice and Bob flagged the same defect at two files; review-close refuses a single-voice row, so R5 rides on R1

### [autonomous] 2026-11-05T10:49:24Z

**Decision**: R3,R4,R6-R11 single-voice medium/low

**Choice**: discard, ledgered

**Rationale**: single-voice; R3/R4 are deviations the design doc chose on purpose (ruff parameter objects, ComposeRequest seam)

### [autonomous] 2026-11-05T10:49:24Z

**Decision**: cycle 2: six single-voice Blake Medium/Low findings (R1-R6)

**Choice**: discarded, ledgered; no tail sweep

**Rationale**: cycle 2 converged: no CRITICAL/HIGH, constraint gate exit 0; all rows [1/4], R1/R2 object to the deliberate cycle-1 security and error-contract fixes
