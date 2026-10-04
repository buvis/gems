# bim doc: `file-path` Markdown-link frontmatter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the source-file link from the zettel body into the existing `file-path` YAML frontmatter key, formatted as a double-quoted Markdown link `"[Open file](file://...)"`, and drop the body's `[Open PDF](...)` line.

**Architecture:** Internal Pydantic `DocumentZettelFrontmatter.file_path` keeps storing a raw absolute path (validator unchanged, all current callers unaffected). The Markdown-link wrapping happens only at YAML serialisation time in `_serialize_frontmatter`, via a `_DoubleQuoted(str)` marker class and a custom PyYAML representer that forces `style='"'`. The body builder loses its link emission.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, pytest, hatch/uv.

**Spec:** `dev/local/specs/2026-05-11-bim-doc-file-path-link-design.md`

---

## Pre-flight

The working tree has uncommitted modifications (`CHANGELOG.md`, `docs/source/tools/bim.rst`, `src/tools/bim/commands/doc/shared/settings_models.py`, two doc test files) from a previous session. Two of those files overlap with files this plan modifies.

- [ ] **Step 0: Surface pre-existing changes**

Run: `git status --short`

If the output is non-empty, stop and ask the user how to proceed (commit, stash, or discard) before continuing. **Do not** silently merge new work onto a dirty tree; CHANGELOG and `bim.rst` edits could collide.

Only proceed once the tree is clean (or the user has explicitly opted in to building on top of the pending edits).

---

## File map

**Modify:**
- `src/tools/bim/commands/doc/shared/zettel_writer.py`: add `_DoubleQuoted` + representer (module scope); rewrite `_serialize_frontmatter`; trim `build_zettel_body`; drop `urllib.parse` import (verify last use).
- `tests/tools/bim/doc/test_zettel_writer.py`: rewrite the body-link test; update summary-present / summary-absent assertions; tighten the absolute-path YAML test to inspect the link substring.
- `dev/bin/gen_zettel_writer_fixtures.py`: no code change. It re-imports the writer, so re-running it produces the new shape.
- `tests/tools/bim/doc/fixtures/zettel_writer/num{0|1}_amt{0|1}_lang{0|1}.md`: 8 files, regenerated mechanically.
- `docs/source/tools/bim.rst`: "Zettel v1 shape" code block + intro paragraph + "Reserved frontmatter keys" entry for `file-path`.
- `dev/local/specs/bim-doc-architecture.md`: §5 YAML example, `file-path` field rule, body template, body rules. (Gitignored; no commit.)
- `CHANGELOG.md`: `[Unreleased] → Changed` entry.

**No new files. No file deletions.**

---

## Task 1: Rewrite the affected unit tests (TDD red)

**Files:**
- Modify: `tests/tools/bim/doc/test_zettel_writer.py`

Concrete edits below. Apply them all in one pass; running pytest after this task is expected to fail, which validates that the tests are exercising the new behaviour.

- [ ] **Step 1: Replace the body-link test with the YAML-link test**

Find this block (around lines 219–229):

```python
def test_open_pdf_link_uses_file_url(self, frontmatter: DocumentZettelFrontmatter) -> None:
    body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
    match = re.search(r"\[Open PDF\]\((file://[^\)]+)\)", body)
    assert match is not None, "expected file:// link in body"
    url = match.group(1)
    assert url.startswith("file://")
    # Tildes stay literal; spaces are %20-encoded.
    assert "%20" in url
    # Round-trip back to the absolute path.
    decoded = urllib.parse.unquote(url[len("file://") :])
    assert decoded == SAMPLE_FILE_PATH
```

This test lives inside `class TestBuildZettelBody`. The new assertion is about the writer's YAML output, not the body, so the replacement test belongs in `class TestZettelWriter`. **Delete** the block above. **Then**, inside `class TestZettelWriter` (the absolute-path test at line 464 is a good neighbour), **add** this test:

```python
def test_file_path_yaml_value_is_open_file_link(
    self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter
) -> None:
    writer = ZettelWriter(
        repo=None,
        vault_root=tmp_path,
        vault_documents_subdir="Zettelkasten/documents",
    )
    body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
    target = writer.write(frontmatter, body, issuer_slug="cez-as")
    raw = target.read_text(encoding="utf-8")
    block = _frontmatter_block(raw)

    # 1. Raw YAML uses double-quoted style with the exact link prefix.
    assert 'file-path: "[Open file](file://' in block, block

    # 2. Parsed YAML value is a single-line Markdown link.
    value_line = block.split("file-path:", 1)[1].split("\n", 1)[0].strip()
    # Strip the surrounding double quotes that PyYAML emitted.
    assert value_line.startswith('"') and value_line.endswith('"'), value_line
    link = value_line[1:-1]
    match = re.match(r"^\[Open file\]\((file://[^\)]+)\)$", link)
    assert match is not None, link

    # 3. URL inside encodes spaces, keeps tildes literal, round-trips.
    url = match.group(1)
    assert "%20" in url
    assert "~" in url  # ``com~apple~CloudDocs`` literal
    decoded_path = urllib.parse.unquote(url[len("file://") :])
    assert decoded_path == SAMPLE_FILE_PATH

    # 4. Link line, not a body line. Body has no [Open PDF] / [Open file].
    body_only = raw.split("---", 2)[2]
    assert "[Open PDF]" not in body_only
    assert "[Open file]" not in body_only
```

- [ ] **Step 2: Tighten the existing `test_yaml_writes_file_path_as_absolute`**

Find the block (lines 464–480):

```python
def test_yaml_writes_file_path_as_absolute(self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter) -> None:
    writer = ZettelWriter(
        repo=None,
        vault_root=tmp_path,
        vault_documents_subdir="Zettelkasten/documents",
    )
    body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
    target = writer.write(frontmatter, body, issuer_slug="cez-as")
    block = _frontmatter_block(target.read_text(encoding="utf-8"))
    assert "file-path:" in block
    # The value starts with ``/`` (absolute), NOT ``~/`` (legacy form).
    # Embedded tildes inside path components (e.g. iCloud's
    # ``com~apple~CloudDocs``) are legitimate and not rejected.
    value_line = block.split("file-path:", 1)[1].split("\n", 1)[0].strip()
    assert value_line.startswith("/"), value_line
    assert not value_line.startswith("~"), value_line
    assert SAMPLE_FILE_PATH in block
```

Replace its body with:

```python
def test_yaml_writes_file_path_as_absolute(self, tmp_path: Path, frontmatter: DocumentZettelFrontmatter) -> None:
    writer = ZettelWriter(
        repo=None,
        vault_root=tmp_path,
        vault_documents_subdir="Zettelkasten/documents",
    )
    body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT)
    target = writer.write(frontmatter, body, issuer_slug="cez-as")
    block = _frontmatter_block(target.read_text(encoding="utf-8"))
    assert "file-path:" in block
    # Extract the URL inside the Markdown link, decode it, and verify the
    # underlying path is absolute (no ``~/`` legacy form). Embedded tildes
    # inside path components (e.g. iCloud's ``com~apple~CloudDocs``) are
    # legitimate and unencoded.
    value_line = block.split("file-path:", 1)[1].split("\n", 1)[0].strip()
    match = re.search(r"\(file://([^\)]+)\)", value_line)
    assert match is not None, value_line
    decoded_path = urllib.parse.unquote(match.group(1))
    assert decoded_path.startswith("/"), decoded_path
    assert not decoded_path.startswith("~"), decoded_path
    assert decoded_path == SAMPLE_FILE_PATH
```

- [ ] **Step 3: Update the summary-present assertion**

Find (lines 231–235):

```python
def test_summary_paragraph_present_when_provided(self, frontmatter: DocumentZettelFrontmatter) -> None:
    body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT, summary="A monthly electricity invoice.")
    assert "\nA monthly electricity invoice.\n" in body
    # Summary appears before the OCR section.
    assert body.index("A monthly electricity invoice.") < body.index("## OCR text")
```

Replace with:

```python
def test_summary_paragraph_present_when_provided(self, frontmatter: DocumentZettelFrontmatter) -> None:
    body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT, summary="A monthly electricity invoice.")
    # H1 then blank line then summary directly (no intervening link line).
    assert f"# {SAMPLE_TITLE}\n\nA monthly electricity invoice.\n" in body
    # Summary appears before the OCR section.
    assert body.index("A monthly electricity invoice.") < body.index("## OCR text")
```

- [ ] **Step 4: Update the summary-absent assertion**

Find (lines 237–241):

```python
def test_summary_paragraph_omitted_when_none(self, frontmatter: DocumentZettelFrontmatter) -> None:
    body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT, summary=None)
    # No double-blank-line gap where the summary would be.
    assert "\n\n\n## OCR text" not in body
    assert "## OCR text" in body
```

Replace with:

```python
def test_summary_paragraph_omitted_when_none(self, frontmatter: DocumentZettelFrontmatter) -> None:
    body = build_zettel_body(frontmatter, SAMPLE_OCR_TEXT, summary=None)
    # H1 is immediately followed (after a single blank line) by ``## OCR text``.
    assert f"# {SAMPLE_TITLE}\n\n## OCR text" in body
    # No double-blank-line gap where the summary would be.
    assert "\n\n\n## OCR text" not in body
```

- [ ] **Step 5: Run the tests and confirm they fail**

Run: `uv run pytest tests/tools/bim/doc/test_zettel_writer.py -v -k "file_path_yaml_value_is_open_file_link or yaml_writes_file_path_as_absolute or summary_paragraph_present or summary_paragraph_omitted_when_none"`

Expected: the four tests should fail. `test_file_path_yaml_value_is_open_file_link` fails because the current writer emits `file-path:` as a bare path, not a quoted Markdown link. `test_yaml_writes_file_path_as_absolute` fails on the `re.search(r"\(file://...\)")` line. The two summary tests fail on the new substring containing the H1 followed directly by content (the current body inserts the `[Open PDF]` line in between).

If they pass instead, stop. Something is wrong with the test edits.

- [ ] **Step 6: Do not commit yet**

The fixture-snapshot tests (`TestZettelWriterPerVariantFixtures`) are still passing right now because the writer hasn't changed. They will start failing after Task 2. Hold the commit until Task 4.

---

## Task 2: Implement the writer changes (TDD green)

**Files:**
- Modify: `src/tools/bim/commands/doc/shared/zettel_writer.py`

- [ ] **Step 1: Add `_DoubleQuoted` and the PyYAML representer at module scope**

Open `src/tools/bim/commands/doc/shared/zettel_writer.py`. After the imports and the existing module-level constants (`_ID_MIN`, `_ID_MAX`, `_EXTRACTION_METHOD_REGEX`, `IngestSource`) but before the `DocumentZettelFrontmatter` class (so near line 57), add:

```python
class _DoubleQuoted(str):
    """Marker subclass: serialise as a double-quoted YAML scalar.

    PyYAML's auto-quoter picks single quotes by default for strings that
    contain YAML flow indicators (``[``, ``]``, ``(``, ``)``). The
    ``file-path`` Markdown link must be emitted with double quotes for
    consistency with the documented v1 zettel shape. Wrapping the value
    in this subclass and registering a representer for it on
    ``yaml.SafeDumper`` forces ``style='"'`` exactly where we need it
    while leaving every other string at PyYAML's discretion.
    """


def _represent_double_quoted(dumper: yaml.SafeDumper, data: _DoubleQuoted) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')


yaml.SafeDumper.add_representer(_DoubleQuoted, _represent_double_quoted)
```

- [ ] **Step 2: Rewrite `_serialize_frontmatter` to wrap the `file-path` value**

Find (lines 253–267):

```python
@staticmethod
def _serialize_frontmatter(fm: DocumentZettelFrontmatter) -> str:
    payload = fm.model_dump(by_alias=True, mode="python")
    # Re-coerce doc-number from the string-or-None we store internally to
    # ``int`` when round-trippable, leaving leading-zero strings as YAML
    # strings (which PyYAML auto-quotes when ambiguous with numbers).
    if "doc-number" in payload:
        payload["doc-number"] = _coerce_doc_number(payload["doc-number"])
    return yaml.safe_dump(
        payload,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        default_style=None,
    )
```

Replace with:

```python
@staticmethod
def _serialize_frontmatter(fm: DocumentZettelFrontmatter) -> str:
    payload = fm.model_dump(by_alias=True, mode="python")
    # Re-coerce doc-number from the string-or-None we store internally to
    # ``int`` when round-trippable, leaving leading-zero strings as YAML
    # strings (which PyYAML auto-quotes when ambiguous with numbers).
    if "doc-number" in payload:
        payload["doc-number"] = _coerce_doc_number(payload["doc-number"])
    # Wrap ``file-path`` as a Markdown link so the source-file URL is
    # part of frontmatter (clickable from Obsidian's Properties pane)
    # instead of a body line. Link text is ``Open file`` so the same
    # shape works for non-PDF documents the pipeline will ingest later.
    if "file-path" in payload:
        raw_path = payload["file-path"]
        encoded = urllib.parse.quote(raw_path, safe="/~")
        payload["file-path"] = _DoubleQuoted(f"[Open file](file://{encoded})")
    return yaml.safe_dump(
        payload,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        default_style=None,
    )
```

- [ ] **Step 3: Trim `build_zettel_body`**

Find (lines 167–210):

```python
def build_zettel_body(
    frontmatter: DocumentZettelFrontmatter,
    ocr_text: str,
    summary: str | None = None,
    settings: ZettelSettings | None = None,
) -> str:
    """Compose the Markdown body (everything after the YAML frontmatter).

    v1 layout: ``# {title}``, blank, ``[Open PDF](file://...)``, blank,
    optional summary paragraph + blank, ``## OCR text``, blank, the existing
    Obsidian ``> [!quote]- Full text`` callout with each OCR line prefixed
    by ``> ``. When ``settings.ocr_text_max_chars`` is positive and the OCR
    text exceeds it, the text is truncated with a Unicode ellipsis appended
    before the callout is composed.
    """
    file_url = "file://" + urllib.parse.quote(frontmatter.file_path, safe="/~")

    lines: list[str] = [
        f"# {frontmatter.title}",
        "",
        f"[Open PDF]({file_url})",
        "",
    ]

    if summary:
        lines.append(summary)
        lines.append("")

    lines.extend(
        [
            "## OCR text",
            "",
            "> [!quote]- Full text",
        ]
    )

    text = ocr_text
    if settings is not None and settings.ocr_text_max_chars > 0 and len(text) > settings.ocr_text_max_chars:
        text = text[: settings.ocr_text_max_chars] + "…"

    for ocr_line in text.split("\n"):
        lines.append(f"> {ocr_line}")

    return "\n".join(lines) + "\n"
```

Replace with:

```python
def build_zettel_body(
    frontmatter: DocumentZettelFrontmatter,
    ocr_text: str,
    summary: str | None = None,
    settings: ZettelSettings | None = None,
) -> str:
    """Compose the Markdown body (everything after the YAML frontmatter).

    v1 layout: ``# {title}``, blank, optional summary paragraph + blank,
    ``## OCR text``, blank, the Obsidian ``> [!quote]- Full text`` callout
    with each OCR line prefixed by ``> ``. The source-file ``file://`` link
    is no longer in the body; it lives in the ``file-path`` frontmatter
    value as a ``[Open file](...)`` Markdown link. When
    ``settings.ocr_text_max_chars`` is positive and the OCR text exceeds
    it, the text is truncated with a Unicode ellipsis appended before the
    callout is composed.
    """
    lines: list[str] = [
        f"# {frontmatter.title}",
        "",
    ]

    if summary:
        lines.append(summary)
        lines.append("")

    lines.extend(
        [
            "## OCR text",
            "",
            "> [!quote]- Full text",
        ]
    )

    text = ocr_text
    if settings is not None and settings.ocr_text_max_chars > 0 and len(text) > settings.ocr_text_max_chars:
        text = text[: settings.ocr_text_max_chars] + "…"

    for ocr_line in text.split("\n"):
        lines.append(f"> {ocr_line}")

    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Verify the `urllib.parse` import is still used**

Run: `rg -n "urllib" src/tools/bim/commands/doc/shared/zettel_writer.py`

Expected: at least the `import urllib.parse` line plus the new `urllib.parse.quote(...)` call inside `_serialize_frontmatter`. If only the import line remains, remove it. (Don't expect this case; the new serializer uses it.)

- [ ] **Step 5: Run the four tests from Task 1; they must now pass**

Run: `uv run pytest tests/tools/bim/doc/test_zettel_writer.py -v -k "file_path_yaml_value_is_open_file_link or yaml_writes_file_path_as_absolute or summary_paragraph_present or summary_paragraph_omitted_when_none"`

Expected: all four pass.

- [ ] **Step 6: Run the full writer test file**

Run: `uv run pytest tests/tools/bim/doc/test_zettel_writer.py -v`

Expected: every test except the 8 `TestZettelWriterPerVariantFixtures::test_variant_fixture_matches_*` (or however they're parametrised) tests should pass. The 8 parametrised fixture-snapshot tests are expected to **fail** because the fixtures still encode the old body shape. Task 3 regenerates them.

If any **other** test fails, stop and investigate; the implementation has a side effect that wasn't captured in the design.

---

## Task 3: Regenerate the per-variant fixture snapshots

**Files:**
- Modify: `tests/tools/bim/doc/fixtures/zettel_writer/num{0,1}_amt{0,1}_lang{0,1}.md` (8 files)

- [ ] **Step 1: Re-run the fixture generator**

Run: `uv run python dev/bin/gen_zettel_writer_fixtures.py`

Expected: 8 fixture files rewritten under `tests/tools/bim/doc/fixtures/zettel_writer/`.

- [ ] **Step 2: Eyeball the diff**

Run: `git diff --stat tests/tools/bim/doc/fixtures/zettel_writer/`

Expected: 8 files changed.

Then: `git diff tests/tools/bim/doc/fixtures/zettel_writer/num1_amt1_lang1.md`

Expected diff content (per file): exactly two regions. (1) The `file-path:` line changes from a bare path to a double-quoted Markdown link. (2) The body loses the `[Open PDF](file:///...)` line and the blank line that followed it (two consecutive deleted lines between the H1 and the next paragraph or `## OCR text`).

If any fixture shows other changes, stop and re-read the writer diff.

- [ ] **Step 3: Run the parametrised fixture tests; they must now pass**

Run: `uv run pytest tests/tools/bim/doc/test_zettel_writer.py::TestZettelWriterPerVariantFixtures -v`

Expected: all 8 parametrised variants pass.

- [ ] **Step 4: Run the full bim doc test suite as a smoke check**

Run: `uv run pytest -m bim tests/tools/bim/doc/ -q`

Expected: all green. The CLI tests, pipeline tests, audit tests, etc., do not consume the `file-path` YAML value as a path, so they should be unaffected (see the design doc for the consumer audit).

If anything is red, stop and investigate.

---

## Task 4: Update CHANGELOG and commit code + tests + fixtures

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Open `CHANGELOG.md` and locate the `[Unreleased]` section**

Specifically find the `### Changed` subheading under `## [Unreleased]`. If `### Changed` does not exist yet, create it (immediately after any `### Added` block, or directly under `## [Unreleased]` if none exists). Use the same heading style as other sections in the file.

- [ ] **Step 2: Add the entry**

Append a single bullet under `### Changed`:

```markdown
- **bim**: doc-ingest zettels embed the source-file link in `file-path` frontmatter as `"[Open file](file://...)"` instead of an `[Open PDF]` link in the body (file-type-agnostic)
```

- [ ] **Step 3: Verify the working tree is what you expect**

Run: `git status --short`

Expected staged-or-modified files (the engineer hasn't run `git add` yet; these are all unstaged `M`/`??`):

```
 M CHANGELOG.md
 M src/tools/bim/commands/doc/shared/zettel_writer.py
 M tests/tools/bim/doc/fixtures/zettel_writer/num0_amt0_lang0.md
 M tests/tools/bim/doc/fixtures/zettel_writer/num0_amt0_lang1.md
 M tests/tools/bim/doc/fixtures/zettel_writer/num0_amt1_lang0.md
 M tests/tools/bim/doc/fixtures/zettel_writer/num0_amt1_lang1.md
 M tests/tools/bim/doc/fixtures/zettel_writer/num1_amt0_lang0.md
 M tests/tools/bim/doc/fixtures/zettel_writer/num1_amt0_lang1.md
 M tests/tools/bim/doc/fixtures/zettel_writer/num1_amt1_lang0.md
 M tests/tools/bim/doc/fixtures/zettel_writer/num1_amt1_lang1.md
 M tests/tools/bim/doc/test_zettel_writer.py
```

(If the pre-flight check surfaced other in-flight changes that the user said to keep, they will appear here too. Inspect carefully and only stage what belongs to this commit.)

- [ ] **Step 4: Commit**

Stage only this plan's changes:

```bash
git add CHANGELOG.md src/tools/bim/commands/doc/shared/zettel_writer.py tests/tools/bim/doc/test_zettel_writer.py tests/tools/bim/doc/fixtures/zettel_writer/
```

Verify with `git diff --cached --stat` (expect ~11 files), then commit:

```bash
git commit -m "feat(bim): embed source-file link as Open file in file-path frontmatter"
```

(Conventional Commits per `rules/development-workflow.md`. No trailers. No HEREDOC.)

---

## Task 5: Update tracked documentation (`docs/source/tools/bim.rst`)

**Files:**
- Modify: `docs/source/tools/bim.rst`

- [ ] **Step 1: Update the introductory paragraph**

Find (around lines 287–291):

```
Both ``bim doc ingest`` and ``bim doc promote`` produce zettels in the v1
shape: kebab-case keys throughout, single ``issuer`` field (the human
display name), ISO-8601 ``ingested-at`` datetime with offset, absolute
``file://`` link in the body, optional LLM-generated summary paragraph,
and per-issuer vault subfolder.
```

Replace `absolute ``file://`` link in the body` with `absolute ``file://`` link in the ``file-path`` frontmatter`. Leave the rest of the paragraph as-is.

- [ ] **Step 2: Update the example code block**

Find the YAML/Markdown code block at lines 293–328. Two edits:

(a) Replace the `file-path:` line (currently line 308):

```
    file-path: /Users/bob/Library/Mobile Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf
```

with:

```
    file-path: "[Open file](file:///Users/bob/Library/Mobile%20Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf)"
```

(b) Remove the body link line and the blank line that follows it. Currently (lines 319–323):

```
    # ČEZ a.s. invoice 7102105594

    [Open PDF](file:///Users/bob/Library/Mobile%20Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf)

    Vyúčtování za elektřinu za období 1.1.2021 – 28.2.2021. Splatnost 25.3.2021. Variabilní symbol 7102105594.
```

After:

```
    # ČEZ a.s. invoice 7102105594

    Vyúčtování za elektřinu za období 1.1.2021 – 28.2.2021. Splatnost 25.3.2021. Variabilní symbol 7102105594.
```

(Keep RST indentation: each line inside the `.. code-block:: markdown` directive must remain 4-space-indented. Don't introduce stray trailing whitespace.)

- [ ] **Step 3: Rewrite the `file-path` reserved-key bullet**

Find (lines 339–340):

```
- ``file-path`` — absolute filesystem path, no ``~`` segment. The body
  ``file://`` link URL-encodes spaces but preserves tildes literal.
```

Replace with:

```
- ``file-path``: a double-quoted Markdown link of the form
  ``"[Open file](file://<encoded-absolute-path>)"``. Path is absolute (no
  ``~`` segment), URL-encodes spaces as ``%20``, keeps tildes literal.
  Link text is ``Open file`` (file-type-agnostic). The source-file link
  used to live in the body as ``[Open PDF](...)``; that body line was
  removed.
```

(Note: this list uses `:` rather than em dashes per `rules/writing.md` rule 6.)

- [ ] **Step 4: Build the docs locally to confirm no Sphinx errors**

Run: `uv run sphinx-build -b html docs/source docs/build/html -q -W`

Expected: exit code 0, no warnings treated as errors. Open `docs/build/html/tools/bim.html` in a browser if you want a visual check, but the build passing is enough.

If Sphinx errors out (often: RST list indentation, missing blank lines around code blocks), fix the indentation and re-run.

- [ ] **Step 5: Commit the docs change**

```bash
git add docs/source/tools/bim.rst
git commit -m "docs(bim): document file-path as Markdown link in zettel frontmatter"
```

(`docs` type per Conventional Commits; no CHANGELOG entry required per `rules/changelog.md`.)

---

## Task 6: Update the local spec (gitignored)

**Files:**
- Modify: `dev/local/specs/bim-doc-architecture.md` (gitignored, no commit)

- [ ] **Step 1: Update the YAML example in §5**

Find the YAML code block at lines 304–328 in `dev/local/specs/bim-doc-architecture.md`. Replace the `file-path:` line:

```
file-path: /Users/bob/Library/Mobile Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf
```

with:

```
file-path: "[Open file](file:///Users/bob/Library/Mobile%20Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf)"
```

- [ ] **Step 2: Rewrite the `file-path` rule under "Field rules"**

Find (line 340):

```
- `file-path` is an **expanded absolute path** (no `~/`), URL-unencoded, written as a YAML plain scalar. Obsidian-side cross-platform portability is sacrificed deliberately so that links in the body are clickable on Bob's Mac.
```

Replace with:

```
- `file-path` is a **double-quoted Markdown link** of the form `"[Open file](file://<encoded-absolute-path>)"`. The path inside the URL is absolute (no `~/`), URL-encoded with `urllib.parse.quote(p, safe="/~")` (spaces become `%20`, tildes stay literal). The link text is `Open file` rather than `Open PDF` so the same shape works when the pipeline later ingests non-PDF documents. Obsidian renders the link clickable from the Properties pane; the body no longer carries a duplicate copy.
```

- [ ] **Step 3: Update the "Zettel body template" block**

Find (lines 353–364):

```markdown
# {{ title }}

[Open PDF](file://{{ file-path-url-encoded }})

{{ summary }}

## OCR text

> [!quote]- Full text
> {{ ocr-text }}
```

Replace with:

```markdown
# {{ title }}

{{ summary }}

## OCR text

> [!quote]- Full text
> {{ ocr-text }}
```

- [ ] **Step 4: Replace the PDF-link body rule**

Find the bullet that begins (line 369):

```
- **PDF link uses an absolute, URL-encoded `file://` URL.** This is what Obsidian opens reliably on macOS. Literal example, line-wrapped only for readability:
```

…and continues through the code example and the "Spaces become `%20`…" sentence (ending around line 373). Replace that entire bullet (the bold heading, the example, and the encoding sentence) with:

```
- **Source-file link lives in frontmatter, not body.** The clickable `file://` URL is the value of the `file-path` frontmatter field (see "Field rules" above) and renders in Obsidian's Properties pane. The body no longer carries a `[Open PDF](...)` line.
```

- [ ] **Step 5: Sanity-check `dev/local/` is still gitignored**

Run: `git check-ignore dev/local/specs/bim-doc-architecture.md`

Expected: the file is listed (exit 0, output includes the gitignore rule). No commit needed; this is a working document by `rules/working-documents.md`.

---

## Task 7: Final verification

- [ ] **Step 1: Run the full bim test suite**

Run: `uv run pytest -m bim -q`

Expected: green. If any unrelated bim test fails, surface it to the user (it predates this work; the writer change is contained).

- [ ] **Step 2: Run the lib test suite (catches any cross-package import regression)**

Run: `uv run pytest -m lib -q`

Expected: green.

- [ ] **Step 3: Type-check**

Run: `uv run mypy src/lib/ src/tools/`

Expected: 0 errors. The new `_DoubleQuoted` class and representer are fully typed; the body builder lost two locals but the function signature is unchanged.

- [ ] **Step 4: Confirm the two commits land cleanly**

Run: `git log --oneline -3`

Expected output shape:

```
<sha> docs(bim): document file-path as Markdown link in zettel frontmatter
<sha> feat(bim): embed source-file link as Open file in file-path frontmatter
<old-sha> <previous commit on master>
```

Both commits use Conventional Commits; no trailers; no `Co-Authored-By`.

- [ ] **Step 5: Done. No PR/push unless the user asks.**

Per `CLAUDE.md` Bash section: don't push or open a PR without explicit user direction.
