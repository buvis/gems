.. _tool-bim:

bim
===

BUVIS InfoMesh — full-featured Zettelkasten manager with query engine, templates,
Jira sync, and a web dashboard.

**Extra:** ``uv tool install buvis-gems[bim]``

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``path_zettelkasten``
     - ``~/bim/zettelkasten/``
     - Root directory for zettels
   * - ``path_archive``
     - ``~/bim/reference/40-archives/``
     - Archive directory

Env vars: ``BUVIS_BIM_PATH_ZETTELKASTEN``, ``BUVIS_BIM_PATH_ARCHIVE``.

Commands
--------

bim create
~~~~~~~~~~

Create a new zettel from a template.

.. code-block:: bash

    # interactive (prompts for template type, title, tags)
    bim create

    # specify type and title directly
    bim create -t project --title "Redesign homepage" --tags "web,design"

    # list available templates
    bim create -l

    # pre-fill template answers
    bim create -t meeting -a "attendees=Alice,Bob" -a "date=2025-01-15"

Options:

- ``-t, --type TEXT`` — template type (note, project, etc.)
- ``--title TEXT`` — zettel title
- ``--tags TEXT`` — comma-separated tags
- ``-a, --answer TEXT`` — template answer as ``key=value`` (repeatable)
- ``-l, --list`` — list available templates

bim query
~~~~~~~~~

Query zettels with a YAML filter/sort/output spec.

.. code-block:: bash

    # inline query: first 5 zettels
    bim query -q '{output: {limit: 5}}'

    # filter by type, pick columns
    bim query -q '{
      columns: [{field: title}, {field: tags}],
      filter: {field: type, op: eq, value: project},
      output: {format: table}
    }'

    # load saved query from file
    bim query -f my-query

    # list saved queries
    bim query -l

    # pick result with fzf, open in nvim
    bim query -q '{filter: {field: type, op: eq, value: note}}' -e

    # interactive TUI
    bim query -q '{output: {limit: 20}}' --tui

Options:

- ``-f, --file TEXT`` — query name or path to YAML spec
- ``-q, --query TEXT`` — inline YAML query string
- ``-e, --edit`` — pick result with fzf and open in nvim
- ``--tui`` — render output in interactive TUI
- ``-l, --list`` — list available queries

Output formats: ``table``, ``csv``, ``markdown``, ``json``, ``jsonl``, ``html``, ``pdf``, ``kanban``.

See `bim-query-examples.md <https://github.com/buvis/gems/blob/master/docs/source/bim-query-examples.md>`_
for a comprehensive reference with filter operators, calculated columns, lookups, and more.

bim import
~~~~~~~~~~

Import a markdown file into the zettelkasten.

.. code-block:: bash

    bim import ~/Downloads/meeting-notes.md
    bim import ~/Downloads/draft.md --tags "imported,review" --force --remove-original

Options:

- ``--tags TEXT`` — comma-separated tags
- ``--force`` — overwrite if target exists
- ``--remove-original`` — delete source file after import

When importing interactively (no flags), if the note has no tags and
``ollama_model`` is configured globally (see :ref:`configuration`), bim
suggests tags via ollama. Each suggested tag is presented for confirmation.
If ollama is unreachable, tag suggestion is skipped with a warning.

bim edit
~~~~~~~~

Modify zettel metadata in-place.

.. code-block:: bash

    bim edit ~/bim/zettelkasten/my-note.md --title "Better title"
    bim edit ~/bim/zettelkasten/my-note.md --tags "updated,important"
    bim edit ~/bim/zettelkasten/my-note.md --processed
    bim edit ~/bim/zettelkasten/my-note.md -s "priority=high" -s "reviewer=alice"

Options:

- ``--title TEXT`` — new title
- ``--tags TEXT`` — comma-separated tags
- ``--type TEXT`` — note type
- ``--processed / --no-processed`` — processed flag
- ``--publish / --no-publish`` — publish flag
- ``-s, --set TEXT`` — arbitrary ``key=value`` metadata (repeatable)

bim format
~~~~~~~~~~

Format a note's metadata and content.

.. code-block:: bash

    bim format ~/bim/zettelkasten/my-note.md
    bim format ~/bim/zettelkasten/my-note.md -d    # show diff
    bim format ~/bim/zettelkasten/my-note.md -h    # highlight output
    bim format ~/bim/zettelkasten/my-note.md -o formatted.md

Options:

- ``-h, --highlight`` — highlight formatted content
- ``-d, --diff`` — show side-by-side diff if content changed
- ``-o, --output FILE`` — write to file instead of in-place

bim show
~~~~~~~~

Pretty-print a zettel.

.. code-block:: bash

    bim show ~/bim/zettelkasten/my-note.md

bim archive
~~~~~~~~~~~

Mark zettel(s) as processed and move to archive directory.

.. code-block:: bash

    bim archive ~/bim/zettelkasten/done-note.md
    bim archive ~/bim/zettelkasten/a.md ~/bim/zettelkasten/b.md
    bim archive --undo ~/bim/reference/40-archives/done-note.md

Options:

- ``--undo`` — unarchive (move back to zettelkasten)

bim delete
~~~~~~~~~~

Permanently delete zettel(s).

.. code-block:: bash

    bim delete ~/bim/zettelkasten/obsolete.md
    bim delete --force ~/bim/zettelkasten/a.md ~/bim/zettelkasten/b.md

Options:

- ``--force`` — skip confirmation prompt

bim sync
~~~~~~~~

Synchronize a note with an external system (currently Jira).

.. code-block:: bash

    bim sync ~/bim/zettelkasten/project-note.md jira

Arguments: ``PATH_TO_NOTE``, ``TARGET_SYSTEM``.

bim serve
~~~~~~~~~

Start the web dashboard (SvelteKit frontend).

.. code-block:: bash

    bim serve
    bim serve -p 3000 -H 0.0.0.0
    bim serve --no-browser

Options:

- ``-p, --port INTEGER`` — port (default: 8000)
- ``-H, --host TEXT`` — host (default: 127.0.0.1)
- ``--no-browser`` — don't auto-open browser

bim doc
-------

Document ingestion + triage workflow. Files PDFs into a canonical filesystem
layout and indexes each one with a Zettelkasten note, OCR'd and structured.

**Extra:** ``uv tool install buvis-gems[doc]``

System dependencies (install separately):

- **Tesseract** (with Czech language pack): ``brew install tesseract tesseract-lang``
- **OCRmyPDF**: ``brew install ocrmypdf``
- **Ollama**: ``brew install ollama``, then ``ollama pull qwen2.5:7b-instruct``

Configuration lives under ``[doc]`` in the bim config (see ``DocSettings``
for the full schema): ``paths.business_root``, ``paths.vault_root``,
``paths.state_dir``, ``paths.issuers_file``, plus ``ocr``, ``classifier``,
and ``zettel`` blocks.

bim doc ingest
~~~~~~~~~~~~~~

Run the ingest pipeline against a single staged PDF. The eight steps -
dedup, OCR, classify, extract, name, write zettel, file, record - run with
mocked-friendly boundaries so dry-run-like behaviour is easy to test.

.. code-block:: bash

    bim doc ingest ~/Downloads/invoice.pdf
    bim doc ingest ~/Downloads/invoice.pdf --source email
    bim doc ingest ~/cez-as/inbox/x.pdf --source issuer-inbox --issuer cez-as

Arguments: ``PDF_PATH`` (must exist).

Options:

- ``--source`` — where the document entered the system. One of ``email``,
  ``scan``, ``download``, ``issuer-inbox``, ``backfill-canonical``,
  ``backfill-noncanonical``. Default: ``download``.
- ``--issuer`` — pre-pin an issuer slug. Honoured when ``--source issuer-inbox``.
- ``--strict`` — exit 1 on pipeline failure (for scripting). Default exit
  code is 0 even on ``success=False``, matching the rest of the bim CLI.
  Triaged and duplicate outcomes are not failures and remain exit 0
  regardless of this flag.

Outcomes (printed to console and recorded in ``state.db``):

- **filed** — PDF moved to ``<business_root>/<issuer-slug>/<canonical>.pdf``
  and zettel written to ``<vault_root>/Zettelkasten/documents/<issuer-slug>/<canonical>.md``
  (per-issuer subfolder; the vault layout mirrors the business root).
- **triaged** — confidence too low or required field missing. The PDF lands
  in ``<business_root>/_triage/`` with a ``.proposed.yml`` sidecar awaiting
  human review.
- **duplicate** — sha256 already mapped to a filed document. A
  ``.duplicate.yml`` sidecar is written next to the staged input.

Zettel v1 shape
~~~~~~~~~~~~~~~

Both ``bim doc ingest`` and ``bim doc promote`` produce zettels in the v1
shape: kebab-case keys throughout, single ``issuer`` field (the human
display name), ISO-8601 ``ingested-at`` datetime with offset, absolute
``file://`` link in the body, optional LLM-generated summary paragraph,
and per-issuer vault subfolder.

.. code-block:: yaml

    ---
    id: 20210311083422
    title: ČEZ a.s. invoice 7102105594
    type: document
    doc-type: invoice
    issuer: ČEZ a.s.
    doc-number: 7102105594
    doc-date: 2021-03-11
    doc-amount: 4218
    doc-currency: CZK
    doc-language: cs
    ingested-at: 2026-05-04T14:30:15+02:00
    ingest-source: email
    file-path: /Users/bob/Library/Mobile Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf
    file-sha256: 3f4a8c2b91e7d5a6b1c2d3e4f5061728394a5b6c7d8e9f0a1b2c3d4e5f607182
    ocr-engine: tesseract
    ocr-mean-confidence: 0.91
    extraction-method: rule:cez-invoice-2024-template:v1
    tags:
      - document/invoice
      - issuer/cez-as
      - year/2021
    ---

    # ČEZ a.s. invoice 7102105594

    [Open PDF](file:///Users/bob/Library/Mobile%20Documents/com~apple~CloudDocs/Business/cez-as/20210311083422-cez-as-7102105594.invoice.pdf)

    Vyúčtování za elektřinu za období 1.1.2021 – 28.2.2021. Splatnost 25.3.2021. Variabilní symbol 7102105594.

    ## OCR text

    > [!quote]- Full text
    > <full OCR text>

Reserved frontmatter keys:

- ``id`` — bare 14-digit integer (Zettelkasten timestamp); never quoted.
- ``title`` — single-line human-readable label, equals the body H1.
- ``type`` — always ``document`` for ingested zettels.
- ``doc-number`` — emitted as a bare integer when the string round-trips
  (``str(int(s)) == s``); otherwise quoted to preserve leading zeros.
- ``ingested-at`` — tz-aware ISO 8601 with offset, parses with
  ``datetime.fromisoformat`` on Python 3.10+.
- ``file-path`` — absolute filesystem path, no ``~`` segment. The body
  ``file://`` link URL-encodes spaces but preserves tildes literal.

bim doc promote
~~~~~~~~~~~~~~~

Promote an approved triage proposal into a filed document. Re-derives OCR
from the staged PDF and ignores user-edited OCR text in the proposal.

.. code-block:: bash

    bim doc promote ~/Business/_triage/x.invoice.pdf.proposed.yml

Arguments: ``YML_PATH`` — path to a ``<basename>.pdf.proposed.yml`` file
whose sibling ``<basename>.pdf`` exists.

Options:

- ``--strict`` — exit 1 on promote failure (for scripting). Default exit
  code is 0 on failure to match the rest of the bim CLI.

The proposal must have ``approved: true`` and a slug present in the issuer
registry (or ``register_issuer: true`` to add a new issuer entry under flock).

Retry behaviour
~~~~~~~~~~~~~~~

The classifier and extractor stages retry transient HTTP failures up to
``classifier.max_retries`` (default 2) times against ``classifier.primary_model``,
then fall back once to ``classifier.fallback_model``. Semantic failures
(missing required fields, uncoercible values, unparseable model output) and
``requests.exceptions.Timeout`` short-circuit to triage immediately without
retry or fallback - retrying with the same input won't help on a model-output
problem.

Issuer registry
~~~~~~~~~~~~~~~

The registry lives at ``~/.dotfiles/bim/issuers.yml`` (configurable via
``paths.issuers_file``). Top-level keys: ``version``, ``doc_types``,
``reserved_slugs``, ``issuers``. Each issuer maps a canonical kebab-case
slug to ``display_name`` and a list of ``aliases`` the classifier uses to
canonicalise vendor names from OCR text.

The file is treated as plaintext by all bim processes; encryption (e.g. via
git-secret) happens at the dotfiles management layer.

Originals retention
~~~~~~~~~~~~~~~~~~~

Re-OCR keeps the pre-modification copy under
``<state_dir>/originals/<timestamp>-<sha256>.pdf`` for
``originals_retention_days`` (default 30). A garbage-collection command
(``bim doc gc-originals``) is out of scope for v1; clean these manually
if needed.

Rule engine
~~~~~~~~~~~

The pipeline runs a deterministic, declarative rule engine **before** the
LLM classifier and extractor. For documents whose templates are stable
(recurring vendor invoices, statements with fixed layouts), rules eliminate
LLM calls entirely, making extraction reproducible and auditable.

When no rule matches, behavior is unchanged from LLM-only ingestion.

**Why rules exist:**

* **Determinism.** A rule for CEZ invoices either matches or doesn't.
  No probabilistic drift across model versions or sampling.
* **Auditability.** A zettel's ``extraction-method: rule:cez-invoice-2024-template:v1``
  records exactly which rule produced its metadata.
* **Cost.** No round-trip to Ollama for documents a regex can pin.

**Rule schema (under each issuer in ``issuers.yml``):**

.. code-block:: yaml

    issuers:
      cez-as:
        display_name: ČEZ a.s.
        aliases: [ČEZ, cez.cz]

        rules:
          - id: cez-invoice-2024-template
            version: 1
            priority: 100
            partial: false
            match:
              ocr_contains: ["IČ: 45274649", "Faktura"]
              ocr_matches: ["Faktura č\\.\\s*(\\d{10})"]
            extract:
              doc_type: invoice
              doc_number:
                from: ocr_match
                pattern: "Faktura č\\.\\s*(\\d{10})"
                group: 1
              doc_date:
                from: ocr_match
                pattern: "Datum vystavení:\\s*(\\d{2}\\.\\d{2}\\.\\d{4})"
                group: 1
                format: "%d.%m.%Y"
                transform: parse_date
              doc_amount:
                from: ocr_match
                pattern: "Celkem k úhradě:\\s*([\\d\\s]+),\\d{2}\\s*Kč"
                group: 1
                transform: strip_whitespace_to_int
              doc_currency: CZK
              doc_language: cs

          - id: cez-fingerprint
            partial: true
            match:
              ocr_contains: ["IČ: 45274649"]
            extract:
              issuer_slug: cez-as
              issuer_display: ČEZ a.s.
              doc_language: cs

A rule with ``partial: true`` pins some fields and lets the LLM fill the
rest (typical use: fingerprint by IČO, let the LLM resolve the doc_type and
specific fields).

**Match clauses (v1 set):**

.. list-table::
   :header-rows: 1

   * - Clause
     - Behavior
   * - ``ocr_contains``
     - Substring(s) appear in OCR text. Case-folded + ASCII-folded.
   * - ``ocr_matches``
     - Regex(es) match OCR text via ``re.search``.
   * - ``email_from_domain``
     - Sender domain matches ``.email.yml`` sidecar's ``from``.
   * - ``email_subject_contains``
     - Substring(s) appear in email subject.
   * - ``email_subject_matches``
     - Regex match against email subject.
   * - ``original_filename_matches``
     - Regex match against the source file's original name.

All clauses within a rule are ANDed. Source-irrelevant clauses
(e.g. ``email_*`` on a scan) are silently false.

**Transforms (v1 set):**

``strip_whitespace_to_int``, ``strip_whitespace_to_decimal``, ``parse_date``
(uses ``format``), ``lowercase``, ``uppercase``, ``strip``, ``slugify``.

**Precedence:**

1. Full rules (``partial: false``) beat partial rules.
2. Among same partial-ness, higher ``priority`` wins.
3. Ties broken by definition order in ``issuers.yml``.

**Conflict** (two rules of same partial-ness disagreeing on ``issuer_slug``)
sends the document to triage with a ``rule_conflict: <id1> vs <id2>`` reason.

**bim doc rules subcommands:**

``bim doc rules list``
    Print all rules with id, issuer, version, partial, priority, enabled.

``bim doc rules validate``
    Static validation of ``issuers.yml`` rule blocks. Catches duplicate
    rule ids, uncompilable regexes, unknown transforms, reserved-field
    assignments. Run this after editing rules.

``bim doc rules test <rule-id> --pdf <path>``
    Run one rule against one PDF. Prints clause-by-clause pass/fail and
    extracted fields. Read-only — no zettel, no file move.

``bim doc rules backtest [--rule ID] [--issuer SLUG]``
    Walk ``business_root`` and report per-rule match counts grouped by
    issuer folder. Read-only. Slow on large archives (OCRs on demand).
    Run this **before deploying any new rule** — false positives that
    file documents under the wrong issuer with confident metadata are the
    most dangerous failure mode.

**Authoring workflow:** write rule → ``rules validate`` → ``rules test``
on a sample → ``rules backtest`` to verify no cross-folder hits → deploy.
