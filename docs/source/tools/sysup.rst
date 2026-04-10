.. _tool-sysup:

sysup
=====

System update tools. Run platform-specific package and tooling updates.

Commands
--------

sysup mac
~~~~~~~~~

Run macOS system and tooling updates. Only available on macOS.

.. code-block:: bash

    sysup mac

sysup pip
~~~~~~~~~

Upgrade pip and outdated Python packages.

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
