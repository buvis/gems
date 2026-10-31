Portfolio freshness: NOT refreshed this cycle (PRD 00002 pending)

194 changed symbol(s) omitted (beyond the 40-symbol cap).

## Similar code

- gems:/Users/bob/git/src/github.com/buvis/gems/src/tools/bim/commands/doc/shared/ocr.py:204-213
      def _backup_original(self, backup_bytes: bytes, sha256: str) -> Path:
        originals_dir = self._state_dir / "originals"
        originals_dir.mkdir(parents=True, exist_ok=True)
        # ISO 8601 basic compact form (Zulu). Spec §9 mandates the full sha256
        # in the backup filename so the pre-OCR hash remains the canonical
        # identifier (no risk of [:8] prefix collision across many backups).
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = originals_dir / f"{timestamp}-{sha256}.pdf"
        atomic_write_bytes(backup_path, backup_bytes)
        return backup_path

- gems:/Users/bob/git/src/github.com/buvis/gems/src/tools/klyreon/assets/installer.py:272-273
  def _at_or_under_a_root(path: Path, roots: set[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)

- gems:/Users/bob/git/src/github.com/buvis/gems/tests/tools/backup/test_config.py:218-244
  class TestBackupSpecificTypoGuard:
    """A typo in a backup-specific file (buvis-backup*.yaml) is rejected, even
    though shared global fields are tolerated — the projection must not silently
    drop a misspelled backup key and run the bundled plan."""

    def test_typo_in_backup_specific_file_is_rejected(self, tmp_path: Path) -> None:
        cfg_dir = tmp_path / "cfg"
        cfg_dir.mkdir()
        _write(cfg_dir / "buvis-backup.yaml", "instnaces:\n  x: {use: tar-archive}\n")
        with pytest.raises(FatalError) as exc_info:
            load_config(config_dir=str(cfg_dir))
        assert "instnaces" in str(exc_info.value)

    def test_misspelled_exclude_in_backup_file_is_rejected(self, tmp_path: Path) -> None:
        cfg_dir = tmp_path / "cfg"
        cfg_dir.mkdir()
        _write(cfg_dir / "buvis-backup.yaml", "exclude: [foo]\n")  # should be 'excludes'
        with pytest.raises(FatalError) as exc_info:
            load_config(config_dir=str(cfg_dir))
        assert "exclude" in str(exc_info.value)

    def test_valid_backup_specific_excludes_directive_accepted(self, tmp_path: Path) -> None:
        cfg_dir = tmp_path / "cfg"
        cfg_dir.mkdir()
        _write(cfg_dir / "buvis-backup.yaml", "excludes+: [scratch]\n")
        cfg = load_config(config_dir=str(cfg_dir))
        assert "scratch" in cfg.excludes

- gems:/Users/bob/git/src/github.com/buvis/gems/tests/tools/morph/test_deblank_extra.py:42-50
      def test_restore_no_backup(self, tmp_path: Path) -> None:
        original = tmp_path / "test.pdf"
        backup = tmp_path / "test.pdf.old"
        warnings: list[str] = []

        CommandDeblank._restore_original(original, backup, warnings)

        assert not original.exists()
        assert warnings == []

- gems:/Users/bob/git/src/github.com/buvis/gems/src/tools/klyreon/assets/installer.py:94-96
  def _backup_path(target: Path, moment: dt.datetime) -> Path:
    stamp = moment.strftime("%Y%m%d%H%M%S")
    return target.with_name(target.name + _BACKUP_PREFIX + stamp)

- gems:/Users/bob/git/src/github.com/buvis/gems/src/tools/klyreon/backends/stub.py:43-56
      def run(self, prompt: str, timeout: int) -> IngestPayload:  # noqa: ARG002 - timeout unused offline
        """Return the next canned payload, or the one its marker matches."""
        if self._by_marker:
            for marker, payload in self._by_marker.items():
                if marker in prompt:
                    return payload
            markers = sorted(self._by_marker)
            msg = f"stub backend: no canned payload matches any marker in the prompt (markers: {markers})"
            raise BackendError(BackendReason.PARSE, msg)

        if not self._queue:
            msg = "stub backend: no canned payload left to return (more run() calls than payloads provided)"
            raise BackendError(BackendReason.PARSE, msg)
        return self._queue.pop(0)

- gems:/Users/bob/git/src/github.com/buvis/gems/src/tools/klyreon/commands/export_claims.py:29-32
      def __init__(self, root: Path, *, out: Path | None = None, now: dt.datetime | None = None) -> None:
        self.root = root
        self.out = out
        self.now = now

## Reuse precedent

- container-images:/Users/bob/git/src/github.com/buvis/container-images/apps/exchanger/app/routes.py:592-615
      def backup() -> BackupResponse:
        """Create backup file with current database contents (atomic snapshot)."""
        logger.debug("backup requested")
        _check_no_task_running()

        backup_data = db.export_all()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        backup_dir = _get_backup_dir()
        filename = _backup_filename(timestamp)
        backup_path = backup_dir / filename

        with gzip.open(backup_path, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f)

        logger.info("backup created: %s (%d rates, %d symbols, %d metadata, %d favorites)", filename, len(backup_data["rates"]), len(backup_data["symbols"]), len(backup_data["metadata"]), len(backup_data["favorites"]))
        return BackupResponse(
            filename=filename,
            timestamp=timestamp,
            rates_count=len(backup_data["rates"]),
            symbols_count=len(backup_data["symbols"]),
            metadata_count=len(backup_data["metadata"]),
            favorites_count=len(backup_data["favorites"]),
        )

- ddb:/Users/bob/git/src/github.com/doogat/ddb/tests/e2e/smoke_core.rs:251-267
  fn smoke_16b_compact_backup_path() {
    let repo = DdbTestRepo::init();
    repo.ddb()
        .args(["register-node", "backup-path-test"])
        .assert()
        .success();
    let backup = repo.path().join("custom-backup.bundle.tar");
    let backup_arg = backup.to_string_lossy().into_owned();

    repo.ddb()
        .args(["compact", "--force", "--backup-path", &backup_arg])
        .assert()
        .success()
        .stdout(predicate::str::contains("backup:"))
        .stdout(predicate::str::contains(&backup_arg));
    assert!(backup.is_file(), "custom backup file was not created");
}

- agent-skills:/Users/bob/git/src/github.com/buvis/agent-skills/src/agent_skills_braid/cli.py:418-429
  def _backup(
    path: Path,
    root: Path,
    category: str,
    result: Result,
    emit: Callable[[str], None],
) -> None:
    backup = root / category / path.name
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(backup))
    result.backed_up += 1
    emit(f"BACKUP {path} -> {backup}")

- claude-autopilot:/Users/bob/git/src/github.com/buvis/claude-autopilot/skills/run-autopilot/scripts/tracon/panels.py:214-247
  def build_head(
    state: model.LoopState,
    rows: Sequence[model.MetricsRow],
    usage: SessionUsage,
    status: Status,
    prd_counts: tuple[int, int],
    batch_id: str,
    root_name: str,
    session_start: float | None,
    agent_counts: tuple[int, int] | None = None,
    now: float | None = None,
) -> Panel:
    if now is None:
        now = time.time()

    row1 = _row_head(state)

    row2 = phase_strip(state)
    row2.no_wrap = True
    row2.overflow = "ellipsis"

    row3 = _row_progress(
        rows,
        status,
        prd_counts,
        model.batch_completed_count(state),
        batch_id,
        session_start,
        now,
        usage,
    )
    row4 = _row_usage(usage, status, agent_counts)

    return Panel(Group(row1, row2, row3, row4), title=root_name)

- container-images:/Users/bob/git/src/github.com/buvis/container-images/apps/exchanger/app/routes.py:580-589
      def list_backups() -> list[BackupInfo]:
        """List available backup files."""
        logger.debug("list_backups requested")
        backup_dir = _get_backup_dir()
        backups = []
        for f in sorted(backup_dir.glob("backup_*.json.gz"), reverse=True):
            ts = _parse_backup_filename(f.name)
            if ts:
                backups.append(BackupInfo(filename=f.name, timestamp=ts))
        return backups

## Findings precedent

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00005-behavior-rules-review-01.md
  Pat (`agents/pat.md` rendered by `render_prompt.py`, Sonnet lane, `sonnet-run.sh -t ""`, no tools) reviewed `11f54ac..ba8e7b8` against the quoted findings and the recorded verification. Output: `docs/dev/tmp/review-task-00005c1rw.md`.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  # Review: 00012-autopilot-package-contract-v1

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  autocodex_blake_anthropic_receipt: /Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/tmp/blake-output-ap00012-c1.txt.receipt.json

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  | R17 | [1/3] | ⚪ | The draft 2020-12 `"type":"integer"` accepts `1.0`, so `attempt: 1.0` passes the schema. The oracle's `range(1, highest + 1)` would then likely raise TypeError instead of returning a defect. The wire test covers 1.5 but not 1.0. | tests/autopilot/test_contract_semantics.py:160 | 3 | BOB |

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  The high resource-edge gap blocks convergence at cycle1/cap3. Existing schema suffices; additive source-anchored dependency rows and tests need no new dependency, external interface or foundational data-model decision. Original completed tasks stay completed. Queue fresh D1 follow-ups through review-close, preserving every prior implementation attempt and the model audit snapshot.

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00020-changelog-skill-presence-check-v1-review-2.md
  `01a077ec-1aa8-7ef1-96ba-8ed4aab0f82a`)

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00058-page-links-accept-javascript-urls-v1-review-1.md
  Fact-Forcing Gate (`gateguard`) — `error=Command blocked by PreToolUse hook:

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00111-braid-state-misses-link-removals-v1-review-2.md
  1, "You have exceeded your monthly quota". Retried once per retry policy, same

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00093-cut-build-phase-clerical-overhead-v1-review-1.md
  [BOB] 🟡 Completed tasks are counted as transition calls rather than distinct task IDs, so duplicate completion updates deflate the ratio | File: .claude/skills/work/scripts/check_build_overhead.py:88 | Task: 7

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00171-route-sonnet-prompt-through-stdin-v1-review-1.md
  `CODEX_SESSION_ID` is what the build phase worked around when it ran

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00176-guard-the-target-reads-in-the-doctor-v1-review-02.md
  ## Follow-up work

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00176-guard-the-target-reads-in-the-doctor-v1-review-03.md
  ```

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00183-make-batch-report-decisions-and-implementor-mix-render-v1-review-2.md
  # Review: 00183-make-batch-report-decisions-and-implementor-mix-render-v1

## Task prose

- No active autopilot batch: `autopilot/state.json` is absent, `prds/wip/` and `prds/backlog/` do not exist, `hold/` is empty. Last batch 202610261200 (00108) drained; its one deferred VERIFY is resolved (210e674c) and its test follow-ups closed 2026-10-29: `test_moves_every_well_formed_receipt_in_place` covers every receipt shape, pinned or not, including the two `future = false` receipts 00105 used to skip.
- Last shipped work: sysup shell-line steps (PR #253, merged 2026-10-28), released as gems-v0.16.0 on 2026-10-29 (tag pushed, publish run in flight at catchup time).
- #252 (timeout orphaning from that PR's review) fixed 2026-10-29 for captured steps; the interactive residual is recorded in the invariants.
- Backup intake 00107 was specced on 2026-10-29 into five sequenced backlog PRDs: 00107 per-instance excludes, 00109 bundle `items` + skip outcomes + replace-after-complete, 00110 `--plan` + once-per-run output resolution, 00111 `--jobs` + cancellation, 00112 progress + `--quiet

---
catchup: skip
design: run
default_model: opus
model_tier_rationale: concurrency, cancellation and subprocess lifecycle decide correctness
---

# backup: bounded parallel jobs with clean cancellation

Source: `docs/dev/project-management/intake/processed/00107-backup-multi-source-parallel/discovery.md` (Q7, Q10, Q11). Depends on PRD 00110 (duplicate-output rejection, run-wide `now`). PRD 00112 depends on this one.

## Overview

### Problem Statement
`Runner.run` loops over instances one after another (`src/tools/backup/runner.py:31`). A run of many large trees takes the sum of all archive times. The system-tar writer blocks in `subprocess.run` (`src/tools/backup/capabilities/tar_archive.py:340`), so a Ctrl-C cannot stop the child cleanly, and nothing cancels a writer that is mid-archive.

### Target Users
The solo operator who runs many instances unattended and sometimes interrupts a run.

### Success Metrics
- `uv run pytest tests/tools/backup/test_parallel_runner.py -q` passes.
