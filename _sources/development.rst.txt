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

Build and install from a temp dir to avoid corrupting the source tree:

.. code-block:: bash

    uv build --out-dir /tmp/gems-test && uv tool install --force --from "/tmp/gems-test/$(ls /tmp/gems-test/buvis_gems-*.whl | head -1 | xargs basename)[all]" buvis-gems

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

``mise`` adds ``dev/bin`` to PATH. Tags with ``rc`` publish to TestPyPI; stable tags go to PyPI.
