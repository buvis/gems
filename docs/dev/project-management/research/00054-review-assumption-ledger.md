# Assumption ledger — PRD 00054, review cycle 1 rework

## 7: Surface PATCH/open failures in ItemPanel, LinkWidget and MarkdownEditor

- (Gemini) `handleSectionSave`/`handleFieldChange` re-throwing so parent callers learn of the failure is intended. **Orchestrator overrode this**: `handleFieldChange`'s re-throw had no consumer (`PropertyField` calls `onchange` fire-and-forget), so it recreated the unhandled-rejection half of the finding. The re-throw was dropped there and kept only on `handleSectionSave`, whose consumer (`MarkdownEditor.save`) now catches it.
- (Gemini) LinkWidget's inline error text renders directly in the span and may wrap if the reason string is long.

## 9: Route EditNoteApp._save through notify_result

- (Tess) `EditNoteApp` exposes the same widget ids as `EditScreen` (`#edit-title`, `#save-btn`) — confirmed by the pre-existing `test_form_renders_fields`.
- (Tess) Used `run_test(size=(100, 50))` for the click-driven tests, matching the size the existing `TestEditScreen` save tests use, rather than the `(80, 30)` used by `EditNoteApp`'s non-clicking tests.
- (Tess) `bim.dependencies.get_repo` needs mocking for `EditNoteApp` save tests too, inferred from the sibling `TestEditScreen` save tests.
- (Tess) Covered exactly the three pinned behaviors; did not add an `EditNoteApp` equivalent of `TestEditScreen`'s fourth test (warning-with-no-output skips the information call).
- (Ivan) none.

## 10: Real-repository PATCH route test

- (Ivan) Reused the pre-existing `minimal_zettel` fixture from `tests/tools/bim/conftest.py` rather than inventing a new one.
- (Ivan) The section-target test targets the heading the parser actually synthesizes (`# Original Title`) rather than the literal `## Content` heading in the source markdown — the parser does not preserve that heading as a section key. Verified empirically against the real repo; existing parser behavior, not introduced by this PRD. **Worth a look**: this is a latent surprise for anyone writing section-targeted PATCH calls.
- (Ivan) Placed the new tests immediately after the existing mocked PATCH tests to keep them grouped.

## 11: Split test_serve.py and parametrize the action matrix

- (Ivan) Centralized only the `client` fixture into `conftest.py`; kept `query_spec` and its stub dataclasses local to `test_serve_queries.py`, the single file that uses them. Verified empirically that this repo's pytest config (`--import-mode=importlib`, no `tests/__init__.py`) does not support cross-module conftest imports, so centralizing single-consumer stubs would have required a fabricated indirection fixture.
- (Ivan) Deleted `test_serve.py` outright once every class migrated, rather than leaving an empty stub.
- (Ivan) Flagged that the orchestrator's stated `1284` baseline was wrong. **Confirmed and corrected**: `1284` was a line count of a collect-only output file, not a test count. True baseline is 1276, and the refactor is exactly test-count-neutral (72 → 72 for the split files).

## 6 and 8

No assumptions recorded (task 6 was a fully-specified CHANGELOG edit; task 8's implementor reported two, both about defensive coercion of a FastAPI `detail` value and using `'success' in body` as the envelope discriminator — both are in the committed code and were reviewed).

---

# Assumption ledger — PRD 00054, review cycle 2 tail sweep

## 12: Sweep cycle-2 medium findings (one PATCH code path, unwrapEnvelope res.ok, LinkWidget aria-live)

- (Tess) `POST /api/actions/patch`'s `file_path` accepts an absolute filesystem path string, resolved through the same `confine_path`/`app_state` as the route's URL path segment — inferred from `handle_patch`'s own `confine_path(file_path, app_state)` call and the existing route tests' use of absolute `tmp_path` paths.
- (Tess) "Same persisted result" is asserted as byte-identical file content between two independently-patched copies of the same starting note, rather than by comparing the two JSON response envelopes — the envelopes carry different `output`/`metadata` strings tied to their file paths, so file-content equality is the meaningful invariant.
- (Tess) Did not read `tests/tools/bim/test_serve_actions.py` (outside her listed scope) to check for overlapping `patch`-action coverage. **Orchestrator verified**: that file does carry `test_patch_action_success_returns_200` and `test_patch_action_failure_returns_422`, but neither is a parity test — they exercise the action alone. Tess's two tests remain the only assertion that the route and the action agree, so nothing is duplicated.
- (Ivan) Took the smaller-diff refactor the architecture context offered — the route delegates to the existing `handle_patch` — rather than extracting a third shared helper, since `_actions.py` needed no change either way. Consequence worth knowing: `confine_path` now runs twice on a PATCH request (once in the route's 404 guard, once inside `handle_patch`). It is a pure resolve-and-check with no side effects, so this is a redundant call, not a behavior change.

