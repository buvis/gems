---
head_sha: 63c7245cea9b1feeb9350783c03c10544649788b
reviewers: alice,blake,bob,eve
---

# Review 1: 00108-sysup-uv-tool-python-upgrade-in-place-v1 (fast-track lane)

One card, `00108-sysup-uv-tool-python-upgrade-in-place-v1-c1`. Carl (gemini) did not report: copilot returned "monthly quota exceeded" twice. Bob's codex run read no file (`sandbox_apply: Operation not permitted`); a `general-purpose` subagent with the Read tool ran the Bob lens instead.

## Alice

**00108-sysup-uv-tool-python-upgrade-in-place-v1-c1**
R1-R13 pass.
🟡 Class docstring stale ("plain" installs), fixed in commit 63c7245c.
🟡 `_run_install` and the "reinstall" failure messages say install; the card pins the messages, so left as is.
⚪ Two dropped skip receipts (`future = false`) not pinned by the in-place test; optional, behavior covered.

## Blake

**00108-sysup-uv-tool-python-upgrade-in-place-v1-c1**
B1-B19 pass except B17 (docs gap), fixed in commit 63c7245c.
🟡 Order-35 paragraph lacked the keeps-requirements statement and the constraints/index-options list; fixed in commit 63c7245c.
⚪ Stale class docstring (fixed); "reinstall" message wording (pinned by the card).

## Bob

**00108-sysup-uv-tool-python-upgrade-in-place-v1-c1**
R1-R13 pass.
🟡 Stale class docstring (fixed).
⚪ Cannot statically verify that the oldest uv supports `uv tool upgrade --python`, nor that an editable receipt keeps its checkout under the upgrade (tests mock subprocess).
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Eve

**00108-sysup-uv-tool-python-upgrade-in-place-v1-c1**
D1-D5 pass. FIX: stale docstring (fixed), docs wording (fixed), add two `future = false` receipts and a pinned customized case to the in-place test (open), fold `test_accepts_plain_receipts_with_harmless_metadata` into it (open).
VERIFY (open): (1) after a failed sync uv may have removed the receipt, so both rollback upgrades fail and the tool stays broken; check uv 0.13.5 `upgrade_tool` and `InstalledTools::create_environment`; (2) the PRD's own unverified claim that `uv tool upgrade --python` records the new interpreter in the receipt; run it on huggingface-hub and check that a second sysup prints `all uv tools on python 3.14`.
KNOWN: install/reinstall vocabulary, CHANGELOG wording, PRD prose imprecision.

Verdict: converged
Tests: 5671 passed, 0 failed, 16 skipped (fast-track batch suite, 1 xfailed)
codex_rung_guard: not fired
