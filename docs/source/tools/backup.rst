.. _tool-backup:

backup
======

Config-driven archiver that wraps the git-src backup as a ``tar-archive``
capability. What gets archived — which source trees, where the archive lands,
and what is excluded — is defined in configuration, not code, so adding or
retuning a backup is a config edit rather than a release.

Usage
-----

.. code-block:: bash

    backup                              # run enabled instances with up to 3 jobs
    backup --jobs 1                     # run instances strictly sequentially
    backup --quiet                      # hide live status, keep final results
    backup --only git-src,docs          # run only these instances (comma list or repeated)
    backup --tag nightly                # run only instances carrying this tag
    backup --list                       # print the configured instances and exit
    backup --plan                       # report run/skip/fail decisions from metadata only
    backup --dry-run                    # walk and report what would be archived, write nothing
    backup --only git-src --source DIR --out FILE   # one-shot override of the selected instance
    backup --show-excludes git-src --for PATH       # print the resolved excludes under PATH

``--source`` / ``--out`` override the single selected instance for one run (a
non-empty flag wins over the configured value); they require exactly one
selected instance, via ``--only``. ``--show-excludes`` is read-only: it prints
the resolved exclude set and, with ``--for <path>``, the ``.bkpignore`` rules
effective under that path, then exits without writing an archive.

Parallel execution
------------------

``--jobs N`` limits concurrent instances (default 3; integer, at least 1).
``--jobs 1`` runs strictly sequentially. Instances are submitted in ascending
``(order, name)`` order; results appear as instances complete. An instance does
not wait for every lower-order instance to finish before it can start.

Ctrl-C stops new work, requests cancellation of active writers and waits for
them to stop. The command names unfinished instances and exits with status 130.
Completed archives remain available; cancellation before publication preserves
any previous archive. Python archive cancellation takes effect after the
current member finishes. Parallel execution does not guarantee a speedup.

Live progress
-------------

TTY runs show per-instance phases and elapsed time, measured from receipt of
the instance's first progress event. Python archives show input-byte percentages
capped at 99%; these measure input consumed, not compressed output or completion.
Finalizing has no percentage. System tar shows activity only, including when
it falls back to the Python engine.

Live status is disabled with ``--quiet``, non-TTY output, ``--list``, ``--plan``,
``--dry-run`` and ``--show-excludes``. Normal final output is preserved;
``--quiet`` keeps final results and summary counts.

Planning
--------

``--plan`` reports a metadata-only preview with a ``run``, ``skip`` or ``fail``
row for each selected instance, including the reason and a replacement marker
when its output already exists. It does not write archives or walk their
contents. Use ``--only`` and ``--tag`` to select instances; ``--source`` and
``--out`` apply the same single-instance overrides as a normal run. A plan with
any ``fail`` row exits with status 1. ``--plan`` and ``--dry-run`` are mutually
exclusive; use ``--dry-run`` to walk and preview archive members.

All selected output paths use one timestamp for ``strftime`` expansion.
Colliding output paths are rejected for plans, normal runs and dry runs after
lexical ``expanduser`` / ``normpath`` normalization; this check does not resolve
symlinks. A plan is a point-in-time preview: execution rechecks conditions before
writing, so later filesystem changes can alter the outcome.

Configuration
-------------

Instances live in ``buvis-backup.yaml`` in the buvis config stack
(``$BUVIS_CONFIG_DIR`` → ``~/.config/buvis`` → cwd), deep-merged over a bundled
default. Instances are a **name-keyed map**, so a machine layer adds an instance
under a new key and overrides a field of an existing instance by that key.

.. code-block:: yaml

    # buvis-backup.yaml
    instances:
      git-src:
        use: tar-archive                # a registered capability
        order: 10                       # submission priority, ascending
        tags: [nightly]
        with:                           # capability inputs
          source: ~/git/src
          out: ~/backups/git-src-%Y%m%d-%H%M%S.tar.gz
          engine: python-tarfile        # or system-tar (opt-in)

    excludes:                           # global basename/relpath exclude list
      - node_modules
      - target
      - __pycache__

Each instance is a ``use`` entry naming a capability with optional ``with``
inputs. Common fields:

============================  ==============================================================
Field                         Meaning
============================  ==============================================================
``use``                       registered capability name (``tar-archive``)
``enabled``                   set ``false`` to skip a merged/bundled instance (default true)
``order``                     integer; submission priority, ascending (default 100)
``tags``                      list of strings for ``--tag`` filtering
``inherit_excludes``          inherit global excludes (default true)
``exclude_remove``            exact inherited patterns to remove (default empty list)
``exclude_add``               patterns to append for this instance (default empty list)
``with``                      capability inputs (``source``, ``out``, ``engine``, ``items``)
============================  ==============================================================

The ``out`` value supports ``strftime`` codes (e.g. ``%Y%m%d-%H%M%S``), expanded
using one timestamp for all selected outputs. An unknown capability name, an
unknown ``with`` input, or an unknown ``engine`` value is a config/step error
reported clearly — never a stack trace.

Selected items
~~~~~~~~~~~~~~

Omit ``items`` to archive the whole source tree, with member names prefixed by
the source directory's name. Set ``items`` to bundle selected files and
directories, with member names relative to ``source``:

.. code-block:: yaml

    instances:
      settings:
        use: tar-archive
        with:
          source: ~
          out: /Volumes/Backup/settings.tar.gz
          items: [.gitconfig, .config/tool]

Items are literal relative paths, without glob expansion. Redundant separators
and ``.`` components are normalized; duplicate items and children of a selected
directory are included only once. Empty lists, empty paths, absolute paths,
paths normalizing to ``.``, and paths whose first component is ``..`` are
errors; a literal name such as ``..hidden`` is valid. ``items`` must be a list
of strings, and ``items: null`` means the key is omitted (whole tree).
An item cannot pass through a symlink directory. A final symlink, including a
broken one, is archived as a link without following its target.

Excludes still match source-relative paths or basenames. Ancestor and selected
directory ``.bkpignore`` files apply with the same pruning and precedence as a
whole-tree backup. Missing items are listed in the result while present items
are archived. An item that cannot be inspected (for example under an
unreadable directory), an unreadable selected file, or one that disappears
after its presence check fails the step instead of counting as missing.

The global ``excludes`` list layers via the 00080 ``excludes+`` / ``excludes-``
directives, so a lower layer extends or trims the shared list without re-listing
it:

.. code-block:: yaml

    # buvis-backup.local.yaml  (machine-local, never `dot add`ed)
    excludes+: [scratch-notes]   # add to the inherited list
    excludes-: [target]          # drop a default on this box only

Instance exclusions
~~~~~~~~~~~~~~~~~~~

Set ``inherit_excludes``, ``exclude_remove`` and ``exclude_add`` beside ``with``,
not inside it:

.. code-block:: yaml

    instances:
      documents:
        use: tar-archive
        inherit_excludes: false
        exclude_add: [scratch, sub/cache]
        with:
          source: ~/Documents
          out: ~/backups/documents.tar.gz
      git-src:
        exclude_remove: [target]
        exclude_add: [logs]

Resolution starts with the merged global ``excludes`` list, or an empty list
when ``inherit_excludes: false``. It removes exact strings in ``exclude_remove``,
then appends ``exclude_add``. Duplicates keep their first occurrence in order.
An addition can therefore restore a removed pattern. Other instances and the
global list are unchanged.

A basename pattern such as ``scratch`` matches that name at any depth, without
matching ``scratchpad``. A pattern containing ``/``, such as ``sub/cache``, is
relative to the source root: it excludes that subtree, not ``outer/sub/cache``
or ``sub/cache-notes``. ``--show-excludes NAME`` prints this effective instance
list; ``--for PATH`` also resolves the path's ``.bkpignore`` rules on top of it.

``.bkpignore`` files
~~~~~~~~~~~~~~~~~~~~~

Beyond the effective instance list, a ``.bkpignore`` file placed in any directory
of a source tree tunes exclusions for that subtree only, gitignore-style:

- A bare line adds an exclude for that subtree.
- A ``!pattern`` line un-ignores — it re-includes a path the global default
  would otherwise drop, path-scoped to that subtree (so ``!target`` in repo A's
  ``.bkpignore`` keeps only A's ``target/``; repo B's stays excluded).
- Blank lines and ``#`` comments are ignored; ``\!`` escapes a literal ``!``.

Precedence follows gitignore: a **descendant** ``.bkpignore`` overrides an
ancestor, and within one file a later line overrides an earlier one. So an
ancestor ``!target`` can be re-excluded by a descendant plain ``target`` line.
``.bkpignore`` files are never themselves archived.

Engines
~~~~~~~

Two archive engines produce byte-for-byte equivalent member sets; Python owns
file selection in both, so ``.bkpignore`` scoping is identical:

============================  ================================================================
Engine                        Behaviour
============================  ================================================================
``python-tarfile``            default; streams a ``w:gz`` tarball via the stdlib
``system-tar``                opt-in; shells out to system ``tar`` (NUL-delimited filelist),
                              falling back to the Python engine (with a note) if ``tar`` is
                              unavailable or fails
============================  ================================================================

Both engines write the archive atomically (temp file, ``fsync``, ``chmod 600``,
``os.replace``), so a crash or ``ENOSPC`` never leaves a partial ``.tar.gz`` at
the final path. An existing archive is replaced only after the new archive is
complete. Writer failures remove temporary files and preserve the existing
archive.

Run outcomes
~~~~~~~~~~~~

A missing source or a bundle with no surviving selected members is skipped,
including during ``--dry-run``. An existing source that is not a directory,
or a source that cannot be inspected (permission denied), fails. Skipped steps print a warning with the reason and leave any existing
archive untouched.

Every run ends with ``archived N, skipped N, failed N``; dry runs use
``previewed`` instead of ``archived``. Counts refer to steps, including an empty
run's zero counts. Skips succeed; failed steps make the command exit nonzero.
