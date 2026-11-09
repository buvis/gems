# Task 2 per-task review

## Initial

MEDIUM | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:73 | `reservation = os.fstat(descriptor)` runs after `os.open` but before the `try/finally`. If `fstat` raises, or a `KeyboardInterrupt` lands there, the descriptor stays open and the zero-byte placeholder stays on disk. Nothing cleans either up, and no test covers this window. The contract requires `finally` cleanup for any exit before save succeeds. | Open the `try` immediately after `os.open` and call `fstat` inside it. Initialise `reservation = None` first, and have the `finally` close the descriptor if it is still open and unlink only when `reservation` is set and its `(st_dev, st_ino)` matches. Add a test where `os.fstat` raises.

MEDIUM | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:46 | The no-sections case builds the heading from `data.metadata['title']`. The contract says `answers.get('title', '')`. If the template metadata has no `title`, this raises `KeyError`. If a template derives the metadata title differently from the answer, the heading differs from the contract. The test `test_initializes_missing_sections_with_answer_title` passes only because `FreshTemplate` sets the metadata title to the answer title. | Use `f"# {answers.get('title', '')}"`. Add a test where the metadata title differs from or is absent beside `answers["title"]`.

LOW | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:76 | `try: os.close(d) except BaseException: os.close(d); raise` closes twice. If the interrupt arrives after the first close completed, the second close raises `EBADF` and masks the `KeyboardInterrupt`. It could also close an unrelated descriptor that reused the number. | Track an `open` flag and close once in the `finally`, which makes this nested try unnecessary.

LOW | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:84 | The `path.exists()` then `path.stat()` pair in `finally` can race. A concurrent removal raises `FileNotFoundError` there and masks the original exception. | Wrap `stat` and `unlink` in `try/except FileNotFoundError`, or use `os.stat` once without `exists()`.

LOW | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:40 | The body normalization and section merge are inline in the `_prepare` retry loop, so `_prepare` mixes retry control with text handling. | Extract a pure `_merge_body(data, template, body)` helper with unchanged behavior.


## Delta

LOW | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:40 | Unresolved, carried forward: the body normalization and section merge are still inline in the `_prepare` retry loop, so `_prepare` mixes retry control with text handling. | Extract a pure `_merge_body(data, template, body)` helper with unchanged behavior.

LOW | tests/lib/zettel/application/test_create_zettel_use_case.py:316 | `test_body_survives_preparation_when_template_omits_title_metadata` checks only `sections[0][1]`, not the heading. A regression to a metadata-derived heading, for example `data.metadata.get('title', '')`, would still pass, because the answer title ("Answer Title") differs from the absent metadata title and nothing asserts the heading. | Assert `data.sections[0][0] == "# Answer Title"`.
