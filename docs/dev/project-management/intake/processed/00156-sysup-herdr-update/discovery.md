# Discovery: sysup Herdr clone audit

## Classification

Depth: standard | Date: 2026-11-15
Source: `idea.md` beside this file; observations are recorded in `evidence.md`.
Requirement clarity, breadth, integration impact, and complexity are medium
for the selected audit slice. The original agent-porting proposal is broader.

## Problem

sysup already delegates community-mod updates to hmod. Personal Herdr mod and
layout clones remain outside that updater, with no persistent reminder when
their recorded source version differs from the installed app. Some clones
reference another personal clone or a source that no longer exists. Users need
an honest review signal before any automatic porting can be specified.

## Requirements

### Must have

- R1: Inspect personal mod and layout clone metadata without executing mods or
  changing Herdr files. Honor HERDR_APP_HOME, falling back to ~/.config/herdr-app.
- R2: Compare a clone's recorded version with the invoked Herdr binary's version.
  Report differences as review needed, never as proof of broken compatibility.
- R3: Distinguish direct shipped sources from unresolved/personal ancestry.
  Report unresolved ancestry even when the recorded version matches.
- R4: Preserve review warnings through sysup's existing attention mechanism.
  A successful complete audit without warnings clears its prior attention;
  an unreadable or malformed inventory fails instead of clearing it as healthy.
- R5: Join the default macOS plan after the existing hmod step. Work with the
  window closed, and perform no audit in sysup dry-run mode.
- R6: Keep command behavior reusable through the existing capability/StepResult
  seam; rendering and attention persistence remain with sysup's adapters.

### Out of scope

- App/core update requests, restart, completion polling and readiness detection.
- Snapshot storage, clone rewriting, version-marker changes, agent launches,
  blanket mod checks, compatibility certification, or automatic git adoption.
- Replacing hmod, changing its consent policy, or auditing community-mod code.

The excluded original work is retained in intake 00157, not declared shipped.

## Constraints

- Preserve the shipped herdr-mods updater and its tests.
- Use existing sysup result statuses and atomic attention persistence; no new
  clone-state database or configuration location.
- A CLI binary's version is not independently a running-window version or a
  proof that generated files came from that binary. State this limitation.
- Malformed metadata and unsafe filesystem links must never produce an all-clear.
- No live Herdr operation is needed to implement or test this audit.

## Codebase Context

- **Relevant code**: `src/tools/sysup/capabilities/__init__.py`,
  `src/tools/sysup/runner.py`, `src/tools/sysup/step_result.py`,
  `src/tools/sysup/attention.py`, and `src/tools/sysup/default.yaml`.
- **Conventions**: capability inputs and result iterators, subprocess mocks,
  temporary homes, console rendering outside the capability.
- **Integration points**: one capability module, registry/default wiring,
  focused capability and CLI integration tests, sysup reference documentation.
- **Ownership evidence**: hmod excludes personal clones; Herdr owns app downloads
  and updates core after app upgrades. CLI update commands expose no verified
  completion contract in the inspected help/status output.

## Success Criteria

- Temporary-home tests distinguish direct matching clones, version differences,
  unresolved ancestry, invalid metadata, and unsafe links.
- Tests prove mod/layout bytes are unchanged and no update/check/restart or
  agent command is invoked. Only the version query is permitted.
- CLI tests prove warnings survive into status, clean audits clear them,
  failures retain attention, and unselected audits preserve prior attention.
- Default-plan tests prove macOS ordering, Linux exclusion, existing hmod
  behavior, and dry-run nonexecution.

## Risks

- **Noisy version signal**: a release need not change a particular source.
  Describe the finding as review needed; never automatically bump provenance.
- **Missing baseline**: old upstream files cannot be recreated by taking a
  current snapshot. Leave three-way merge promises to the follow-up.
- **Clone-of-clone ancestry**: the observed buvis layout names absent my-main.
  Report the limitation rather than resolving it by guessing a shipped source.
- **Independent upgrades**: the CLI binary and generated assets can diverge.
  Report the version basis and do not claim a completed compatibility check.

## Discovery Log

- Problem, integration points, constraints, and behavioral success criteria
  came from the intake and repository inspection; redundant questions skipped.
- A scope question offered audit-first, update requests too, or the full
  proposal. No answer was received before drafting. Audit-first is an explicit
  reversible planning assumption under standing authorization, not user consent
  to discard the rest. Intake 00157 retains that work.
- Restart remains outside this slice. The original default-off constraint is
  carried into the follow-up; processing this intake authorized no live restart.
- New contract choices: exact version-string comparison, warned review signals,
  failed unreadable inputs, and a separate default audit entry. These are
  supported local planning decisions, not claimed existing Herdr behavior.
- The original statement that community mods are never updated is superseded
  by shipped hmod integration. The original blanket check is excluded because
  the installed guide says checks execute init code with possible side effects.

## Open Questions

No blocking question remains for the audit slice. Update completion,
snapshot provenance, and supervised porting contracts remain in intake 00157.
