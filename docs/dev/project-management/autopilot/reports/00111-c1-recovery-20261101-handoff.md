# PRD 00111: permission recovery handoff

The operator authorized regeneration of the context, diff and engram pack under
the reports directory and reviewer reads there. The installed driver hardening
is verified against its tested manifest. The prior permission failures and all
original reviewer evidence remain intact.

Resume review cycle 1, cap 2, in a fresh session. All five implementation tasks,
their model provenance, the batch identity and work_start_sha are unchanged.
No completion review or convergence was performed in this recovery session.

## Verified inputs and transport

- `00111-c1-recovery-20261101-inputs.json` records hashes, source artifacts and
  the pinned reviewed head `3976e25f4b8ce0201c5693389bf3debf17c61ecb`.
- The regenerated diff differs from the prior staging only in dispatch-metrics
  bookkeeping. Source, tests, product documentation, dependency manifest and
  lockfile have no changes between that reviewed head and the recovery head.
- `00111-c1-recovery-20261101-access-probe.jsonl` and `.stderr` preserve the live
  Kiro probe. All three file reads and native file search/text search succeeded;
  observed model is `claude-opus-5.5`, effort `xhigh`, with no permission denial.
  A calcard MCP startup warning was unrelated to these successful local reads.
- The probe is not a review and has no review receipt or coverage claim.
- No Kiro profile, permission policy, global ignore rule or backend order was
  changed. The candidate sentinel profile remains uninstalled; it is not needed
  to use the verified existing read-only route.

## Next session

Read the installed host contract and full review-work-completion skill. Run the
implementation audit/review-route checks before dispatch. Reuse the corrected
`00111-c1-recovery-20261101-{alice,blake,bob}-prompt.md` files in this directory,
preserving their complete rubrics and all three fresh, isolated reviewer lanes.
Their transport paragraph supersedes shell examples: use native read/search
tools, never shell commands. Blake receives only the PRD and test gate; do not
give Blake this handoff, context pack, diff, history or sibling findings.

The context and supplied full-suite gate describe the unchanged product tree at
the pinned head. Verify that the product tree is still unchanged before reuse;
if it changed, regenerate context and gates before review. All new output and
receipt paths must be unique. Do not reuse the failed Alice/Blake receipts or
treat the access probe as coverage. Run the complete roster, consolidate every
required rubric, and follow the ordinary decision gate and cap rules.

If staging must run again, place the required review inputs under reports and
carry this explicit operator authorization forward. Do not send new reviewers
the obsolete docs/dev/tmp input paths or the shell-oriented transport paragraph.

The tested driver fix prevents false successful receipts. A general automated
backend capability/input preflight remains future hardening; this recovery does
not claim that every possible autocodex failure has been eliminated.
