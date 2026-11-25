# Decision Audit Log: 00136-sysup-plan-config-errors-raw-v1

PRD: `00136-sysup-plan-config-errors-raw-v1.md`
Started: 2026-11-13T20:25:27Z
Completed: 2026-11-13T20:25:27Z
Autonomous: 10  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-11-13T20:25:27Z

**Decision**: The load-time exception handlers omit `ConfigurationError`, so that exception from `load_yaml` escapes instead of becoming a file-qualified `FatalError`. Add it to both handlers and cover this error path.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-13T20:25:27Z

**Decision**: ConfigurationError from load_yaml is not caught and converted to FatalError

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-13T20:25:27Z

**Decision**: ConfigurationError from load_yaml is not caught and converted to FatalError

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-13T20:25:27Z

**Decision**: `load_config` lets `ConfigurationError` escape for a non-mapping YAML root; the docstring claim "never a raw traceback" is still false and `src/tools/sysup/cli.py:175` catches only `FatalError`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-13T20:25:27Z

**Decision**: Source tracking misattributes inherited errors when two files modify the same mapping entry. For example, an invalid `commands.custom.order` in `config.yaml` is blamed on `buvis-sysup.yaml` when that file only changes `commands.custom.steps`. Track sources by nested field path in both loaders.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-13T20:25:27Z

**Decision**: Error attribution is last-writer-wins per top-level key and per `commands.<name>` / `expiry.<name>` entry. If two layers each set different fields of the same entry, the error names the later file.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-13T20:25:27Z

**Decision**: R1, R2, R5, R8: single-voice medium findings (missing load-failure test, cross-tool duplication, ntfy test binding, set-union hoist)

**Choice**: discard

**Rationale**: single-voice (one reviewer each); recorded in the settled-decisions ledger so a re-raise is auto-dismissed

### [autonomous] 2026-11-13T20:25:27Z

**Decision**: R9, R10, R13: single-voice low findings (characterization tests, _load_default wrapping, sysup/backup wording asymmetries)

**Choice**: discard

**Rationale**: single-voice (one reviewer each); recorded in the settled-decisions ledger

### [autonomous] 2026-11-13T20:25:27Z

**Decision**: R4/R6/R7/R11: ConfigurationError from load_yaml escapes the new _merge_layer handlers in both sysup and backup

**Choice**: tail sweep (task 4/5)

**Rationale**: raised by three reviewers; cycle converged with no critical or high, so it is swept as a normal fix task rather than a new review cycle

### [autonomous] 2026-11-13T20:25:27Z

**Decision**: R3/R12: config error source attribution is last-writer-wins per top-level key or entry, so it can name the wrong file

**Choice**: tail sweep (task 4/5)

**Rationale**: raised by two reviewers; swept as a normal fix task on the converged cycle
