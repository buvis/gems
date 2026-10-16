# PRD 00093 design review

Verdict: approved for implementation; no blocking findings.

Reviewed the PRD, design plan, root instructions, existing staging service,
CommandAdd, CLI/TUI callers, ShellAdapter, and affected unit tests independently.
Only the root AGENTS.md is present in this checkout.

- Correctness: porcelain classification matches ShellAdapter's actual return
  contract. Literal pathspecs plus shell quoting address glob and quote handling;
  check-ignore correctly receives a plain quoted path. Cwd-first absolute paths
  and lexists preserve the intended link and missing-path behavior. Reporting
  describes final index state without claiming previously staged changes are new.
- Architecture: CommandAdd passes through CommandResult; the existing lazy CLI
  adapter renders via console.report_result. The TUI retains its distinct shared
  whole-file stage action. No new UI-specific business logic is needed.
- Test fidelity: the prescribed real-Git cases complement exact-command mocks,
  exercise production-style bare configuration, and assert index contents. Keep
  both stdin guards and capture. Record both required fail-first runs before
  implementing their corresponding production changes.
- Premises: test_add currently has 13 test definitions. The exception phrase
  occurs only in the stage class, check_ignore parametrization, and the expressly
  approved hooks-path test at line 97. Preserve the latter two unchanged. The
  implementer must retain the required collected-count evidence before edits.
- Scope: transcribe the specified final functions exactly. Existing _git prefix
  quoting, directory intent-to-add error handling, and staged-deletion ambiguity
  remain accepted limitations, not reasons to redesign this patch.

One wording limitation: “no git command” for a missing path is stronger than the
prescribed code. DotGitService initialization already performs configuration
checks before CommandAdd resolves the path. The prescribed assertion accurately
guarantees no stage_interactive call and no staging; preserve the exact code and
describe that narrower guarantee in completion reporting.

This is design approval, not implementation verification. All planned execution,
test, lint/type/documentation, and independent implementation-review gates remain.
