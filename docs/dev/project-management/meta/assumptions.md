# PRD 00161 assumptions

## 1: Python set_default_id derives the id from the UTC digits of date

- Tess: the year-rollover and same-wall-clock-other-instant cases are in scope as Devon-proof constraints on the UTC rule.
- Tess: "restoring afterwards" for the TZ switch means `monkeypatch.undo()` then `time.tzset()` inside the test.
- Tess (strengthen): `test_raises_on_invalid_date` stays unchanged; weak points 3 and 4 went into a new sibling test `test_invalid_date_keeps_metadata_and_sets_no_id`.
- Tess (strengthen): "other metadata keys are kept" on the invalid-date path means the metadata dict is left exactly as it was.
- Tess (strengthen): `zoneinfo` resolves `Europe/Prague` from system tzdata; CI runs on Linux and macOS only.
- Ivan: a datetime is aware when `tzinfo is not None`; a tzinfo whose `utcoffset()` returns None goes through `astimezone` and is read as local time. No test covers it.

## 2: Python _get_date_from_file parses file-name digits as UTC, seconds 60-99 as 59

- Tess: `FileMetadataReader` methods are called on the class with the file path as the only argument.
- Tess: "an eastern zone" is `Asia/Kolkata` (+05:30); an invalid 12-digit stem falls back like a 14-digit one.
- Tess: added `test_invalid_file_name_date_falls_back_to_earliest_file_date` to pin the unchanged fallback.
- Tess (strengthen): `20240115146022` is an invalid minute, so it must fall back, not clamp.
- Ivan: the seconds rule applies only to 14-digit names; the requested comment is wrapped over 2 lines for the 120-char lint limit.

## 3: Rust core mirrors UTC ids and UTC file-name dates; bump CACHE_VERSION

- Tess: a 12-digit stem gives seconds `00`; for a 60-99 suffix the default id comes from the clamped date (`...59`), not the raw digits.
- Tess: a stem of 12 ASCII digits followed by a fullwidth digit is left untested.
- Tess: chrono `Local` reads the `TZ` variable the Python parity test sets.
- Tess (strengthen): an impossible calendar value (Feb 30, month 13, hour 25) gives `None`; an explicit `id: null` counts as missing.
- Ivan: none.

## 4: CreateZettelUseCase allocates suffixed ids 60-99 without sleeping

- Tess: the hook runner runs even when `template.hooks()` is empty; `prepare` creates no file at the chosen path.
- Tess: a short id `12345` passes through the zettel factory unchanged, so it serves as the non-14-digit case.
- Tess (strengthen): `test_create_never_sleeps` asserts the 40-suffix exhaustion call takes under 0.3 s; this assumes CI filesystems are fast enough (Pat flagged it as a possible flake).
- Tess (strengthen): vault confinement is checked through a slug template's `folder`.
- Ivan: `zettel.id` is not reassigned when the base path is chosen; after exhaustion it is left at the last suffix (the call raises).
- Ivan: `_build` is a module-level helper returning a `Zettel`, and candidate paths come from a lazy generator `_candidate_paths`, not the design's `_build(...) -> tuple[Zettel, list[Path]]`. Behavior matches the contract.

## 5: Docs state the UTC id rule and the 60-99 collision suffix

- Ivan: the SKILL.md bullet is three short sentences with the 2-space hanging indent of its neighbours; README writes "seconds 60 to 99" without code ticks.

## 6: CHANGELOG entry for UTC ids

- Orchestrator: the `### Changed` line landed in task 1's `fix` commit (953e13a0) and was extended in task 2 (f0e11fd8), because the CHANGELOG rule requires the entry in the first user-visible commit. Task 6 only verified it; no new commit.

## Step 7: final verification

- Orchestrator: `tests/lib/zettel/infrastructure/test_markdown_parser.py::test_from_file_sets_date_and_title` pinned the old local-time file-name date; the PRD did not name it. Its expectation now reads UTC (task 2, attempt 2). It is a spec change, not a relaxed test.
- Orchestrator: the 10 `tests/tools/dot/test_pull_divergence_two_hosts.py` setup errors come from global `commit.gpgsign=true` and the locked signing agent in the sandbox (`git commit` exits 128 in the fixture). No `dot` file changed in this PRD.
