# Brush report - gems

- generated: 2026-07-13 15:06 | mode: full | HEAD: fda75cbd9259 | branch: master | unpushed: 0
- phases: catchup OK | git-hygiene OK | assess SCALED-DOWN (see digest) | backlog OK | agents-md OK (no change) | atlas OK

## 1. Done automatically (all reversible)

| action | detail | undo |
|---|---|---|
| `git fetch --prune` | no stale remote-tracking refs found | refetch |
| `git maintenance run --auto` | ran clean, no output | none needed |
| purge-devlocal dry-run | 0 trashed, 1 flagged (see §4) — nothing to apply | n/a |
| capsule update | `dev/local/project-capsule.md` refreshed with today's GitHub state, CI break, backlog delta | edit file back |
| PRD edits (auto-fixed by backlog review, untracked — `dev/local` is gitignored, no git action) | 00041 stale forward-ref fixed; 00067 gained a task; 00069 comment corrected; 00070 two fixes (see backlog-review report) | edit files back, or `mv`/restore from git history N/A (untracked) |
| atlas refresh | `survey --refresh` equivalent, wrote 19.9KB atlas | re-run survey |

## 2. Decisions - mark [x] to approve, then run /brush apply

(none this run — no untracked junk, no local branches, no stashes, no worktrees to act on)

## 3. Manual only - never executed by apply

- MANUAL BR-1 (remote-delete) `origin/build/bincode-3` — merged via PR #9 on 2026-02-17, no longer referenced - you run: `git push origin --delete build/bincode-3`
- MANUAL BR-2 (remote-delete) `origin/build/textual-9` — merged via PR #8 on 2026-02-17, no longer referenced - you run: `git push origin --delete build/textual-9`
- ~~MANUAL BR-3 (CI fix)~~ **DONE 2026-07-13**: added `--skip-editable` to `pip-audit` (`.github/workflows/test.yml:95`), which surfaced 20 real CVEs across 8 deps the broken self-audit had masked. Bumped `uv.lock` for all 8 (cryptography, idna, msgpack, pillow, pip, pydantic-settings, soupsieve, starlette), verified pip-audit clean + full test suite (3670 passed) + mypy clean, added CHANGELOG entry, committed `fc74a1e`. That run then surfaced a second, unrelated pre-existing bug (first time the full tools matrix ran in a while, since `uv.lock` changes trigger it): `test_doc_audit_runs_against_fixture` asserted a report filename verbatim, but Rich's word-wrap at width 80 can split the filename itself at a hyphen on long CI temp paths — fixed by stripping newlines before the check (`tests/tools/bim/doc/test_cli_audit.py`), reproduced and verified locally, committed `b462a95`. **CI confirmed green** on `b462a95` (run 29255152474).
- MANUAL BR-4 (dependency PRs piling up) 18 open PRs, all renovate/dependabot bumps, oldest from 2026-05-06 (mypy v2, ocrmypdf v17) - you run: `git-ferry:review-deps-prs` to triage/merge in batch.

## 4. Phase digests

- catchup: capsule at `dev/local/project-capsule.md` refreshed. 5 open issues (all low-severity, already tracked in PRDs 00046/00049/hold). 18 open PRs, all dependency bots. **Master CI is red** — see BR-3 above; this is new since the 2026-07-09 assessment, which reported CI green.
- assess-evolution: scaled down rather than a full 9-lens re-run — the last full battery ran 2026-07-09 (4 days ago, GO'd 2026-07-10) and only 2 non-code commits (doc-only) landed since, so the architecture findings and roadmap (PRDs 00041-00061 in `backlog/`/`hold/`/`done/`) are still current. No new structural findings this pass beyond the CI break (already captured under catchup/BR-3).
- backlog: `review-prd-backlog` re-ran in full (unattended, auto-applying Recommended fixes) over all 26 current backlog PRDs — the 18 from 2026-07-10 (unchanged, still valid) plus the new 8-PRD "postup" epic (00063-00070) added since. **Verdict: GO.** 0 Blocking, 5 Non-blocking findings auto-fixed (stale PRD cross-reference, a missing frontend-build-hook task, an inaccurate reuse claim, a wrong assumption about dotfiles tracking, a missing CHANGELOG requirement). No reshapes needed — confirmed PRDs 00049/00059 are correctly parked in `hold/` (would collide with 00069 otherwise). The discovery doc `dev/local/discovery/00062-postup-gem.md` looked orphaned to purge-devlocal but isn't — it correctly seeded 00063-00070 and just never became a PRD itself; sequence numbers 00041-00070 are fully consecutive, no gaps or dupes. Full report: `dev/local/audit-results/backlog-review-2026-07-13.md`.
- agents-md: audited, no change. 208 lines (under the 300 hard cap), no anti-pattern phrases, no `agent_docs/` split yet but not needed at this size. File was deliberately edited 2 commits ago (evolution guardrails) — left as-is rather than force a restructure on actively-maintained, load-bearing content. MEMORY.md has 7 entries, well under the 15-entry promotion-cadence trigger — no promotion pass run.
- atlas: refreshed cleanly, 19.9KB, no degradation (tree-sitter available).

## 5. Failures and skips

- assess-evolution: full 9-lens parallel battery deliberately not re-run (see digest above) — a judgment call, not a failure. Nothing else skipped or failed silently.

## 6. How to continue

1. Nothing in section 2 to approve this run.
2. Section 3 (MANUAL) items are yours to run by hand: two stale remote branch deletes, the pip-audit CI fix (recommended first), and a dependency-PR triage pass.
3. `/brush apply` has nothing to do until you check something in section 2 on a future run.
