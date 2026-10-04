# fctracker: validate CSV order and handle bad/overdraft rows

<!-- tasks; migrated from PRD 00048 flat file -->

## Tasks

### Phase 0: Core
- [ ] Add the date-monotonicity assertion after reversal in the reader; surface via the command as a failed `CommandResult` — Acceptance: mis-ordered CSV → clear error, no wrong numbers.
- [ ] Catch overdraft/zero-amount/malformed-cell in `commands/transactions` → `CommandResult(success=False, ...)` — Acceptance: each error class returns a friendly message; tests cover all three.
