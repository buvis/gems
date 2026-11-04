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

**00117-backup-bundle-out-under-source-v1-c1** (codex `gpt-6-astra`, prompt, context and diff inlined because the nested sandbox blocks its file reads; an earlier Claude opus fallback run, made while codex was over its usage limit, is kept below as an extra voice)
- 🟡 Codex: several new tests pass against the pre-change guard (whole-tree tests, source-equality tests, one relative-output parameter), which breaks fail-first. Adjudicated: not a defect. They are deliberate regression guards for behavior the PRD requires unchanged, and the pre-implementation run showed 114 failed (all behavior-changing cases) alongside 168 passed. No rework.
- ⚪ Codex: could not statically verify the test gates (they pass: 282 / 954 / 6569) or the 800-line limit. Verified by `wc -l`: tar_archive.py 716, test_bundle_items.py 530, test_plan_validation.py 405, so R13 holds. Codex marked R2 and R13 as fail; R2 is answered above and R13 was an unverified guess.
- Claude opus fallback run (extra voice): 🟡 dead `ValueError` branch and double normalization of items; ⚪ unused `items: object = None` default; ⚪ case-insensitive volume weakness.

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: fail
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
