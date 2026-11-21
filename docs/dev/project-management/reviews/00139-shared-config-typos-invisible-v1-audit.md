# Decision Audit Log: 00139-shared-config-typos-invisible-v1

PRD: `00139-shared-config-typos-invisible-v1.md`
Started: 2026-11-14T02:28:30Z
Completed: 2026-11-14T02:28:30Z
Autonomous: 16  |  Deferred: 4  |  Doubts: 0

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: cross-tool shared config-key check (PRD 00139 design)

**Choice**: entry-point registry (buvis.config_settings group) discovers every tools settings keys via importlib.metadata, unioned for a warn-only never-raise check on config.yaml/buvis.yaml typos

**Rationale**: library must not import tool code; entry points converge to the real installed tool set without hardcoding, unlike decorator self-registration (only sees the current tool) or a hand-maintained list (drifts)

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: R1 [3/4] 🟠 shared-file warn branch flags valid global fields when known_keys is None (resolve(GlobalSettings))

**Choice**: fix in cycle-1 rework

**Rationale**: Confirmed by two independent reviewer probes; resolve(GlobalSettings) is a documented public API path. Fix is bounded: pass an own_fields set computed unconditionally from settings_class.model_fields | config_deferred_keys and use it for is_own_field, leaving the raising branch's known_keys gate untouched.

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: R2 [3/4] 🟡 _load_yaml is 60 lines and 5 levels deep after the change

**Choice**: fix in cycle-1 rework

**Rationale**: Clear mechanical, behavior-preserving extraction into a helper; three reviewers agree and the mechanical-facts block confirms the line count.

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: R3 [2/4] 🟡 test_registry.py leaks monkeypatched names in the process-wide lru_cache

**Choice**: fix in cycle-1 rework

**Rationale**: Mechanical: autouse fixture clearing known_tool_names.cache_clear() on setup and teardown. The design's Risks section already names this leak.

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: R4 [2/4] 🟡 no test pins the real buvis.config_settings entry-point wiring (R7 is the same defect in Carl's wording)

**Choice**: fix in cycle-1 rework; R7 retired as duplicate

**Rationale**: Additive test only. The design mandated an integration test over real entry points and it was not written; registry drift is the PRD's own main risk.

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: R5, R6, R7, R8, R9, R10 single-voice or duplicate rows

**Choice**: discarded, recorded in the settled-decisions ledger

**Rationale**: R5 single-voice (its coverage lands with the R1 regression tests); R6 single-voice and partly mitigated by R4's drift test; R7 duplicate of R4; R8 single-voice, an accepted design follow-on; R9 single-voice and Alice's own row calls it acceptable; R10 is a positive all-clear, not a defect.

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: Valid global fields `debug` and `log_level` produce the unknown-key warning when the caller resolves plain `GlobalSettings`. `resolve()` sets `known_keys` to None whenever `tool_name` is None (the default `BUVIS_` prefix), and the shared-file branch then treats every key that isn't a tool name as unknown. The spec requires no warning for a global field. Exact contract for the fix: in `resolve()` (resolver.py:290-294) compute an `own_fields` set UNCONDITIONALLY as `set(settings_class.model_fields) | set(getattr(settings_class, 'config_deferred_keys', ()))`, independent of the existing `tool_name is not None and extra == 'forbid'` gate; pass it to `_load_yaml` as a NEW keyword argument beside `known_keys`; use `own_fields` (not `known_keys`) for `is_own_field` in the `path.name in {'config.yaml','buvis.yaml'}` branch at resolver.py:207. Leave `known_keys` and the `elif known_keys is not None` raising branch at resolver.py:217-220 byte-for-byte unchanged, so custom-file rejection keeps today's behavior. Regression tests required: (a) resolving `GlobalSettings` against a `config.yaml` holding `debug: true` and `log_level: DEBUG` emits NO warning; (b) resolving `GlobalSettings` against a `config.yaml` holding `srouces: x` still warns, naming file and key; (c) the existing custom-file `ConfigurationError` test still passes.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: `ConfigResolver._load_yaml` grows to 60 lines, over the project's 50-line limit, and the new shared-file check sits 5 levels deep (for, try, if, for, if). Extract the `config.yaml`/`buvis.yaml` branch into a module-level or static helper such as `_warn_unknown_shared_keys(layer, path, own_fields)` and hoist the `known_tool_names()` call out of the per-key loop. Behavior must not change: same warning text, same one warning per unknown key, same `_split_directive` base-name handling.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: `test_registry.py` leaves monkeypatched names in the process-wide `lru_cache` of `known_tool_names()`. `test_result_is_cached_until_cleared` ends with the cache holding `{"delta"}`, and the other tests end holding their fakes, so later tests in the same pytest process that resolve against `config.yaml`/`buvis.yaml` see a bogus registry and emit spurious warnings. Add an autouse fixture in this module that calls `known_tool_names.cache_clear()` both before and after each test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: No test asserts the real `buvis.config_settings` entry-point wiring; the design's "Integration (real entry points, no monkeypatching)" bullet was not implemented. Add a test that calls `known_tool_names()` with NO monkeypatching and asserts it matches the declared tool set (the `buvis.config_settings` names in `pyproject.toml`, or equivalently the `src/tools/*` package names), so a missing or misspelled registration among the 18 fails in CI. Clear the cache around it so it does not see another test's fake.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: R3 (cycle 2): registry stores no per-tool key sets, so the check is narrower than the success metric

**Choice**: settled deferral (same as cycle 1 R11)

**Rationale**: the approved design settles shared files as carrying a <tool>: namespace section per tool; per-tool field sets would make the library import tool code, against the AGENTS.md invariant the PRD restates

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: R4 (cycle 2): Task 5's mandated GlobalSettings regression tests are absent (Bob's wording)

**Choice**: discard

**Rationale**: duplicate of R1, which carries the same fix with three finders; the defect itself is deferred as a cap-overflow, not dismissed

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: R5 (cycle 2): known_tool_names() now runs even when no shared file is loaded

**Choice**: discard

**Rationale**: single-voice; known_tool_names() is lru_cached so the metadata scan happens at most once per process, and the hoist that caused it was the cycle-1 R2 fix the panel asked for

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: R6 (cycle 2): per-test known_tool_names.cache_clear() calls are now redundant with the autouse fixture

**Choice**: discard

**Rationale**: single-voice; a redundant cache_clear in a test is harmless and the raiser calls it redundant, not wrong

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: R7 (cycle 2): the gate run reports 10 failures out of 7702 tests

**Choice**: discard

**Rationale**: verified not a defect of this PRD: all 10 are collection ERRORs in tests/tools/dot/test_pull_divergence_two_hosts.py from this host's commit.gpgsign=true needing interactive approval, pre-existing and already a deferred decision

### [autonomous] 2026-11-14T02:28:30Z

**Decision**: R8 (cycle 2): the CHANGELOG entry describes a narrower guarantee than the PRD's success metric

**Choice**: discard

**Rationale**: not a defect; the row is a positive all-clear and the narrowness it notes is the settled R11/R3 deferral

### [deferred] 2026-11-14T02:28:30Z

**Decision**: R11: shared-file unknown-key check does not know other tools settings fields; top-level sources: warns when sysup resolves config.yaml

**Choice**: deferred to batch end

**Rationale**: requirements ambiguity: PRD Success Metric 1 says any tools settings field, the approved design settles it as <tool>: namespace sections; per-tool field sets would make the library import tool code

### [deferred] 2026-11-14T02:28:30Z

**Decision**: The check knows only the resolving tool's own fields and the registered tool names, not "any tool's settings field" as Success Metric 1 words it. A top-level `sources:` (a braid field) warns when sysup resolves `config.yaml`. The approved design settles this the other way (shared files carry `<tool>:` namespace sections), and per-tool field sets would make the library import tool code against the AGENTS.md invariant, so the reading needs a human call.

**Choice**: deferred

**Rationale**: deferred by review-close

### [deferred] 2026-11-14T02:28:30Z

**Decision**: R1 (cycle 2): the GlobalSettings false-positive fix in resolver.py is not pinned by any test. No shared-file test resolves GlobalSettings, so reverting the _own_fields change would leave the suite green. Needed: a test that resolve(GlobalSettings) against a config.yaml carrying debug/log_level emits no warning, and one that GlobalSettings against srouces still warns with file and key.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-11-14T02:28:30Z

**Decision**: R2 (cycle 2): resolve() hands the own-field set to _warn_unknown_shared_keys through mutable instance state (self._own_fields) instead of the keyword argument on _load_yaml the task contract specified, so _load_yaml now depends on resolve() having run first. Fix: compute own_fields as a local in resolve(), add own_fields to _load_yaml as a keyword parameter, drop the instance attribute.

**Rationale**: rework cap reached with this finding unresolved
