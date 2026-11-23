# bim ids: read a naive `date` in a configured zone (Prague rule)

Status: new. Recorded 2026-11-23. Owner decision, relayed by the session
`feature-bim-utc-ids-ef` (which ran the 2026-11-17 backlog review that removed
this rule from PRD 00161). Owner's words: "lets add Prague rule through that
session currently building 00161".

Routing (decided 2026-11-23 in the 00161 build session): 00161 finalizes on its
current scope first. This item then becomes PRD 00165 and runs the full gate
(design, plan, work, review) on branch `feature/bim-utc-ids`. Number 00164 is
taken by `intake/new/00164-bim-tx-utc-ids/idea.md` (commit cea75f91, branch
`feature/merge-klyreon-to-bim`).

## Requirement

A `date` without an offset is the wall clock of the zone in the bim setting
`id_naive_timezone` (default `Europe/Prague`, DST-aware). The default id of
such a note is the UTC digits of that instant. The Python path and the Rust
path give the same id.

## Fixed contract points

1. `BimSettings.id_naive_timezone: str = "Europe/Prague"` (env
   `BUVIS_BIM_ID_NAIVE_TIMEZONE`). An unknown IANA name fails settings
   validation with a message that names the value.
2. "Naive" means all three forms the Rust parser accepts today:
   `YYYY-MM-DD HH:MM:SS`, date only `YYYY-MM-DD` (midnight in the zone), and
   the truncated `YYYY-MM-DDT`.
3. DST: for a repeated local time take the first occurrence (Python
   `fold=0`). For a local time that does not exist, use the offset in force
   before the gap (what `zoneinfo` gives with `fold=0`). Rust must give the
   same instants; chrono-tz returns `Ambiguous` and `None` for these two
   cases, so it needs explicit handling. No error and no skip in either case.
4. The library does not import bim settings (AGENTS.md invariant "The library
   stays interface-agnostic"). bim passes the value in once, from its
   composition root.
5. Aware dates do not change: the UTC rule of PRD 00161 stays.

## Facts verified by the relaying session (HEAD 8ae17032)

- `src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_id.py:26-30`:
  a naive date keeps its digits. The fixer is called as `fixer(zettel_data)`
  through the consistency service, so an argument alone does not carry a
  setting.
- `src/rust/src/types.rs:103-122`: the three naive branches label the value
  UTC with `from_utc_datetime(&chrono::Utc, ..)`. No context argument.
- `src/rust/src/lib.rs:13-17`: the core exposes only `parse_file`,
  `load_all`, `load_filtered`, `search`, `refresh_cache`. No configuration
  channel into Rust.
- Python calls the core only in
  `infrastructure/persistence/markdown_zettel_repository/markdown_zettel_repository.py:20`,
  with `from_rust=True`, which skips the Python fixers. The Rust path is the
  one users see.
- `src/rust/Cargo.toml` has `chrono` only. A fixed IANA zone needs
  `chrono-tz` (new dependency, Cargo.lock changes, the crate must download in
  the build environment).
- `src/rust/src/scanner.rs`: cached metadata is made after parsing. A cache
  made under one zone must not be served under another, so the zone must be
  part of the cache validity (not only a version bump).
- `src/tools/bim/settings.py`: `BimSettings` forbids unknown keys, so the
  field must exist before any config names it.

## Suggested design (open to change)

One process-wide naive zone: a setter in the Rust core exposed to Python, a
matching value on the Python side for `set_default_id`, default
`Europe/Prague` when never set, settable more than once so tests can change
it. bim sets it once where it resolves settings.

## Intended side effect

Through Rust the instant of a naive `date` itself moves (14:53 naive was read
as 14:53 UTC, now 14:53 Prague). When bim saves such a note, the formatter
(`markdown_zettel_formatter/helpers.py:50`) writes the correct instant with an
offset. This stops the wrong-offset damage that PRD 00162 lists under Risks.
Say so in the CHANGELOG line.

## Tests to write (suggested names)

`naive_date_read_in_configured_zone`, `naive_date_only_is_midnight_in_zone`,
`naive_dst_overlap_takes_first_occurrence`, `naive_dst_gap_uses_offset_before_gap`,
`rust_python_naive_id_parity`, `id_naive_timezone_setting_reaches_core`,
`unknown_zone_name_is_refused`, `cache_not_reused_after_zone_change`.
Replace `test_naive_date_keeps_its_digits` (it pins the removed behavior).
Edge case: naive `2026-11-17 08:37:39` gives id `20261117073739` with Prague.

## Docs

Add the setting to the settings table and the env-var list in
`docs/source/tools/bim.rst`, and correct the naive-date sentences there.

## Carried from the PRD 00161 cycle-1 review (single-voice, verified, same files)

See `docs/dev/project-management/reviews/00161-bim-utc-ids-v1-ledger.json`.

- R6: no Python/Rust parity test for a naive `date`. Covered by
  `rust_python_naive_id_parity` above.
- R7: `zettel_file_parser.py:67` compares the seconds suffix as text
  (`digits[12:] >= "60"`); the 00161 contract says `int(digits[12:]) >= 60`.
  Fullwidth digits below 60 are read as 59. Fix and add a regression test.
- R8: `test_create_zettel_use_case.py` does not pin two design safeguards: a
  `None` base id must avoid the `Zettel.id` setter, and an unused suffix path
  that is a symlink outside the vault must not reject a free base. Add
  prepare/execute cases for both. Mind the 800-line limit (file is at 796).

## Not in scope

PRD 00162 does not change: its `--naive-timezone` default is the same zone
and it imports nothing from bim.
