Development
===========

Setup
-----

.. code-block:: bash

    uv sync --all-groups --all-extras
    pre-commit install
    uv run pytest
    uv run mypy src/lib/ src/tools/

Local Testing
-------------

Build a ``.devN`` wheel (N = commits since version tag) and install it:

.. code-block:: bash

    release local                          # build + install as e.g. 0.3.2.dev3
    release --dry-run local                # preview version without building

This bypasses mise but installs to the same ``~/.local/bin``. After testing, restore the mise-managed version:

.. code-block:: bash

    mise install --force "pipx:buvis-gems"

Release
-------

.. code-block:: bash

    release patch|minor|major              # bump, tag, push → CI publishes to PyPI
    release --pre rc1                      # pre-release current version to TestPyPI
    release --pre rc1 minor                # bump + pre-release to TestPyPI
    release                                # after rc: strip suffix, release stable to PyPI
    release --dry-run [--pre rc1] [patch]  # preview without changes

``mise`` adds ``dev/bin`` to PATH. Tags with ``rc`` publish to TestPyPI; stable tags go to PyPI.
