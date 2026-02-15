CLI Tools
=========

Installation
------------

The base install registers all 9 CLIs but only pulls core dependencies.
Tools that need extra packages will tell you what to install if the dep is missing.

.. code-block:: bash

    uv tool install buvis-gems              # core CLIs
    uv tool install buvis-gems[bim]         # + jira
    uv tool install buvis-gems[bim,muc]     # combine extras
    uv tool install buvis-gems[all]         # everything

Available extras: ``bim``, ``hello-world``, ``muc``, ``pinger``, ``readerctl``, ``ml``, ``all``.

Overview
--------

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Command
     - Extra
     - Description
   * - ``bim``
     - ``bim``
     - BUVIS InfoMesh — Zettelkasten management with Jira integration
   * - ``dot``
     -
     - Dotfiles manager
   * - ``fctracker``
     -
     - Foreign currency account tracker
   * - ``hello-world``
     - ``hello-world``
     - Sample script template
   * - ``muc``
     - ``muc``
     - Music collection tools (tagging, tidying)
   * - ``outlookctl``
     -
     - Outlook calendar CLI (Windows)
   * - ``pinger``
     - ``pinger``
     - ICMP ping utilities
   * - ``readerctl``
     - ``readerctl``
     - Readwise Reader CLI
   * - ``zseq``
     -
     - Zettelsequence file naming utilities

Common Options
--------------

Every tool inherits these options from the shared ``buvis_options`` decorator:

.. code-block:: text

    --config FILE                   YAML config file path
    --config-create FILE            Generate YAML config template to FILE
    --config-dir DIRECTORY          Configuration directory
    --log-level [debug|info|warning|error]
    --debug / --no-debug            Enable debug mode

See :doc:`configuration` for how settings are resolved (CLI > env > YAML > defaults).

.. _tool-bim:

bim
---

BUVIS InfoMesh — full-featured Zettelkasten manager with query engine, templates,
Jira sync, and a web dashboard.

**Extra:** ``uv tool install buvis-gems[bim]``

Configuration
~~~~~~~~~~~~~

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
~~~~~~~~

**bim create** — Create a new zettel from a template.

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

**bim query** — Query zettels with a YAML filter/sort/output spec.

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

**bim import** — Import a markdown file into the zettelkasten.

.. code-block:: bash

    bim import ~/Downloads/meeting-notes.md
    bim import ~/Downloads/draft.md --tags "imported,review" --force --remove-original

Options:

- ``--tags TEXT`` — comma-separated tags
- ``--force`` — overwrite if target exists
- ``--remove-original`` — delete source file after import

**bim edit** — Modify zettel metadata in-place.

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

**bim format** — Format a note's metadata and content.

.. code-block:: bash

    bim format ~/bim/zettelkasten/my-note.md
    bim format ~/bim/zettelkasten/my-note.md -d    # show diff
    bim format ~/bim/zettelkasten/my-note.md -h    # highlight output
    bim format ~/bim/zettelkasten/my-note.md -o formatted.md

Options:

- ``-h, --highlight`` — highlight formatted content
- ``-d, --diff`` — show side-by-side diff if content changed
- ``-o, --output FILE`` — write to file instead of in-place

**bim show** — Pretty-print a zettel.

.. code-block:: bash

    bim show ~/bim/zettelkasten/my-note.md

**bim archive** — Mark zettel(s) as processed and move to archive directory.

.. code-block:: bash

    bim archive ~/bim/zettelkasten/done-note.md
    bim archive ~/bim/zettelkasten/a.md ~/bim/zettelkasten/b.md
    bim archive --undo ~/bim/reference/40-archives/done-note.md

Options:

- ``--undo`` — unarchive (move back to zettelkasten)

**bim delete** — Permanently delete zettel(s).

.. code-block:: bash

    bim delete ~/bim/zettelkasten/obsolete.md
    bim delete --force ~/bim/zettelkasten/a.md ~/bim/zettelkasten/b.md

Options:

- ``--force`` — skip confirmation prompt

**bim sync** — Synchronize a note with an external system (currently Jira).

.. code-block:: bash

    bim sync ~/bim/zettelkasten/project-note.md jira

Arguments: ``PATH_TO_NOTE``, ``TARGET_SYSTEM``.

**bim parse_tags** — Extract unique tags from an Obsidian Metadata Extractor ``tags.json``.

.. code-block:: bash

    bim parse_tags ~/bim/tags.json
    bim parse_tags ~/bim/tags.json -o tags.txt

Options:

- ``-o, --output FILE`` — write output to file

**bim serve** — Start the web dashboard (SvelteKit frontend).

.. code-block:: bash

    bim serve
    bim serve -p 3000 -H 0.0.0.0
    bim serve --no-browser

Options:

- ``-p, --port INTEGER`` — port (default: 8000)
- ``-H, --host TEXT`` — host (default: 127.0.0.1)
- ``--no-browser`` — don't auto-open browser

.. _tool-dot:

dot
---

Manager for bare-repo dotfiles. Wraps git operations on your ``$DOTFILES_ROOT``
(defaults to ``$HOME``).

Configuration
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``add_file_path``
     - *none*
     - Default file to stage in ``add``

Commands
~~~~~~~~

**dot status** — Show git and git-secret status of your dotfiles repo.

.. code-block:: bash

    dot status

**dot add** — Interactively stage changes (cherry-pick mode).

.. code-block:: bash

    dot add                     # interactive selection
    dot add ~/.bashrc           # stage specific file

.. _tool-fctracker:

fctracker
---------

Track balances and transactions across foreign currency accounts.

Configuration
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``transactions_dir``
     - ``""``
     - Directory containing transaction files
   * - ``local_currency``
     - ``code=CZK, symbol=Kč, precision=2``
     - Local currency config
   * - ``foreign_currencies``
     - ``{}``
     - Map of currency code to ``{symbol, precision}``

Example YAML config:

.. code-block:: yaml

    transactions_dir: ~/finance/transactions
    local_currency:
      code: CZK
      symbol: "Kč"
      precision: 2
    foreign_currencies:
      EUR:
        symbol: "€"
        precision: 2
      USD:
        symbol: "$"
        precision: 2

Commands
~~~~~~~~

**fctracker balance** — Print current balance across all accounts and currencies.

.. code-block:: bash

    fctracker balance

**fctracker transactions** — Print transaction ledger with optional filters.

.. code-block:: bash

    fctracker transactions
    fctracker transactions -a savings -c EUR
    fctracker transactions -m 2025-01

Options:

- ``-a, --account TEXT`` — filter by account
- ``-c, --currency TEXT`` — filter by currency
- ``-m, --month TEXT`` — filter by month (``YYYY-MM``)

.. _tool-hello-world:

hello-world
------------

Sample script template. Renders text with figlet fonts. Useful as a proof-of-concept
or starting point for new tools.

**Extra:** ``uv tool install buvis-gems[hello-world]``

Configuration
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``font``
     - ``doom``
     - Figlet font name
   * - ``text``
     - ``World``
     - Text to render

Commands
~~~~~~~~

.. code-block:: bash

    hello-world                          # render "World" in doom font
    hello-world "Buvis" -f slant         # custom text and font
    hello-world -r                       # random font
    hello-world -l                       # list available fonts
    hello-world --diag                   # print python runtime and dep info

Options:

- ``-f, --font TEXT`` — font name
- ``-l, --list-fonts`` — list available fonts
- ``-r, --random-font`` — pick a random font
- ``--diag`` — print Python runtime and dependency info

.. _tool-muc:

muc
---

Music collection tools for transcoding and cleanup.

**Extra:** ``uv tool install buvis-gems[muc]``

Configuration
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``limit_flac_bitrate``
     - ``1411000``
     - Target bitrate (bps)
   * - ``limit_flac_bit_depth``
     - ``16``
     - Target bit depth
   * - ``limit_flac_sampling_rate``
     - ``44100``
     - Target sampling rate (Hz)
   * - ``tidy_junk_extensions``
     - ``.cue .db .jpg .lrc .m3u .md .nfo .png .sfv .txt .url``
     - File extensions to remove during tidy

Commands
~~~~~~~~

**muc limit** — Transcode FLAC files to target spec (CD quality by default).

.. code-block:: bash

    muc limit ~/music/hi-res-album/
    muc limit ~/music/hi-res-album/ -o ~/music/transcoded/

Options:

- ``-o, --output TEXT`` — output directory (default: ``./transcoded``)

**muc tidy** — Clean up a music directory: merge macOS metadata, normalize
extensions, remove junk files, delete empty directories.

.. code-block:: bash

    muc tidy ~/music/album/
    muc tidy ~/music/album/ -y     # skip confirmation

Options:

- ``-y, --yes`` — skip confirmation prompt

.. _tool-outlookctl:

outlookctl
----------

Outlook calendar CLI. Windows only (uses COM automation via ``OutlookLocalAdapter``).

Configuration
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``default_timeblock_duration``
     - ``25``
     - Timeblock duration in minutes (Pomodoro-style)

Commands
~~~~~~~~

**outlookctl create_timeblock** — Create a timeblock event in Outlook.

.. code-block:: bash

    outlookctl create_timeblock

.. _tool-pinger:

pinger
------

ICMP ping utilities. Waits for a host to come online.

**Extra:** ``uv tool install buvis-gems[pinger]``

Configuration
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``host``
     - ``127.0.0.1``
     - Default target host
   * - ``wait_timeout``
     - ``600``
     - Max wait in seconds

Commands
~~~~~~~~

**pinger wait** — Poll a host with ICMP until it responds or timeout is reached.

.. code-block:: bash

    pinger wait 192.168.1.1
    pinger wait nas.local -t 120

Options:

- ``-t, --timeout INTEGER`` — give up after N seconds (overrides setting)

.. _tool-readerctl:

readerctl
---------

CLI for Readwise Reader. Add URLs to your reading list.

**Extra:** ``uv tool install buvis-gems[readerctl]``

Configuration
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``token_file``
     - ``~/.config/scripts/readwise-token``
     - Path to API token file

Commands
~~~~~~~~

**readerctl login** — Authenticate with Readwise. Prompts for token and stores it.

.. code-block:: bash

    readerctl login

**readerctl add** — Add URL(s) to Reader. Requires prior ``login``.

.. code-block:: bash

    readerctl add -u https://example.com/article
    readerctl add -f ~/urls.txt     # one URL per line

Options:

- ``-u, --url TEXT`` — single URL to add
- ``-f, --file TEXT`` — file with URLs (one per line)

.. _tool-zseq:

zseq
----

Work with Zettelkasten sequential file naming (``YYYYMMDDHHMMSS`` prefixes).
Reports the highest sequence number in a directory.

Configuration
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``path_dir``
     - ``/Volumes/photography/photography/src/2024``
     - Directory to scan
   * - ``is_reporting_misnamed``
     - ``false``
     - Report files not following zettelseq naming

Commands
~~~~~~~~

.. code-block:: bash

    zseq                                 # max seq in default dir
    zseq -p ~/photos/2025/               # custom directory
    zseq -m                              # also report misnamed files

Options:

- ``-p, --path TEXT`` — directory to scan
- ``-m, --misnamed-reporting`` — report non-conforming files

Extending Tools
---------------

Each tool follows the same Click-based pattern:

.. code-block:: python

    import click
    from buvis.pybase.configuration import buvis_options, get_settings

    @click.command()
    @buvis_options
    @click.pass_context
    def cli(ctx: click.Context) -> None:
        settings = get_settings(ctx)
        command = MyCommand(settings)
        command.execute()

See :doc:`configuration` for how to create custom settings classes and YAML config files.
