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
  and zettel written to ``<vault_root>/Zettelkasten/documents/<canonical>.md``.
- **triaged** — confidence too low or required field missing. The PDF lands
  in ``<business_root>/_triage/`` with a ``.proposed.yml`` sidecar awaiting
  human review.
- **duplicate** — sha256 already mapped to a filed document. A
  ``.duplicate.yml`` sidecar is written next to the staged input.

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
