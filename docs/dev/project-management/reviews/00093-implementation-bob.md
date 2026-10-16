# PRD 00093 implementation review — Bob

Verdict: **PASS. No actionable in-scope findings.**

Fresh independent doubt/de-slop review, 2026-10-16. Reviewed root AGENTS.md,
the PRD, implementation diff, related shell/CLI code, tests, documentation and
task-log evidence. No other implementation review was read. All commands ran
inside the feature worktree; no production or test files were changed. No nested
AGENTS.md files were found under src, tests or docs.

## Concrete doubts and resolutions

1. **The new mocks could still conceal the real untracked-file bug. Refuted.**
   The regression now supplies porcelain `??`, asserts captured whole-file add,
   and forbids interactive staging. Independently ran the eight real-Git tests
   with default capture: **8 passed in 1.30s, zero skipped**. These exercise the
   bare repository with `status.showUntrackedFiles=no`, nested cwd, ignore rule,
   bracketed filename beside a modified tracked neighbor, directory intent-to-add,
   existing staged changes, clean tracked file, symlink mode and outside path.

2. **Quoting could protect the shell but still allow Git glob expansion. Refuted.**
   `_literal` combines `shlex.quote` with Git literal magic; the affected status,
   add, directory and diff commands include `--`. `check-ignore` uses the plain
   quoted path as specified. The shell adapter preserves quoted argument text
   during alias expansion. The embedded-quote unit assertion and bracketed-name
   integration check cover the two distinct boundaries.

3. **Resolution could lose symlinks or silently stage the whole tree on a typo.
   Refuted.** `lexists` accepts dangling links, `abspath` preserves the link name,
   and the directory branch explicitly excludes symlinks. Missing-path execute
   returns failure before `stage_interactive`. Existing constructor Git-config
   checks remain, as required by the prescribed initializer; this is not a claim
   that constructing CommandAdd makes no Git calls whatsoever.

4. **Reported success could mean new hunks were staged when none were accepted.
   Refuted within the accepted contract.** `_staged_report` reads the current
   index and labels it “Currently staged”; empty tracked results warn and empty
   untracked results fail. CommandAdd returns the same result to the existing
   console renderer. Directory intent-to-add error handling, the existing
   interactive adapter's exit behavior, and the documented two-status-line edge
   are not redesigned by this review.

5. **Tests or lint configuration could hide unrelated changes. Refuted for this
   patch.** An independent AST comparison proved every module node outside
   `TestDotGitServiceStageInteractive` unchanged. Both authorized exception-phrase
   fixtures remain; production dot code has no phrase match. The task log records
   original 13/13 guard counts and fail-first failures; current add definitions
   total 16 and the staging class is recorded as 20 collected tests. The sole
   per-file Ruff ignore disables PLR0911 only for service.py, with its reason
   beside it. It necessarily covers other functions in that file, but is bounded
   to one rule and one file and preserves the explicitly mandated seven returns.
   No unrelated lint relaxation or speculative refactor is warranted.

6. **Integration could hang or depend on developer configuration. Refuted for
   the required run.** Both Git-availability and `os.isatty(0)` guards are present;
   global/system Git config is isolated and repo identity set. The independent
   run used default capture, never `-s`, with GIT_TEMPLATE_DIR pointing to the
   worktree's `.venv/empty-git-template` and PYTEST_ADDOPTS setting basetemp to
   `.venv/review-bob-tmp`. All eight cases executed.

## R1–R5 minimalism/de-slop

| Lens | Assessment |
| --- | --- |
| R1 Necessity | PASS — each production change implements an explicit path, staging or outcome requirement; docs explain those changes. |
| R2 Simplest implementation | PASS — direct state branches and a shared final-index report; no new flags, parser or orchestration layer. |
| R3 Native/reused boundaries | PASS — native Git porcelain/pathspecs, existing ShellAdapter, DotGitService, CommandResult and console renderer. |
| R4 No speculative abstractions | PASS — only `_literal` and `_staged_report` helpers, both immediately used; no future-facing configuration or interfaces. |
| R5 No redundant/dead code | PASS — obsolete warnings and exception-string classification removed; repeated test scenarios verify distinct observable behaviors. |

## Validation and limits

Independent exact-text assertions passed for every prescribed Python fenced block;
`stage_interactive` has exactly seven return statements. Documentation and
changelog match the requested behavior. Reviewed the recorded service, add,
full-dot, mypy, repository Ruff/format and Sphinx gate results; did not redundantly
rerun the full suite. The independently executed integration gate and structural
checks above passed. No new security defect was found in changed argument handling;
pre-existing `_git` root-prefix quoting remains an explicitly accepted limitation.
