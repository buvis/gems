# Discovery: bim naive dates read in a configured zone (Prague rule)

## Classification

Depth: comprehensive | Date: 2026-11-24

Source: `idea.md` beside this file.

Comprehensive because the change crosses the Rust core (parser, cache, new
setter, new crate), the Python parser, fixer, formatter and query renderer, the
bim settings and composition root, and the docs. Clarity of the input was high,
so only three questions were needed.

## Problem

A front-matter datetime without an offset (`date: 2026-11-17 08:37:39`) is the
owner's Prague wall clock, but the Rust core labels it UTC
(`src/rust/src/types.rs:103-122`) and the Python fixer keeps its digits
(`set_default_id.py:26-30`). So the default id is off by one or two hours, and
when bim saves such a note the formatter writes the wrong instant with an
offset, which makes the error permanent. PRD 00161 removed the Prague rule from
its scope on 2026-11-17; the owner put it back on 2026-11-23 as its own PRD on
branch `feature/bim-utc-ids`. PRD 00162 (id migration) lists the wrong-offset
damage under Risks; this PRD stops it at the source.

## Requirements

### Must have

1. **Setting.** `BimSettings.id_naive_timezone: str = "Europe/Prague"` (env
   `BUVIS_BIM_ID_NAIVE_TIMEZONE`). An unknown IANA name fails settings
   validation with a message that names the value.
2. **Naive forms.** All three forms the Rust parser accepts are naive:
   `YYYY-MM-DD HH:MM:SS`, `YYYY-MM-DD` (midnight in the zone), and
   `YYYY-MM-DDT` (midnight in the zone).
3. **Every key.** The zone applies to every naive datetime value in front
   matter, not only `date` (Q1). Aware values keep their instant (the PRD 00161
   UTC id rule stays).
4. **DST.** A repeated local time takes the first occurrence (Python `fold=0`).
   A local time inside a gap takes the offset in force before the gap (what
   `zoneinfo` gives with `fold=0`). Rust handles chrono-tz `Ambiguous` and
   `None` explicitly to give the same instants. No error, no skip.
5. **Rust channel (Q2).** The core exposes `set_naive_timezone(name)`. It can be
   called more than once, defaults to `Europe/Prague` when never called, and
   raises `ValueError` naming the value for a zone it does not know. bim calls
   it once in the `cli` group callback (`src/tools/bim/cli.py:41`). The
   background refresh child (`query_presentation.py:207`) calls it with the same
   name before `refresh_cache`.
6. **Python side (Q3).** One library-level setter holds the same zone for
   Python and forwards it to the core when the core is present, so bim makes one
   call. The pure-Python parser turns all three naive forms into aware
   datetimes in the zone at parse time. `set_default_id` and the formatter
   (`markdown_zettel_formatter/helpers.py:50`) read any naive value still in
   memory in the zone, never the machine zone.
7. **Rendering (Q1).** Query columns convert datetimes to the configured zone
   before `strftime` (`query_zettels_use_case.py:237-238`), so
   `deadline: 2026-12-01` shows `2026-12-01`. `bim serve` emits datetimes in the
   configured zone (`commands/serve/_routes.py:80-93`), per the all-interface
   rule.
8. **Cache.** The zone is part of cache validity in `src/rust/src/scanner.rs`:
   the cache records the zone it was built under, and a load under another zone
   rebuilds cold. Bump `CACHE_VERSION` (now 5) because the format changes.
9. **Parity.** For each naive form and both DST edges, the Rust path and the
   pure-Python path give the same instant and the same default id.
10. **Layering.** The library never imports bim settings (AGENTS.md invariant
    "The library stays interface-agnostic").
11. **Carried from the 00161 review** (ledger
    `reviews/00161-bim-utc-ids-v1-ledger.json`):
    - R6: covered by requirement 9.
    - R7: `zettel_file_parser.py:67` compares the seconds suffix as text; use
      `int(digits[12:]) >= 60`. Regression test with fullwidth digits.
    - R8: `test_create_zettel_use_case.py` pins two safeguards: a `None` base id
      avoids the `Zettel.id` setter, and an unused suffix path that is a symlink
      outside the vault does not reject a free base. The file is at 796 lines,
      so the new cases go in a new test file.
12. **Docs and changelog.** Add the setting to the settings table and env-var
    list in `docs/source/tools/bim.rst` and correct its naive-date sentences.
    The CHANGELOG `Fixed` line names the visible effects: naive dates read as
    Prague (configurable), ids of such notes change, queries show local time.

### Nice to have

- A test that a zone unknown to chrono-tz but known to `zoneinfo` gives a clear
  bim error, not a stack trace (tzdb versions can differ).

### Out of scope

- PRD 00162 (id migration): its `--naive-timezone` default is the same zone and
  it imports nothing from bim.
- Rewriting naive dates on disk in bulk. Only notes bim saves for another reason
  gain an offset.
- Loop-log migration dates (`migration/project.rs:104`,
  `migrate_loop_log.py:78`), which use the machine zone for a different format.
- Other gems tools that use the zettel library get the `Europe/Prague` default
  and no setting.

## Constraints

- New Rust crate `chrono-tz` (Cargo.toml, Cargo.lock). It must download in the
  sandbox and CI build. The sandbox needs `CARGO_HOME` in the scratchpad.
- The rebuilt `_core` `.so` must be re-signed on macOS (`codesign -f -s -`).
- `BimSettings` has `extra="forbid"`, so the field must ship before any config
  names it.
- Python 3.11+ floor: `zoneinfo` is stdlib.
- 800-line file limit (R8 test file).

## Codebase Context

- **Relevant code**:
  - Rust naive parsing: `src/rust/src/types.rs:103-122`.
  - Rust exports: `src/rust/src/lib.rs:13-17`; stub `src/lib/buvis/pybase/zettel/_core.pyi`.
  - Rust to Python handoff converts to UTC: `src/rust/src/pybridge.rs:37`.
  - Cache: `src/rust/src/scanner.rs:112-144` (version byte, rmp body).
  - Python id fixer: `domain/entities/zettel/fixers/set_default_id.py`.
  - Python parser and YAML loader: `infrastructure/persistence/file_parsers/zettel_file_parser.py`,
    `parsers/markdown/helpers.py:17-59` (`_ZettelSafeLoader`).
  - Formatter: `infrastructure/formatting/markdown_zettel_formatter/helpers.py:50`.
  - Query render: `application/use_cases/query_zettels_use_case.py:237-238`.
  - Serve render: `src/tools/bim/commands/serve/_routes.py:80-93`.
  - Settings: `src/tools/bim/settings.py`; resolved once by
    `@buvis_options(settings_class=BimSettings)` on the `cli` group
    (`src/tools/bim/cli.py:39-42`), which is the composition root for CLI,
    TUI and serve.
  - Refresh child: `src/tools/bim/shared/query_presentation.py:199-212`.
- **Conventions**: Rust and Python parity tests compare instants, not wall
  clocks (`pybridge.rs` hands UTC). Tests are class-based and named for the
  rule. Lazy imports in CLI handlers.
- **Integration points**: the `cli` group body (now `pass`), the refresh child
  script string, `get_repo` in `src/tools/bim/dependencies.py` (unchanged with
  the setter approach).
- **Similar implementations**: `src/rust/src/consistency/defaults.rs:37` and
  `parser/enrichment.rs:29` already format ids from UTC instants; the new code
  only changes how a naive value becomes an instant.

## Approach

- **Chosen**: one process-wide zone. A library setter stores a `ZoneInfo` for
  Python and calls the core setter, which stores a `chrono_tz::Tz`. Both
  parsers make naive values aware at parse time. Renderers convert to the zone.
  The cache stores the zone name next to the version byte.
- **Why**: one call from bim's composition root reaches every path. No core
  signature changes. The fixer is called as `fixer(zettel_data)`, so it cannot
  take an argument without a global anyway.
- **Rejected alternatives**:
  - Zone argument on every core function: five signatures and all callers
    change, and the Python fixer still needs a global, so two styles result.
  - Core reads `BUVIS_BIM_ID_NAIVE_TIMEZONE` from the environment: breaks the
    interface-agnostic invariant and misses values set in the config file.
  - Zone only for the `date` key: Rust parses values without their key, and one
    text form would get two meanings in one file.

## Success Criteria

- Naive `2026-11-17 08:37:39` with Prague gives id `20261117073739` on the Rust
  path and the Python path.
- Naive `2026-07-01 08:00:00` (summer) gives `20260701060000`.
- `deadline: 2026-12-01` shows `2026-12-01` in `bim query` and in serve output.
- DST overlap `2026-10-25 02:30:00` gives `20261025003000` (first occurrence,
  +02:00). DST gap `2026-03-29 02:30:00` gives `20260329013000` (offset before
  the gap, +01:00). Both paths agree.
- Changing the zone between two `load_filtered` calls on the same cache gives
  results in the new zone.
- `BUVIS_BIM_ID_NAIVE_TIMEZONE=Mars/Base bim query ...` fails with a message
  that names `Mars/Base`.
- Suggested test names from `idea.md` all exist and pass;
  `test_naive_date_keeps_its_digits` is replaced.

## Risks

- **tzdb skew**: Python `zoneinfo` uses system tzdata, chrono-tz embeds its
  own. A name may pass the settings validator and fail the core setter. The bim
  callback must catch the core `ValueError` and panic through the console.
- **Visible id change**: notes with naive dates and no stored `id` get new
  default ids. Notes with a stored `id` are not affected. Call it out in the
  CHANGELOG.
- **Visible render change**: query and serve show local time for aware dates
  too (they showed UTC). This is the intended fix (Q1) but users will notice.
- **Missed child process**: a future subprocess that loads notes without the
  setter uses the default zone. The cache zone check limits the damage to that
  process.
- **Test state leak**: the global zone must be reset between tests (an autouse
  fixture), or test order changes results.

## Open Questions

- Should the WebUI frontend change, or does it only print the ISO string from
  serve? Not checked in this pass; the design step should read
  `bim/commands/serve/frontend/` for date slicing.
- Where exactly the Python setter lives (for example
  `buvis.pybase.zettel` package level or a small `naive_zone` module) is a
  design choice for `/autopilot:design-solution`.

## Discovery Log

### Q1: Scope of the zone rule (every naive datetime value, or only `date`) and query rendering
**Answer**: All keys + local render. The zone applies to every naive datetime
value in front matter. Query formatting converts to the configured zone before
`strftime`, so `deadline: 2026-12-01` still shows 2026-12-01, and aware dates
also show local time instead of UTC.

### Q2: How the zone reaches the Rust core, given the `refresh_cache` child process
**Answer**: Setter + child sets it. One process-wide `set_naive_timezone(name)`
in the core, called once from the bim `cli` group callback. The background
refresh child script (`query_presentation.py:207`) calls it too before
`refresh_cache`.

### Q3: Where the Python side applies the zone
**Answer**: Parse time, like Rust. The pure-Python parser turns all three naive
forms into aware datetimes in the zone. `set_default_id` and the formatter use
the same zone for any naive value still in memory.

### Inferred without asking
- Problem, priority and routing: given in `idea.md` (owner decision
  2026-11-23, full gate on `feature/bim-utc-ids` after 00161).
- Decomposition: the owner bundled R7 and R8 into this item; kept as one PRD.
- Cache invalidation: zone name stored in the cache header plus a version bump
  (requirement 8 of `idea.md` already rules out a bump alone).
- Serve output follows Q1 under the all-interface rule.
- Success-criteria instants: computed from Europe/Prague rules (CET +01:00,
  CEST +02:00, 2026 transitions on 29 March and 25 October).
