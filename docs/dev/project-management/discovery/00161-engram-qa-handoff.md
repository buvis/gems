# Engram QA handoff to the Gems port

Status: source QA disposition retained for target planning. No port or product
fix has been implemented by this handoff.

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
- `docs/dev/project-management/prds/hold/00017-*.md` through `00027-*.md`:
  detailed source specifications, retained as reference only.

Observed 2026-11-23 before this routing edit: Engram HEAD
`4ef8965d270eacdaae52872f97237b28a740c229`; Gems HEAD
`4b4b8ab685b7f7b861b3508f4110e1d60750378b`. All three source prerequisite PRDs
were in the completed lifecycle directory. Gems had no `src/tools/engram` or
`tests/tools/engram` tree. Recheck these facts before target implementation.

## Target ownership

The numbers below identify held source specifications, not Gems PRD numbers.
Use the port's existing phases and preserve dependencies when splitting target
work. Both HIGH findings are listed first.

| Source spec | Accepted correction | Port phase and adaptation |
|---|---|---|
| 00017 | Verify served model identity; reject malformed endpoints; check store identity before work | Core client in Phase 1; YAML settings in Phase 2; CLI/status diagnostics in Phase 3. Keep mocked observations labeled. |
| 00018 | Index source lookups by corpus/path | Store in Phase 1. An additive index changes database bytes; reconcile with the no-change cutover checks before applying it. |
| 00019 | Validate/canonicalize registration; prevent empty-registry pruning; snapshot harvest registry | Corpora and harvest in Phase 1, command errors in Phase 3. Preserve legacy memory attribution. |
| 00020 | Read NUL-delimited tracked paths; contain source reads; filter scope before enumeration | Enumeration in Phase 1; direct pack inputs in Phase 3. Keep existing independent memory/transcript roots. |
| 00021 | Verify worktree membership; canonicalize lookup and harvested source identity | Core in Phase 1 and command mapping in Phase 3. Retain differing historical findings. |
| 00022 | Exclude shifted worktree symbols; bound path resolution; use physical diff lines | Pack/diff core in Phase 1. Capture deliberate result changes in Phase 3 contract tests. |
| 00023 | Hold writer locks; clean interrupted rebuilds; explicit recoverable corruption handling | Windows-safe locking in Phase 1; explicit recovery CLI in Phase 3. Adapt the source's POSIX-specific details. |
| 00024 | Redact published context; fence excerpts; filter controls; create private artifacts | Core formatting/storage in Phase 1; machine-output adapters and consumer checks in Phase 3. Preserve existing data by default. |
| 00025 | Isolate parser failures; clarify config and missing-directory diagnostics | Parsers in Phase 1, YAML/config errors in Phase 2, Click/CommandResult output in Phase 3. Do not port obsolete TOML handling literally. |
| 00026 | Reject path imports/control bytes in migrated memory metadata | Memory migration in Phase 1, CLI outcomes in Phase 3. Downstream import effects remain unverified. |
| 00027 | Correct lifecycle, downloads, corpus coverage and upgrade guidance | Target tool documentation and cutover in Phase 4. Do not spend work reorganizing the retired standalone changelog. |

## Compatibility decisions required in target specifications

The source specifications cannot be executed as written. The port promises
byte-identical output, exit codes, unchanged chunking/cache behavior and no
production DB mutation during cutover. Some accepted fixes intentionally change
those properties. Before target PRD emission:

1. Refresh the inventory at the selected post-00016 source commit.
2. Classify each QA correction as a port-phase fix or a target follow-up.
3. For each behavioral change, record the precise parity exception and affected consumer calls.
4. Preserve unaffected golden output and add separate regression fixtures for each approved correction.
5. Resolve database schema/data migrations against the cutover hash checks; do not silently weaken either requirement.
6. Use Gems paths, Python support, settings, platform locks and test gates in executable PRDs.

These are planning obligations, not a request for another standalone build.
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
