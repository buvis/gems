.. _tool-klyreon:

klyreon
=======

Autonomous Memex-Zettelkasten. ``klyreon`` is the gem that reads, writes, and
validates the Klyreon vault format (the normative format spec lives at
``docs/reference/klyreon/zettel-format-specification.md``), finds and creates
the vault, and commits machine writes under a dedicated identity so authorship
stays detectable. It runs on the core install — no extra.

This first release (PRD 00074) ships the spec engine, the vault contract, the
git layer, and five commands. Ingest, operator assets, and the autonomous
maintain loop land in later PRDs.

The vault root
--------------

Every path inside a zettel or source document is relative to a **root**. klyreon
resolves the root as:

1. ``$KLYREON_ROOT`` (wins outright — used for test isolation), else
2. the ``root`` key in ``$XDG_CONFIG_HOME/klyreon/config.yaml`` (falling back to
   ``~/.config/klyreon/config.yaml``).

A relative root, a missing root directory, or a missing config file fails loudly
and creates nothing. Paths containing ``..`` or escaping the root are rejected.

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Setting
     - Default
     - Description
   * - ``backend``
     - ``claude``
     - LLM backend for later autonomous PRDs.
   * - ``model``
     - (unset)
     - Optional model override.
   * - ``max_sources_per_run``
     - ``5``
     - Ingest cap (PRD B).
   * - ``source_timeout_seconds``
     - ``900``
     - Per-source ingest timeout (PRD B).
   * - ``max_zettel_body_lines``
     - ``60``
     - Oversized-body lint threshold.
   * - ``maintenance_window_days``
     - ``7``
     - Staleness window for the maintenance warning.
   * - ``pruning_enabled``
     - ``false``
     - Whether pruning deletes (PRD D).
   * - ``prune_window_days``
     - ``365``
     - Prune candidate window (PRD D).
   * - ``git_identity_name``
     - ``klyreon``
     - Author name on machine commits.
   * - ``git_identity_email``
     - ``klyreon@localhost``
     - Author email on machine commits.

Settings layer CLI > env (``BUVIS_KLYREON_*``) > YAML config > defaults. The
vault root is **not** a setting — it lives in klyreon's own config file so every
tool finds the vault the same way.

Commands
--------

.. code-block:: bash

    klyreon init [PATH]                      # create the vault skeleton + config
    klyreon init . --force                   # repoint an existing config here
    klyreon new --title "A thesis" --type note --concept-type thesis
    klyreon new --title "ripgrep tip" --type snippet
    klyreon validate                         # exit 1 on any error, 0 when clean
    klyreon validate --json                  # machine-readable report (stdout)
    klyreon export-claims                     # claim index JSON to stdout
    klyreon export-claims --out ~/claims.json # refused if under the vault root
    klyreon status                           # vault dashboard, computed on demand

- ``init`` is idempotent and never runs ``git init``; it warns when the root is
  not a git work tree.
- ``new`` allocates a collision-free 14-digit id; a concept zettel gets
  ``assent: tentative``, ``lifecycle: fleeting``, ``processed: false`` and a
  starter claim; a utility zettel gets none of those.
- ``validate`` runs every mechanical check (file-level + graph-level, including
  the transitive-relation cycle check).
- ``export-claims`` includes claims on ``assent: rejected`` zettels, labelled.
- ``status`` warns when maintenance is stale (every command does).
