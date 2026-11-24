# Engram QA handoff to the Gems port

Status: Gems owns PRDs 00163-00173 in hold. No port or product fix has been implemented by this handoff.

## How readiness becomes visible

The port agent must perform the
[required QA release checkpoints](00161-engram-port-plan.md#required-qa-release-checkpoints)
at Phase 3 and Phase 4 closeout, then after each relevant QA dependency completes.
It moves verified-ready PRDs into the executable backlog and reports the promoted
IDs. It records an exact blocker for each PRD still held. The user does not need
to inspect the directories or remember to release them. These are workflow
requirements for the future port job; no watcher has been started.

## Original continuation status, checked 2026-11-24

Source: `docs/dev/tmp/00161-handoff-20261116-1427.md` in Gems. This tracked
summary preserves the remaining work so it does not depend on keeping that
temporary file. Observed source HEAD: engram e413696; target HEAD: Gems 61707c50.

| Original step | Status and next action |
|---|---|
| 1. Verify standalone 00014-00016 and completion reviews | Completed check: all three are in the completed PRD directory and have cycle-2 completion-review records. This is not a claim that every historical check passed. |
| 2. Run main and evaluation suites | Not rerun for this handoff in this session. From the Engram checkout, run `.venv/bin/python -m pytest -q --ignore=eval` and `PYTHONPATH=src:. .venv/bin/python -m pytest -q eval` at the chosen source commit; record pass/fail/skip counts. Historical QA counts do not replace that checkpoint. |
| 3. Pin source and refresh inventory | Not completed. The plan freshness line still describes a0892e6 while 00014 was building. Refresh all rows against the selected post-batch commit after verification. |
| 4. Reinstall standalone; optional backfill | Current installation not verified. Preserve the documented external-install handoff if needed; no production backfill, rebuild or model repin was performed. Backfill is optional and still requires the stated backup and explicit authorization. |
| 5. Create port Phase 1 PRD | Not completed. Gems has QA follow-up PRDs 00163-00173, but no Phase 1 core-port PRD or src/tools/engram tree. Create only Phase 1 after the source checks; it is distinct from the QA fixes. |
| Later phases | Not started by this session. Create each phase after the preceding phase lands, as the original handoff requires. Phase 5 also waits for 00122, still in the executable backlog at this check. |

The older instruction to ask approval for every phase PRD is superseded by the
user's current standing authorization for routine work. Explicit production
data, install-tool permissions, release and retirement restrictions still apply.

No port job was launched by this status check. The next port session starts at
the fresh-suite and inventory checkpoints, then creates the Phase 1 PRD; it does
not drain the QA follow-ups before the port exists.

Authority: user decision of 2026-11-16 in
[the port plan](00161-engram-port-plan.md), reaffirmed on 2026-11-23.
Ship Engram inside buvis-gems after standalone PRDs 00014-00016 finish.
The recommendation to execute a new standalone QA backlog was an agent error.

## Source evidence

Repository: buvis/engram. All paths below are relative to that repository:

- `docs/dev/project-management/audit-results/agoge-2026-11-16.md`: 31 packets.
- `docs/dev/project-management/audit-results/agoge-2026-11-15-2.md`: 16 earlier packets.
- `docs/dev/project-management/audit-results/agoge-triage-2026-11-23.md`: all
  47 dispositions, duplicates, evidence limits and deferral conditions.
- Former source PRDs 00017-00027 were transferred to Gems on 2026-11-24; no duplicate source copies remain. The ownership table below links their replacements.

Observed 2026-11-23 before this routing edit: Engram HEAD
`4ef8965d270eacdaae52872f97237b28a740c229`; Gems HEAD
`4b4b8ab685b7f7b861b3508f4110e1d60750378b`. All three source prerequisite PRDs
were in the completed lifecycle directory. Gems had no `src/tools/engram` or
`tests/tools/engram` tree. Recheck these facts before target implementation.

## Target ownership

The table maps former source numbers to their current Gems PRDs. The Gems PRDs remain on hold until their port prerequisites are met.
Use the port's existing phases and preserve dependencies when splitting target
work. Both HIGH findings are listed first.

| Former source / Gems owner | Accepted correction | Port phase and adaptation |
|---|---|---|
| 00017 / [00163](../prds/hold/00163-engram-verify-embedding-model-identity-v1.md) | Verify served model identity; reject malformed endpoints; check store identity before work | Core client in Phase 1; YAML settings in Phase 2; CLI/status diagnostics in Phase 3. Keep mocked observations labeled. |
| 00018 / [00164](../prds/hold/00164-engram-index-chunks-by-source-v1.md) | Index source lookups by corpus/path | Store in Phase 1. An additive index changes database bytes; reconcile with the no-change cutover checks before applying it. |
| 00019 / [00165](../prds/hold/00165-engram-validate-repository-registry-v1.md) | Validate/canonicalize registration; prevent empty-registry pruning; snapshot harvest registry | Corpora and harvest in Phase 1, command errors in Phase 3. Preserve legacy memory attribution. |
| 00020 / [00166](../prds/hold/00166-engram-bound-indexing-to-repositories-v1.md) | Read NUL-delimited tracked paths; contain source reads; filter scope before enumeration | Enumeration in Phase 1; direct pack inputs in Phase 3. Keep existing independent memory/transcript roots. |
| 00021 / [00167](../prds/hold/00167-engram-unify-worktree-source-identity-v1.md) | Verify worktree membership; canonicalize lookup and harvested source identity | Core in Phase 1 and command mapping in Phase 3. Retain differing historical findings. |
| 00022 / [00168](../prds/hold/00168-engram-exclude-worktree-self-matches-v1.md) | Exclude shifted worktree symbols; bound path resolution; use physical diff lines | Pack/diff core in Phase 1. Capture deliberate result changes in Phase 3 contract tests. |
| 00023 / [00169](../prds/hold/00169-engram-protect-store-write-lifecycle-v1.md) | Hold writer locks; clean interrupted rebuilds; explicit recoverable corruption handling | Windows-safe locking in Phase 1; explicit recovery CLI in Phase 3. Adapt the source's POSIX-specific details. |
| 00024 / [00170](../prds/hold/00170-engram-sanitize-retrieved-context-v1.md) | Redact published context; fence excerpts; filter controls; create private artifacts | Core formatting/storage in Phase 1; machine-output adapters and consumer checks in Phase 3. Preserve existing data by default. |
| 00025 / [00171](../prds/hold/00171-engram-isolate-malformed-input-failures-v1.md) | Isolate parser failures; clarify config and missing-directory diagnostics | Parsers in Phase 1, YAML/config errors in Phase 2, Click/CommandResult output in Phase 3. Do not port obsolete TOML handling literally. |
| 00026 / [00172](../prds/hold/00172-engram-reject-imports-in-migrated-memory-v1.md) | Reject path imports/control bytes in migrated memory metadata | Memory migration in Phase 1, CLI outcomes in Phase 3. Downstream import effects remain unverified. |
| 00027 / [00173](../prds/hold/00173-engram-correct-operating-documentation-v1.md) | Correct lifecycle, downloads, corpus coverage and upgrade guidance | Target tool documentation and cutover in Phase 4. Do not spend work reorganizing the retired standalone changelog. |

## Compatibility decisions required in target specifications

The transferred specifications cannot execute until their target prerequisites are verified. The port promises
byte-identical output, exit codes, unchanged chunking/cache behavior and no
production DB mutation during cutover. Some accepted fixes intentionally change
those properties. Before releasing the target PRDs from hold:

1. Refresh the inventory at the selected post-00016 source commit.
2. Classify each QA correction as a port-phase fix or a target follow-up.
3. For each behavioral change, record the precise parity exception and affected consumer calls.
4. Preserve unaffected golden output and add separate regression fixtures for each approved correction.
5. Resolve database schema/data migrations against the cutover hash checks; do not silently weaken either requirement.
6. Use Gems paths, Python support, settings, platform locks and test gates in executable PRDs.

These are hold-release obligations for Gems, not a request for another standalone build.
The existing per-machine benchmark requirement and retirement criteria remain.
The research eval stays in the source archive; its suite is not a Gems runtime gate.

## Retained deferrals

Keep the source disposition's closure conditions for preflight caching,
unchanged-harvest caching, name-miss lookup optimization, vector partition
layout, differing historical findings, and expanded top-level language coverage.
Do not turn these into port blockers without new evidence.

The historical install/upgrade and live-server QA gaps remain recorded.
This handoff performs no runtime tests, new QA lanes, installation, rebuild,
release, retirement or production-data change.

## Transfer validation: 2026-11-24

The user requested target ownership now. PRDs 00163-00173 replace source PRDs
00017-00027. Evidence blocks are unchanged; dependency links use Gems IDs.
Expected implementation paths and tests use the target layout. YAML settings,
Click/CommandResult boundaries, platform locks and the Gems CI gates replace
standalone assumptions. The target module map still requires grounding after
the prerequisite port lands; these PRDs are deliberately outside the executable
backlog. PRD 00164 also waits until the initial cutover DB checks finish.

The obsolete standalone changelog cleanup is not a Gems task. PRD 00173 covers
Gems installation/configuration docs instead, while retaining the original
finding as historical evidence. The existing pre-port discovery filename 00161
is not an Engram executable PRD number; Gems PRD 00161 belongs to BIM.

Validation passed: 11 unique target IDs, template order, dependency and report links, all 47 packet dispositions, and unchanged QA evidence blocks. Source grounding reported 0 blocking and 0 unverified references; this does not verify the absent target modules. Runtime tests were not run for this document transfer. Both repository diffs passed git diff --check.
