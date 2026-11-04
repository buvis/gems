---
head_sha: d8e6bec6f80e6f539bc7eeef3228c8a4ecfb1ae0
reviewers: alice,blake,bob,carl,eve
---

Lane: fast-track, one card (`00117-backup-bundle-out-under-source-v1-c1`). Full per-lane report: `docs/dev/tmp/00117-backup-bundle-out-under-source-v1-c1-fast-track-review.md`.

## Alice

**00117-backup-bundle-out-under-source-v1-c1**
- 🟡 `_reject_out_inside_source` calls `_normalize_items` itself, so `run` validates and normalizes items twice; the `items: object = None` default is unneeded (tar_archive.py:269/285). Behavior correct, cost trivial. Not CRITICAL/HIGH, no rework.
- ⚪ rst/CHANGELOG wording fine, no action.

## Blake

**00117-backup-bundle-out-under-source-v1-c1**
- ⚪ Docs addition is a multi-sentence paragraph, not one sentence.
- ⚪ Containment compares resolved paths without case folding (pre-existing in the whole-tree guard).
- ⚪ Containment rejects `out` inside an item even when an exclude would filter it (conservative).

## Bob

**00117-backup-bundle-out-under-source-v1-c1** (codex backend hit its usage limit; the copilot fallback model was refused; the lane ran as a Claude opus subagent with Read tools)
- 🟡 Dead `ValueError` branch in `_run_validated` and double normalization after the change; return the normalized list and pass it down.
- ⚪ Unused `items: object = None` default on `_reject_out_inside_source`.
- ⚪ Case-insensitive volume: `.Config` item vs `.config` out passes the check (pre-existing weakness class).

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

**00117-backup-bundle-out-under-source-v1-c1**
- ⚪ Docs paragraph longer than the single requested sentence.
- ⚪ No case folding in the containment check.
- ⚪ Redundant item normalization across run and plan paths.

## Eve

**00117-backup-bundle-out-under-source-v1-c1**
- FIX (MEDIUM): double normalization, dead ValueError branches, unused default (tar_archive.py:269,181-187,317-321).
- FIX (LOW): docs paragraph exceeds one sentence and leaks internals.
- KNOWN: case-insensitive filesystems (pre-existing); `out` naming an existing directory fails at `os.replace` with EISDIR (pre-existing, no data loss).
- D1-D5: pass.

Verdict: converged
Tests: 6569 passed, 0 failed, 16 skipped (fast-track batch suite, 1 xfailed)
codex_rung_guard: not fired
