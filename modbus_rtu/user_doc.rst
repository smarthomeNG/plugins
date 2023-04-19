.. index:: modbus_rtu plugin
.. index:: Plugins; modbus_rtu

==========
modbus_rtu
==========

SmarthomeNG plugin, zum Lesen von Register über ModBusRTU. Das Plugin wurde vom modbus_tcp Plugin übernommen und angepasst.
Danke an die Entwickler von modbus_tcp.

Anforderungen
-------------
* Python > 3.6
* pymodbus >= 3.0.2
* SmarthomeNG >= 1.8.0

pymodbus
~~~~~~~~
das Paket sollte automatisch von SH installiert werden.

pymodbus - manuelle Installation:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: shell-session

    pip install pymodbus

Konfiguration
-------------

plugin.yaml
~~~~~~~~~~~

.. code-block:: yaml

    test:
        plugin_name: modbus_rtu
        instance: test
        tty: '/dev/ttyUSB0'
        baud: 9600
        cycle: 60
        parity: None
        stopbits: 1

* 'instance' = Name der Instanz, sollen mehrere Geräte angesprochen werden (Multiinstanz)

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


items.yaml
~~~~~~~~~~

.. code-block:: yaml

    Example_Read_Float:
        type: num
        visu_acl: ro
        database: init
        modBusRtuUnit: 1
        modBusRtuObjectType: InputRegister
        modBusRtuAddress: 98
        modBusRtuDataType: float32
        modBusRtuDirection: read

    Example_Write_Float:
        type: num
        visu_acl: rw
        cache: true
        modBusRtuUnit: 1
        modBusRtuObjectType: HoldingRegister
        modBusRtuAddress: 56
        modBusRtuDataType: float32
        modBusRtuDirection: write

    Example_Write_Bit:
        type: bool
        visu_acl: rw
        cache: true
        modBusRtuUnit: 1
        modBusRtuObjectType: Coil
        modBusRtuAddress: 3
        modBusRtuDataType: bit
        modBusRtuDirection: write

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


logic.yaml
~~~~~~~~~~

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


Funktionen
~~~~~~~~~~

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.
        

Changelog
---------

V1.0.0  Initial plugin version


Web Interface
-------------

Das Plugin kann aus dem Admin Interface aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.
