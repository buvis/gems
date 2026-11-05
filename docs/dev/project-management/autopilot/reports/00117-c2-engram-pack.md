Portfolio freshness: NOT refreshed this cycle (PRD 00002 pending)

71 changed symbol(s) omitted (beyond the 40-symbol cap).

## Similar code

- gems:/Users/bob/git/src/github.com/buvis/gems/src/rust/src/consistency/fixers.rs:233-240
      fn test_fix_lists_bullets() {
        let mut data = ZettelData::new();
        data.sections.push(("# T".to_string(), "* item1\n* item2\n- item3".to_string()));
        fix_lists_bullets(&mut data);
        assert!(data.sections[0].1.contains("- item1"));
        assert!(data.sections[0].1.contains("- item2"));
        assert!(data.sections[0].1.contains("- item3"));
    }

- gems:/Users/bob/git/src/github.com/buvis/gems/src/rust/src/consistency/fixers.rs:84-103
  pub fn fix_lists_bullets(data: &mut ZettelData) {
    data.sections = data
        .sections
        .iter()
        .map(|(heading, content)| {
            let fixed: String = content
                .lines()
                .map(|line| {
                    if line.starts_with("* ") {
                        format!("- {}", line[2..].trim())
                    } else {
                        line.trim().to_string()
                    }
                })
                .collect::<Vec<_>>()
                .join("\n");
            (heading.clone(), fixed)
        })
        .collect();
}

- gems:/Users/bob/git/src/github.com/buvis/gems/src/lib/buvis/pybase/zettel/infrastructure/persistence/file_parsers/parsers/markdown/back_matter_preprocessor.py:15-22
      def fix_obsidian_dataview_keys(text: str) -> str:
        dataview_key_pattern = r"^(\S+)::"

        def replace(match: re.Match[str]) -> str:
            return match.group(1) + ":"

        corrected_lines = [re.sub(dataview_key_pattern, replace, line, count=1) for line in text.split("\n")]
        return "\n".join(corrected_lines)

- gems:/Users/bob/git/src/github.com/buvis/gems/src/rust/src/parser/back_matter.rs:39-50
  fn fix_dataview_keys(text: &str) -> String {
    text.lines()
        .map(|line| {
            DATAVIEW_KEY_RE
                .replace(line, |caps: &regex::Captures| {
                    format!("{}:", caps.get(1).unwrap().as_str())
                })
                .to_string()
        })
        .collect::<Vec<_>>()
        .join("\n")
}

- gems:/Users/bob/git/src/github.com/buvis/gems/src/tools/backup/capabilities/tar_archive.py:380-397
  def _normalize_items(source: Path, items: object) -> list[Path]:
    """Validate literal item paths and remove duplicate selected subtrees."""
    if not isinstance(items, (list, tuple)) or not all(isinstance(item, str) for item in items):
        raise ValueError("items must be a list of relative paths")
    if not items:
        raise ValueError("items must not be empty")
    selected: list[Path] = []
    for item in items:
        relative = Path(os.path.normpath(item))
        if not item or relative.is_absolute() or relative == Path(".") or relative.parts[0] == "..":
            raise ValueError(f"invalid item '{item}': must be a relative path inside the source")
        for parent in reversed(relative.parents):
            if parent != Path(".") and (source / parent).is_symlink():
                raise ValueError(f"item '{item}' passes through symlink '{parent.as_posix()}'")
        if relative not in selected and not any(parent in selected for parent in relative.parents):
            selected = [path for path in selected if relative not in path.parents]
            selected.append(relative)
    return selected

- gems:/Users/bob/git/src/github.com/buvis/gems/src/tools/backup/cli.py:24-34
  def _format_progress(event: ProgressEvent, elapsed: float) -> str:
    percentage = ""
    if (
        event.done_bytes is not None
        and event.total_bytes is not None
        and event.total_bytes > 0
        and event.phase != "finalizing"
    ):
        percentage = f" [{min(99, event.done_bytes * 100 // event.total_bytes)}%]"
    minutes, seconds = divmod(max(0, int(elapsed)), 60)
    return f"{event.label} {event.phase}{percentage} {minutes}:{seconds:02d}"

- gems:/Users/bob/git/src/github.com/buvis/gems/src/tools/dot/tui/widgets/diff_view.py:47-57
          def __init__(
            self,
            *,
            hunk: Hunk,
            line_select_mode: bool,
            selected_line_indices: frozenset[int],
        ) -> None:
            super().__init__()
            self.hunk = hunk
            self.line_select_mode = line_select_mode
            self.selected_line_indices = selected_line_indices

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

- ddb:/Users/bob/git/src/github.com/doogat/ddb/ddb-core/src/types/schema.rs:256-304
  impl fmt::Display for Fix {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Fix::TagsDeduped { removed } => write!(f, "deduplicated tags: {}", removed.join(", ")),
            Fix::TagsSorted => write!(f, "sorted tags"),
            Fix::TagsStrippedHash { tags } => {
                write!(f, "stripped # from tags: {}", tags.join(", "))
            }
            Fix::DefaultSet { field, value } => write!(f, "set default {field}: {value}"),
            Fix::TitleDerived { source } => match source {
                TitleSource::FirstH1(h) => write!(f, "derived title from H1: {h}"),
                TitleSource::Filename(n) => write!(f, "derived title from filename: {n}"),
            },
            Fix::KeyNormalized { old, new } => write!(f, "normalized key {old} -> {new}"),
            Fix::TitleTrimmed => write!(f, "trimmed title"),
            Fix::TitleCapitalized => write!(f, "capitalized title"),
            Fix::H1Aligned { old_h1, new_h1 } => {
                write!(f, "aligned H1: {old_h1} -> {new_h1}")
            }
            Fix::CrossZoneResolved { key, kept_zone } => {
                write!(
                    f,
                    "resolved cross-zone duplicate: {key} (kept {kept_zone:?})"
                )
            }
            Fix::FieldRenamed { old, new } => write!(f, "renamed field {old} -> {new}"),
            Fix::TypeNormalized { old, new } => write!(f, "normalized type {old} -> {new}"),
            Fix::ManualTypedef { type_name } => write!(
                f,
                "manual typedef '{type_name}' — consider recreating with: ddb query \"CREATE TABLE {type_name} (...)\""
            ),
            Fix::TitleNonCompliant { expected } => {
                write!(f, "title does not match template (expected: {expected})")
            }
            Fix::ZoneMigrated { column, from, to } => {
                write!(f, "migrated column '{column}' from {from:?} to {to:?}")
            }
            Fix::SingletonConflictResolved {
                table,
                winner,
                losers,
            } => write!(
                f,
                "resolved singleton conflict in {table}: kept {winner}, quarantined {}",
                losers.join(", ")
            ),
        }
    }
}

## Findings precedent

- findings:/Users/bob/git/src/github.com/buvis/gems/dev/local/reviews/00046-dot-tui-secret-status-refresh-v1-review-01.md
  FIX:

- findings:/Users/bob/git/src/github.com/buvis/gems/dev/local/reviews/00046-dot-tui-secret-status-refresh-v1-review-02.md
  FIX:

- findings:/Users/bob/git/src/github.com/buvis/gems/dev/local/reviews/00042-bim-serve-confinement-and-auth-v1-review-01.md
  FIX:

- findings:/Users/bob/git/src/github.com/buvis/gems/dev/local/reviews/00042-bim-serve-confinement-and-auth-v1-review-02.md
  FIX:

- findings:/Users/bob/git/src/github.com/buvis/gems/dev/local/reviews/00043-bim-doc-promote-collision-v1-review-01.md
  FIX:

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00010-split-long-validator-functions-review-01.md
  ### Outcome (2026-11-01)

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  # Review: 00012-autopilot-package-contract-v1

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  | R2 | [1/3] | 🟠 | resource_closure leaves out many runtime script dependencies. `resource_edges` has 202 rows, yet packaged skills call scripts that are neither packaged nor declared external: `consolidate_findings.py` (plugins/autopilot/skills/run-autopilot/references/lane-solo.md:168, plugins/autopilot/skills/review-work-completion/SKILL.md:386), `compute_mech_facts.py` (plugins/autopilot/skills/fast-track/SKILL.md:270), and also `render_prompt.py`/`record_dispatch.py` in fast-track, `detect_tautological_tests.py`, `check_review_file.py`, `await_reviewer_outputs.py`, `fast_track_plan.py`, `card.py`, `fablectl.py` and `parse_review.py`. The test locks the edge count and digest (tests/autopilot/test_package.py:331), so it cannot catch the gap. The unconditional skill gates block runtime harm today, but later PRDs that restore entry points will inherit this incomplete map | tools/autopilot/source-map.json | Phase 1 task 2 | BLAKE |

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  | R17 | [1/3] | ⚪ | The draft 2020-12 `"type":"integer"` accepts `1.0`, so `attempt: 1.0` passes the schema. The oracle's `range(1, highest + 1)` would then likely raise TypeError instead of returning a defect. The wire test covers 1.5 but not 1.0. | tests/autopilot/test_contract_semantics.py:160 | 3 | BOB |

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-02.md
  autocodex_blake_anthropic_receipt: /Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/tmp/blake-output-ap00012-c2.txt.receipt.json

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00007-extract-memory-candidates-from-transcripts-v1-review-2.md
  ## Cycle-1 rework verification

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00017-malformed-memory-half-written-v1-review-2.md
  | [1/4] | 🟡 | FIX: `target.is_file()` can itself raise `OSError` for an inaccessible parent before `_readable_bytes()` runs, and the handler still catches only `WriteError`/`KeyError`; catch that probe failure and add a regression asserting exit 1 with both files untouched. | skills/distil-memory/scripts/write.py:169 | 5 | BOB |

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00020-changelog-skill-presence-check-v1-review-2.md
  `01a077ec-1aa8-7ef1-96ba-8ed4aab0f82a`)

## Task prose

### Batch 202610292344
- [x] 00111-backup-parallel-jobs-and-cancellation-v1.md (1 cycle)
- [x] 00112-backup-live-progress-and-quiet-v1.md (1 cycle)
- [x] 00107-backup-per-instance-excludes-v1.md (1 cycle, recovered 2026-11-02)
- [x] 00109-backup-bundle-items-and-skip-outcomes-v1.md (2 cycles, recovered 2026-11-02)
- [x] 00110-backup-plan-preview-and-output-resolution-v1.md (3 cycles at cap 2, recovered 2026-11-02)

Observations: Batch drained; all held PRDs passed completion review on `fix/backup-batch-202610292344` (unpushed). Full isolated suite at `93781cd0`: 6417 passed, 16 skipped; Python 3.14 backup suite 802 passed. Open: hold stub 00117 (bundle `out` under source rejected by the containment guard; needs a PRD decision); GNU tar/gzip descendant cleanup deferred for Linux verification; ledgered follow-up candidate: uniform, labelled access-error framing in tar-archive run/plan. `autopilot review-once` cannot run while headless `claude -p` reports a revoked OAuth token. Evidence: 

---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: one validation function gains an item-scoped branch; tests and docs follow existing patterns in the same files
---

# backup: allow a bundle `out` under `source` when it lies outside every selected item

Source: hold stub 00117, promoted 2026-11-02 from the deferred finding of batch `202610292344` (ledger `docs/dev/project-management/autopilot/deferred/202610292344-deferred.json`, HIGH, raised against 00109 cycle 1). Depends on nothing open: 00109 and 00110 are done.

## Overview

### Problem Statement
`_reject_out_inside_source` in `src/tools/backup/capabilities/tar_archive.py` refuses any `out` whose resolved path equals or lies under the resolved `source`. Both `TarArchive.run` and `_plan_source` call it before `items` is considered. The guard exists so a whole-tree archive never re-archives its own previous output. A bundle archives only its selected items, so the 00109 headline case is refused although th
