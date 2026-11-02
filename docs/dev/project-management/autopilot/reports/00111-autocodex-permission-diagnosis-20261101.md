# Autocodex permission failure diagnosis

## Failure capture
- Session/task: PRD 00111 cycle 1; session 170e9af6f2e5468abb5d47912f7449df.
- Goal: obtain independent Anthropic Alice, Blake and Bob completion reviews.
- Error: host_reviewer_permission; Kiro cannot ask for tool approval non-interactively.
- Last successful step: three processes completed and emitted receipts; Bob had no observed permission denials.
- Last failed operations: Alice fs_read requests under docs/dev/tmp; Alice and Blake shell requests through run_command.
- Repeated pattern: shell commands retried after approval failed; coordinator correctly refused coverage despite successful receipts.
- Environment assumptions verified: Kiro only trusts read tools; docs/dev/tmp is denied through .gitignore_global; runFinished success does not establish successful tool access.
- Context pressure: no evidence that context exhaustion caused this incident.

## Root cause
The transport trusts read tools but leaves reviewers trying shell commands. Alice's supplied review inputs were under a denied path. Kiro reports structured policyDenial and failed tool-call approval results, plus stderr denials, then can emit a successful runFinished event. The driver only recognized display_error permission events. It therefore issued successful receipts for incomplete runs. The coordinator caught this inconsistency manually.

## Contained recovery
Prepared docs/dev/tmp/autocodex-permission-fix/changes.patch against the installed files, preserving their pre-existing uncommitted changes. The patch recognizes both recorded structured failure forms, checks Kiro stderr, makes permission_denied independently invalidate Result.ok, rejects denied raw evidence during receipt validation, hashes stderr in new receipts, and documents read-only tool/input preflight obligations. No permission policy, route order, model, review lens, state, cap, or old evidence changed.

Regression tests: four reproduced the original failure before the patch. Final focused suite: 72 passed. Full suite before the final stderr hash/documentation additions: 183 passed, two blocked by macOS denying ps. Escalated retry hit the same outer restriction. Ruff passes. Replay of immutable incident logs now rejects Alice and Blake and accepts Bob.

Installation is pending warrant ac92e2f33850607bdce3bb18c160f42c. The installer checks before/after hashes, runs the complete suite before any installation, backs up existing files, and replaces only five named files atomically. It does not resume the workflow.

## Remaining preventive work
1. Establish a backend reviewer profile that exposes exactly its approved read tools; verify it with actual CLI capability probes. Prompt instructions alone cannot guarantee tool selection.
2. Validate all required input paths before starting the roster. Resolve this incident's explicit read denial through operator-approved recovery; do not relocate denied content or switch launchers to evade it.
3. Supply coordinator-generated gate evidence and permitted review context while preserving Blake's blind inputs. If required coverage cannot be obtained with the allowed tools, report that capability gap before dispatch.
4. Add recorded CLI event fixtures and contract probes for every supported backend, so CLI changes are discovered before expensive review cycles.
5. After installed fix and input/capability recovery, use the normal Resume procedure and a fresh review session. Retain existing findings and evidence; do not certify Alice or Blake retroactively.

## Self-debug report
- Failure class: deterministic transport/policy mismatch plus incomplete success validation.
- Result: partial; tested hardening prepared, installation awaits warrant, review remains paused.
- Burn risk: unchanged retries waste full review cycles; detection now fails closed but cannot grant missing capabilities.
- Follow-up: approve installation, resolve reviewer input/capability contract, then resume through the single state writer.
- Permanent prevention: enforce backend capabilities and evidence semantics in code; do not rely on a coordinator noticing contradictory receipts.

## Installation request correction

Warrant refused ac92e2f33850607bdce3bb18c160f42c before execution because the repository virtualenv resolves to a uv-managed Python outside trusted executable roots. Replacement request b0d77e2a251ef6bd37b57e5f57aad588 uses /Users/bob/.local/share/mise/installs/python/3.14.6/bin/python3, which already provides pytest. The installer and patch are unchanged, and the complete test suite remains an installation prerequisite. Warrant must still validate this runtime; no trust policy was read or changed.

## Verified trusted runtime

Warrant also refused the mise runtime before execution. The operator supplied the trusted executable roots, including /opt/homebrew. Replacement request 38a8385ccb1c2c1976c76d64e86bf767 invokes /opt/homebrew/bin/python3, resolving under /opt/homebrew/Cellar/python@3.15/3.15.2. Pytest 9.1.1 and its dependencies are staged locally in test-deps; the installer uses the trusted interpreter for its subprocess and isolates pytest from auto-loaded plugins. This exact runtime passed 185 tests; the two ps-dependent tests remain mandatory in the full 187-test installation gate. Installed-file preconditions and patch hashes were verified unchanged. No policy change or denied runtime is used.

## Installed fix verified; access recovery pending

Operator reported warrant installation succeeded. SHA-256 verification confirms all five installed files match the tested manifest. Workflow remains paused at host_reviewer_permission. Inspection of the original Alice prompt confirms it explicitly recommended rg/shell commands despite the read-only route. A candidate read-only Kiro profile at docs/dev/tmp/autocodex-permission-fix/sentinel.json validates with kiro-cli agent validate (exit 0); it is not installed or selected, and no live probe or new completion review has run. Kiro configuration reference: https://kiro.dev/docs/custom-agents/configuration-reference/ .

An explicit operator decision is pending: authorize regeneration of the three review-only artifacts (context, diff, engram pack) under the reports directory and reviewer reads there. Existing denied inputs, raw evidence and global policy remain unchanged. No access recovery, route switch or state transition has been performed without that decision.
