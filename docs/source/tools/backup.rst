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

    backup                              # run every enabled instance, in order
    backup --only git-src,docs          # run only these instances (comma list or repeated)
    backup --tag nightly                # run only instances carrying this tag
    backup --list                       # print the configured instances and exit
    backup --dry-run                    # walk and report what would be archived, write nothing
    backup --only git-src --source DIR --out FILE   # one-shot override of the selected instance
    backup --show-excludes git-src --for PATH       # print the resolved excludes under PATH

``--source`` / ``--out`` override the single selected instance for one run (a
non-empty flag wins over the configured value); they require exactly one
selected instance, via ``--only``. ``--show-excludes`` is read-only: it prints
the resolved exclude set and, with ``--for <path>``, the ``.bkpignore`` rules
effective under that path, then exits without writing an archive.

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
        order: 10                       # instances run in ascending order
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
``order``                     integer; instances run ascending (default 100)
``tags``                      list of strings for ``--tag`` filtering
``with``                      capability inputs (``source``, ``out``, ``engine``)
============================  ==============================================================

The ``out`` value supports ``strftime`` codes (e.g. ``%Y%m%d-%H%M%S``), expanded
at archive time. An unknown capability name, an unknown ``with`` input, or an
unknown ``engine`` value is a config/step error reported clearly — never a stack
trace.

The global ``excludes`` list layers via the 00080 ``excludes+`` / ``excludes-``
directives, so a lower layer extends or trims the shared list without re-listing
it:

.. code-block:: yaml

    # buvis-backup.local.yaml  (machine-local, never `dot add`ed)
    excludes+: [scratch-notes]   # add to the inherited list
    excludes-: [target]          # drop a default on this box only

``.bkpignore`` files
~~~~~~~~~~~~~~~~~~~~~

Beyond the global list, a ``.bkpignore`` file placed in any directory of a
source tree tunes exclusions for that subtree only, gitignore-style:

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
the final path.
