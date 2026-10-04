# bim doc: move source-file link from body to `file-path` frontmatter

Date: 2026-05-11
Status: approved (brainstorming)
Owner: tomas@buvis.net

## Problem

`bim doc ingest` and `bim doc promote` write zettels whose body contains a
hard-coded `[Open PDF](file://...)` link directly under the H1. Two things
are wrong with that:

1. **PDF-specific.** The link text says "Open PDF" even though the ingest
   pipeline will eventually accept other file types (images, plain-text,
   email exports, etc.).
2. **Body noise.** The source-file URL is metadata about the document, not
   prose about it. Anything machine-readable belongs in frontmatter; the
   body should be free for the H1, the LLM summary, and the OCR callout.

## Goal

Move the source-file link out of the body and into the existing `file-path`
frontmatter key, with file-type-agnostic link text. The value becomes a
Markdown link string `"[Open file](file://...)"`, double-quoted in YAML.
The body loses its `[Open PDF]` line entirely.

## Out of scope

- Migration of zettels already filed in Bob's vault. Confirmed unneeded;
  no programmatic consumers depend on `file-path`'s shape today.
- Renaming the `file-path` key. The name still describes the field's
  purpose; only the shape of its value changes.
- Other frontmatter fields, the OCR callout, the canonical filename, the
  per-issuer subfolder layout, or any other body section. All unchanged.
- PRDs. `dev/local/prds/backlog/` and `dev/local/prds/wip/` are empty;
  `done/` is off-limits per `rules/working-documents.md`.

## Design

### New shape

YAML frontmatter (only the `file-path` line changes; key order is
unchanged):

```yaml
ingest-source: email
file-path: "[Open file](file:///Users/bob/Library/Mobile%20Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf)"
file-sha256: 3f4a8c2b91e7d5a6b1c2d3e4f5061728394a5b6c7d8e9f0a1b2c3d4e5f607182
```

Body (the `[Open PDF]` line and the blank line that followed it are gone):

```markdown
# ČEZ a.s. invoice 7102105594

Vyúčtování za elektřinu za období 1.1.2021 – 28.2.2021. Splatnost 25.3.2021.

## OCR text

> [!quote]- Full text
> <full OCR text>
```

When no summary is produced, the body collapses to H1 + blank + `## OCR
text` directly (same rule as today; no extra blank line).

### URL encoding

Unchanged from current behaviour: `urllib.parse.quote(file_path,
safe="/~")`. Spaces become `%20`; forward slashes and tildes stay literal.

### Link text

Exactly `Open file`. File-type-agnostic on purpose.

### YAML scalar style

The value MUST be emitted double-quoted (`"..."`), not single-quoted nor
plain. Rationale: the value contains `[`, `]`, `(`, `)`. PyYAML's
auto-quoting would pick single quotes by default; the user wants double.

This is the only field that needs a forced style. Implementation:

```python
class _DoubleQuoted(str):
    """Marker subclass: serialise as a double-quoted YAML scalar."""

def _double_quoted_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')

yaml.SafeDumper.add_representer(_DoubleQuoted, _double_quoted_representer)
```

In `_serialize_frontmatter`, after `model_dump(by_alias=True, mode="python")`,
wrap `payload["file-path"]` in `_DoubleQuoted(link_string)` where
`link_string` is `f"[Open file](file://{quoted_path})"`.

### Pydantic model

`DocumentZettelFrontmatter.file_path: str` keeps storing the **raw absolute
path** as today. The existing validator (`_file_path_is_absolute_no_tilde`)
is unchanged: it still rejects relative paths and bare `~` segments. Other
code that consumes `frontmatter.file_path` programmatically
(`ZettelWriter._derive_basename`, `pipeline_helpers.build_filing_frontmatter`,
`build_promote_frontmatter`) keeps receiving a plain path string.

The Markdown-link wrapping happens **only at YAML serialisation time** in
`_serialize_frontmatter`. The in-memory model stays semantic.

### Body builder

In `build_zettel_body`:

- Drop the `file_url = "file://" + urllib.parse.quote(...)` line.
- Drop the `urllib` import (no other use in the file; verify before
  removing).
- Drop `f"[Open PDF]({file_url})"` and the blank line after it from the
  initial `lines` list.
- Adjust the docstring (`"v1 layout: ..."`) to reflect the new shape.

After: `lines` starts as `[f"# {frontmatter.title}", ""]`, then the optional
summary block, then `"## OCR text"`, then the OCR callout. The current
"blank before `## OCR text`" rule still holds because the summary block
already appends a trailing `""`, and when summary is `None` the H1's
trailing `""` plays that role. Re-check this when writing the test fixtures.

## Touched files

| File | Change |
|---|---|
| `src/tools/bim/commands/doc/shared/zettel_writer.py` | Add `_DoubleQuoted` + representer; wrap `file-path` in `_serialize_frontmatter`; strip link emission and `file_url`/`urllib` from `build_zettel_body`; update docstrings. |
| `tests/tools/bim/doc/test_zettel_writer.py` | Rename / rewrite link assertion (see below); update YAML format test; update summary present/absent assertions; drop body-link tests. |
| `tests/tools/bim/doc/fixtures/zettel_writer/num{0\|1}_amt{0\|1}_lang{0\|1}.md` (8 files) | Regenerate. |
| `dev/local/specs/bim-doc-architecture.md` §5 | Update YAML example, `file-path` field rule, body template, body rules. |
| `docs/source/tools/bim.rst` | Update "Zettel v1 shape" prose + code block + "Reserved frontmatter keys" entry. |
| `CHANGELOG.md` | Add entry under `[Unreleased] → Changed`. |

## Test plan

Existing tests in `tests/tools/bim/doc/test_zettel_writer.py` to update:

1. `test_open_pdf_link_uses_file_url` → rename to
   `test_file_path_yaml_value_is_open_file_link`. Reads the written file,
   parses YAML, then asserts:
   - The raw frontmatter text contains `file-path: "[Open file](file://`
     (double-quoted, link text exact).
   - The parsed YAML value matches `^\[Open file\]\(file://.+\)$`.
   - The URL inside, after `urllib.parse.unquote`, round-trips to the
     absolute path that the model was constructed with.
   - Spaces in the input path appear as `%20` in the URL; tildes stay
     literal.
2. `test_yaml_writes_file_path_as_absolute`: assert the absolute path
   appears inside the link substring (not as a bare scalar). The two
   sanity checks ("starts with `/`", "does not start with `~`") run
   against the path extracted from the link, not the YAML value as a
   whole.
3. `test_yaml_top_level_key_order_matches_spec_section_5`: unchanged
   (key order is preserved).
4. `test_summary_paragraph_present_when_provided`: assert the summary
   sits directly under the H1 (one blank line between H1 and summary;
   no link line in between).
5. `test_summary_paragraph_omitted_when_none`: assert H1 is followed by
   `## OCR text` after a single blank line, with no link line.
6. `test_h1_is_title`, `test_ocr_callout_present`: unchanged.

Any other test that grep matches `Open PDF` or `[Open PDF]` is dropped.

Fixture regeneration is mechanical: run the writer against the fixture
inputs (the test helpers in `test_zettel_writer.py` already build the
frontmatter from `_frontmatter_kwargs`), diff the output, replace the
expected `.md` files. Verify visually that exactly two diffs landed per
file: `file-path` line shape and body link removal.

No new tests beyond the rewrites above. The change is a format swap; the
test surface stays the same size.

## Documentation updates (verbatim plan)

### `dev/local/specs/bim-doc-architecture.md` §5

- In the YAML example (currently line 318), replace:
  ```
  file-path: /Users/bob/Library/Mobile Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf
  ```
  with:
  ```
  file-path: "[Open file](file:///Users/bob/Library/Mobile%20Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf)"
  ```
- Rewrite the `file-path` bullet under "Field rules" (line 340):

  > `file-path` is a **double-quoted Markdown link** of the form
  > `"[Open file](file://<encoded-absolute-path>)"`. The path inside the
  > URL is absolute (no `~/`), URL-encoded with `urllib.parse.quote(p,
  > safe="/~")` (spaces become `%20`, tildes stay literal). Link text is
  > `Open file` rather than `Open PDF` so the same shape works when the
  > pipeline later ingests non-PDF documents. Obsidian renders the link
  > clickable from the Properties pane.

- In the "Zettel body template" code block (lines 354–364), remove the
  `[Open PDF](file://{{ file-path-url-encoded }})` line and the blank
  line after it.
- Replace the "PDF link uses an absolute, URL-encoded `file://` URL ..."
  bullet (lines 369–373) with a single bullet:

  > The body no longer carries the source-file link. The clickable
  > `file://` URL lives in the `file-path` frontmatter value (see
  > "Field rules" above).

### `docs/source/tools/bim.rst`

- In the intro paragraph at lines 287–291, replace "absolute ``file://``
  link in the body" with "absolute ``file://`` link in the ``file-path``
  frontmatter".
- In the code block, change the `file-path:` line to the double-quoted
  `"[Open file](...)"` form, and remove the `[Open PDF](...)` body line
  with its surrounding blank line.
- Replace the "Reserved frontmatter keys" `file-path` entry
  (lines 339–340):

  > - ``file-path``: a double-quoted Markdown link of the form
  >   ``"[Open file](file://<encoded-absolute-path>)"``. Path is
  >   absolute (no ``~`` segment), URL-encodes spaces as ``%20``, keeps
  >   tildes literal. Link text is ``Open file`` (file-type-agnostic).

### `CHANGELOG.md`

Under `[Unreleased] → Changed`:

```
- **bim**: doc-ingest zettels embed the source-file link in `file-path` frontmatter as `"[Open file](file://...)"` instead of an `[Open PDF]` link in the body (file-type-agnostic)
```

## Risks and mitigations

- **YAML scalar style regressions.** Registering a custom representer on
  `yaml.SafeDumper` affects every `yaml.safe_dump` call in this process.
  Mitigation: the representer keys on the `_DoubleQuoted` subclass only;
  plain `str` values are untouched. Verified by re-running the existing
  YAML order test (it checks every other key).
- **`urllib` import dead after removal from `build_zettel_body`.** If the
  module has no other `urllib` reference, remove the import; if some
  test or helper still uses it, leave it. Verify with a single ripgrep
  before committing.
- **Obsidian rendering of Markdown links in YAML.** Obsidian's
  Properties pane renders text-type properties as raw text by default.
  The user confirmed this is the desired shape and has presumably
  verified rendering in their vault. No mitigation needed in code.
- **Fixture drift across the 8 variants.** Each fixture must change in
  exactly the same two places. Mitigate by regenerating all 8 in one
  pass and diffing the patch for unexpected changes.

## Open questions

None. All decisions were resolved during brainstorming:

1. Link text is `Open file` (confirmed).
2. Value is the Markdown-link string stored in the existing `file-path`
   key, not a new key (confirmed from user wording).
3. YAML scalar style is double-quoted (confirmed).
4. No migration of existing zettels (confirmed).
