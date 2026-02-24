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

Re-running a Failed Release
^^^^^^^^^^^^^^^^^^^^^^^^^^^

If CI fails after a release tag was pushed (e.g. a lint error), fix the issue on master, then move the tag to the latest commit and force-push it:

.. code-block:: bash

    git tag -f gems-vX.Y.Z
    git push origin gems-vX.Y.Z --force

This re-triggers the publish workflow on the new commit.

Installing Pre-releases
-----------------------

To install a release candidate from TestPyPI:

.. code-block:: bash

    uv tool install "buvis-gems[all]==X.Y.Zrc1" \
        --extra-index-url https://test.pypi.org/simple/

Replace ``X.Y.Zrc1`` with the actual version (e.g. ``0.4.0rc1``).

To go back to the stable release:

.. code-block:: bash

    uv tool install --force buvis-gems[all]
