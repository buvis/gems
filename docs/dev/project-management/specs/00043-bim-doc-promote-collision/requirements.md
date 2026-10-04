# bim doc promote: stop overwriting on canonical-name collision

<!-- requirements; migrated from PRD 00043 flat file -->

## Problem

`bim doc promote` permanently destroys an existing archived document when a second one resolves to the same canonical filename. `_finalize` builds `target_pdf = business_root / issuer.slug / canonical_filename` with no existence check (`src/tools/bim/commands/doc/promote/promote.py:218`) and then `source_pdf.replace(plan.target_pdf)` (`:256`), which overwrites unconditionally; the zettel side overwrites too. Promote's zk timestamp is always `YYYYMMDD000000` (`promote.py:339-340`), so time never disambiguates. Two triaged docs with the same issuer + doc date + number/title slug (e.g. two "statement" PDFs) collide, and promoting the second silently deletes the first PDF and its zettel. The ingest path already solves this with a seconds-increment resolver (`shared/pipeline.py:722-758`); promote just skips it.

## Solution

Before `_finalize` moves the PDF / writes the zettel, run the same collision resolution ingest uses: if the target path exists, increment the zk timestamp's seconds field (bounded, then fail loud) until the name is free. Reuse the existing resolver rather than reimplementing it.

## Requirements

### Must have
- Promote calls the shared seconds-increment collision resolver before finalizing; on a taken canonical name it advances to the next free one.
- If resolution exhausts its bound (same cap ingest uses), promote returns `CommandResult(success=False, error=...)` — never overwrites.
- Regression test: two proposals resolving to the same canonical filename → both survive on disk after promoting both (second lands at the incremented name); assert file count and that the first file's bytes are unchanged.

### Nice to have
- Factor the resolver so ingest and promote share one function (if it is currently private to the pipeline).

## Success Criteria

- Promoting a document whose canonical name is already taken never deletes the incumbent.
- bim doc tests green; behavior matches ingest's collision handling.
