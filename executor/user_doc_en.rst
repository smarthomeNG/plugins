.. index:: Plugins; executor
.. index:: executor

========
executor
========

Introduction
============

The executor plugin is used to test **eval expressions** and **Python code** often used within **logics**.

.. important::

  Be aware that enabling this plugin might be a security risk if other person get access to the web interface
  one can control the whole SmartHomeNG beast. So be careful!!!

Configuration
=============

Activating the plugin is enough.

Example Eval
============

.. code-block:: python

    12 if 23 % 3 == 5 else None

This will return **None**

.. code-block:: python

    sh..child() + 4

As the eval term contains relative item declaration it is necessary to define the item path of the item containing the referred child item.

Example Python Code
===================

A mockup of ``logger`` and ``print`` should work for output. The intention is that most parts of a logic can be copied and pasted here from a logic for test purposes.

Test the logger

.. code-block:: python

    logger.warning("Eine Warnung")
    logger.info("Eine Info")
    logger.debug("Eine Debugmeldung")
    logger.error("Eine Debugmeldung")


Print Series Data for an item

Deal with data from database plugin for an item <your item here>:

.. code-block:: python

    import json

    def myconverter(o):
        import datetime
        if isinstance(o, datetime.datetime):
          return o.__str__()
    data = sh.<your item here>.series('max','1d','now')
    pretty = json.dumps(data, default = myconverter, indent = 2, separators=(',', ': '))
    print(pretty)


would result in

.. code-block:: json

    {
      "sid": "ArbeitszimmerOG.Raumtemperatur|max|1d|now|100",
      "cmd": "series",
      "update": "2019-11-09 17:54:22.205668+01:00",
      "params": {
        "sid": "ArbeitszimmerOG.Raumtemperatur|max|1d|now|100",
        "update": true,
        "start": 1573317598203,
        "end": "now",
        "func": "max",
        "item": "ArbeitszimmerOG.Raumtemperatur",
        "step": 864000
      },
      "series": [
        [
          1573231198203,
          21.0
        ],
        [
          1573232535421,
          21.2
        ]
      ]
    }
