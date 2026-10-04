# Retire the pidash tool from buvis-gems

<!-- design; migrated from PRD 00071 flat file -->

## Implementation

### Module: pidash removal
- **Location**: `src/tools/pidash/`, `tests/tools/pidash/`, `docs/source/tools/pidash.rst`, `pyproject.toml`, `CHANGELOG.md`
- **Responsibility**: delete the tool and every wiring point that references it.
- **Exports**: none — this is a removal.

### Dependencies

- `pidash removal`: no dependencies (nothing in gems imports pidash; the
  cross-tool isolation invariant guarantees it).

## Notes

- Supersedes gems PRDs `00049-pidash-hook-durability-v1` and
  `00059-pidash-state-schema-contract-v1` (both parked in
  `dev/local/prds/hold/`). Their obligations do not transfer: the hooks they
  hardened no longer exist, and `statectl.py` in the buvis home repo already
  provides atomic, advisory-locked state writes.
- `00069-postup-autopilot-data-layer-v1` was parked to `hold/` in the 2026-08-07
  backlog review for the same reason: tracon and `statectl.py` already own the
  autopilot data layer and dashboard, so gems does not rebuild them.
- postup keeps the portfolio-brief function (00063-00068, 00072). This PRD
  retires only the autopilot-dashboard tool.
