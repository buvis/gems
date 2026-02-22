.. _tool-netscan:

netscan
=======

Network scanning tools. Discover hosts and SSH services on the local network.

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Setting
     - Default
     - Description
   * - ``interface``
     - ``en0``
     - Network interface to scan
   * - ``ssh_port``
     - ``22``
     - SSH port to check

Commands
--------

netscan hosts
~~~~~~~~~~~~~

Discover hosts on the local network.

.. code-block:: bash

    netscan hosts
    netscan hosts -i eth0

Options:

- ``-i, --interface TEXT`` — network interface to scan (overrides setting)

netscan ssh
~~~~~~~~~~~

Find hosts with SSH available.

.. code-block:: bash

    netscan ssh
    netscan ssh -i eth0 -p 2222

Options:

- ``-i, --interface TEXT`` — network interface to scan (overrides setting)
- ``-p, --port INTEGER`` — SSH port to scan (overrides setting)
