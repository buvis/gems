Portfolio freshness: NOT refreshed this cycle (PRD 00002 pending)

190 changed symbol(s) omitted (beyond the 40-symbol cap).

## Similar code

- gems:/Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00111-verification-runner.py:12-47
  def main() -> int:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_", "GIT_CONFIG_"))
    }
    environment.update(
        UV_CACHE_DIR="/tmp/gems-autocodex-uv-cache",
        XDG_STATE_HOME="/tmp/gems-autocodex-test-state",
        BUVIS_CONFIG_DIR=str(Path(__file__).with_name("00111-verification-config").resolve()),
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_SYSTEM=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
    )
    result = subprocess.run(
        ["uv", "run", "--no-sync", "pytest", "-q", "--tb=line", *sys.argv[1:]],
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=600,
        check=False,
    )
    sys.stdout.write(result.stdout)
    summary = next(
        (line for line in reversed(result.stdout.splitlines()) if re.search(r"\d+ (?:passed|failed)", line)),
        "",
    )
    counts = {kind: int(value) for value, kind in re.findall(r"(\d+) (passed|failed|skipped)", summary)}
    if not counts:
        return result.returncode or 2
    print(
        f"PASS {counts.get('passed', 0)} FAIL {counts.get('failed', 0)} "
        f"SKIP {counts.get('skipped', 0)} EXIT {result.returncode}"
    )
    return result.returncode

- gems:/Users/bob/git/src/github.com/buvis/gems/src/tools/bim/commands/doc/shared/extractor.py:63-105
  class IncompleteExtraction(Exception):
    """Raised when the extractor cannot produce a complete, usable result.

    The ``transient`` flag distinguishes HTTP/transport failures (retryable)
    from semantic failures like missing fields or uncoercible values
    (not retryable - the model's output is fundamentally unusable for this
    document, retrying with the same input won't help).

    The ``partial`` field carries whatever fields the extractor was able to
    coerce before giving up. The pipeline surfaces these in triage proposals
    so a human reviewer sees what the model did find, not just a wall of
    nulls.
    """

    def __init__(
        self,
        reasons: list[str],
        *,
        transient: bool = False,
        partial: ExtractResult | None = None,
    ) -> None:
        """Initialise with one or more reasons describing why extraction failed.

        Args:
            reasons: Human-readable failure reasons. Joined with ``"; "`` to
                form the exception message and exposed as ``self.reasons`` for
                callers that want to inspect them individually.
            transient: True when the failure is HTTP/transport-related (the
                model server was unreachable or returned an HTTP error) and a
                retry might succeed. False (default) when the failure is
                semantic - missing required fields, uncoercible values, or
                unparseable model output. Only transient failures should be
                retried.
            partial: An ``ExtractResult`` populated with the fields the
                extractor successfully coerced before failing, or ``None``
                when no useful fields were obtained (e.g. JSON parse failure
                or HTTP transport error). The triage path surfaces these in
                the proposal even when extraction was "incomplete".
        """
        super().__init__("; ".join(reasons))
        self.reasons = reasons
        self.transient = transient
        self.partial = partial

## Reuse precedent

- home:/Users/bob/git/src/github.com/buvis/home/.config/autocodex/test_roles.py:32-40
  def test_host_contract_uses_resolved_roles(tmp_path: Path) -> None:
    env = {"AUTOCODEX_OPUS_MODEL": "gpt-6-astra", "AUTOCODEX_OPUS_EFFORT": "high"}
    prompt = driver.host_prompt(tmp_path, tmp_path, "build", env=env)
    assert "opus = gpt-6-astra / high" in prompt
    assert "sonnet = gpt-6.1-sol / medium" in prompt
    assert "haiku = gpt-6-luna / low" in prompt
    assert "gpt-5.6-" not in prompt
    assert "{ROLE_MAPPING}" not in prompt
    assert "gpt-6.1-sol / high" in prompt

## Findings precedent

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00005-behavior-rules-review-01.md
  - F4: read `MACHINE_PATH` (`checks.py:89-92`). The `/` branch requires at least one `segment/`, so `/tmp` and `/config.json` never match, and `$HOME` has no branch.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00005-behavior-rules-review-01.md
  - F1: each of the three guard tests seeds a defect in the same file after its no-finding assertion. Mutation at `ba8e7b8`: with `closed_fences`, `portable_links` and `requirement_source` returning `[]`, all three tests fail.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00007-reviews-and-conversion-review-01.md
  - F7: accepted (ledger entry added). The T-077 outcome records the copy as a choice: each scan runs standalone by `python3 <path>`.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  # Review: 00012-autopilot-package-contract-v1

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  autocodex_blake_anthropic_receipt: /Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/tmp/blake-output-ap00012-c1.txt.receipt.json

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-02.md
  The source's Codex-only inline-input requirement is adapted to the authorized Claude transport: Bob received the complete assembled persona, rubrics and appendices plus readable context/diff paths. His successful raw tool reads establish that the restriction that motivated inline-only Codex prompts does not apply. The 45 MB full diff was not truncated into a prompt. No implementation thread was resumed.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-02.md
  Provider: Anthropic; served model claude-opus-5-5; effort xhigh; session 95ff83bd-845a-4d23-9d77-2b8ff0ab183b.

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00009-walk-memory-proposal-queue-v1-review-1.md
  # Review: 00009-walk-memory-proposal-queue-v1

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00051-qwen-eval-harness-core-v1-review-1.md
  ### Classification

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00051-qwen-eval-harness-core-v1-review-2.md
  ### Adversarial verification

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00058-page-links-accept-javascript-urls-v1-review-1.md
  Fact-Forcing Gate (`gateguard`) — `error=Command blocked by PreToolUse hook:

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00176-guard-the-target-reads-in-the-doctor-v1-review-03.md
  ```

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00182-close-open-dispatch-rows-at-session-handoffs-v1-review-2.md
  `5ebd59c`, `6273c54`, `9d6bdef`, `5a5daa8`, `a026540`. Cycle 1 reviewed the full

## Task prose

### Batch 202610292344
- [x] 00111-backup-parallel-jobs-and-cancellation-v1.md (1 cycle)
- [ ] 00112-backup-live-progress-and-quiet-v1.md

Observations: PRD 00111 completed all nine tasks and its Tail sweep. Final verification: 6237 passed, 16 skipped; Ruff and mypy clean. Original three-lens review, receipts and implementation audit remain intact; companion audit records sweep provenance. Direct-child tar supervision remains a durable deferred non-blocker. Two existing hold triage stubs remain outside the drain. Start PRD 00112 in a fresh build session.

---
name: feedback-buvis-home-repo
description: Home tracked via bare repo ~/.buvis, remote buvis/home is PUBLIC on GitHub. Flood guard is a .gitignore allowlist. Use plain git -C /Users/bob with explicit --git-dir/--work-tree; confirm commit/push plan first; secret-scan before pushing.
metadata:
  node_type: memory
  type: feedback
  originSessionId: 485c8153-7fb1-4569-8c23-2f11ae7a8b8d
  modified: 2026-09-05T08:56:03.151Z
---
User's

---
catchup: skip
design: run
default_model: opus
model_tier_rationale: progress events cross worker threads into the calling thread; ordering and honest percentages decide correctness
---

# backup: live progress and --quiet

Source: `docs/dev/project-management/intake/processed/00107-backup-multi-source-parallel/discovery.md` (Q8). Depends on PRD 00111 (worker pool, `Runner(jobs=...)`) and PRD 00110.

## Overview

### Problem Statement
A long archive shows nothing until it ends: the CLI prints one result line per instance after the fact (`_report_step` in `src/tools/backup/cli.py`). With parallel jobs the operator cannot tell which archives are running, stuck or nearly done. A percentage derived from the compressed output size would be wrong, since compressed bytes are not input bytes.

### Target Users
The solo operator who watches a long interactive run and the cron job that must stay quiet.

### Success Metrics
- `uv run pytest tests/tools/backup/test_progress.py -q` passes.
- `
