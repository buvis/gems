.. _tool-sysup:

sysup
=====

System update tools. Run platform-specific package and tooling updates.

Commands
--------

sysup mac
~~~~~~~~~

Run macOS system and tooling updates. Only available on macOS.

Steps run in order: brew, npm-check, pip, uv tools, helm repos, and mise
last — mise upgrade deletes replaced tool version directories that the
shell's PATH still points at, so it must not run before the other lookups.

The run caches sudo credentials first (one upfront password prompt, kept
fresh in the background) so brew cask installs don't stop for a password
mid-flight. Declining the prompt is fine; steps that need sudo will then
prompt on their own as before.

The helm step updates repos only when ``helm repo list`` shows at least
one; an empty list reports a clean skip instead of helm's "no repositories
found" error.

.. code-block:: bash

    sysup mac

sysup pip
~~~~~~~~~

Upgrade pip and outdated packages in every mise-managed Python (falls back
to the ``python3`` on PATH when mise is absent). Interpreters without pip,
such as uv-built venvs, are reported and skipped.

.. code-block:: bash

    sysup pip

sysup wsl
~~~~~~~~~~

Run WSL/Linux package updates. Only available on Linux.

.. code-block:: bash

    sysup wsl

sysup nvim
~~~~~~~~~~

Update Neovim plugins, mason tools, and treesitter parsers headlessly.

Runs three steps in order:

1. ``Lazy! sync`` to update lazy.nvim plugins.
2. ``MasonToolsUpdateSync`` to install and update mason packages (blocking).
3. ``TSUpdateSync`` to update nvim-treesitter parsers.

Requires a Neovim config using lazy.nvim, mason.nvim, mason-tool-installer.nvim,
and nvim-treesitter. Safe to run during dotfiles bootstrap.

.. code-block:: bash

    sysup nvim

The mason step reports per-tool status. After ``MasonToolsUpdateSync`` finishes,
it checks every name in ``mason-tool-installer``'s ``ensure_installed`` list
against ``mason-registry``. If any expected tool is not installed, the step
fails with the tool names and a tail of ``mason.log`` (last ~200 lines, capped
at 8 KiB) so the underlying install error is visible. If ``mason-registry`` or
``mason-tool-installer`` cannot be loaded, the step succeeds with an
``INCONCLUSIVE`` note rather than failing.
