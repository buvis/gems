.. _tool-pinger:

pinger
======

ICMP ping utilities. Waits for a host to come online.

**Extra:** ``uv tool install buvis-gems[pinger]``

Configuration
-------------

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
--------

pinger wait
~~~~~~~~~~~

Poll a host with ICMP until it responds or timeout is reached.

.. code-block:: bash

    pinger wait 192.168.1.1
    pinger wait nas.local -t 120

Options:

- ``-t, --timeout INTEGER`` — give up after N seconds (overrides setting)
