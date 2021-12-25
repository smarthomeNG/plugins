modbus_tcp
=====================================================
SmarthomeNG plugin, zum Lesen von Register über ModBusTCP

Anforderungen
-------------
* Python > 3.6
* pip install pymodbus
* SmarthomeNG >= 1.8.0

Konfiguration
-------------

plugin.yaml
~~~~~~~~~~~

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


items.yaml
~~~~~~~~~~

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


logic.yaml
~~~~~~~~~~

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


Funktionen
~~~~~~~~~~

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


Beispiele
---------
Beispiel für SH-Item's

siehe example.yaml

mydevice:
    geraetename:
        type: str
        value: ''
        modBusAddress: 40030
        modBusDataType: 'string16'        #(optional) default: uint16  
        #modBusFactor: '1000'               #(optional) default: 1
        modBusByteOrder: 'Endian.Little'   #(optional) default: 'Endian.Big'
        modBusWordOrder: 'Endian.Little'   #(optional) default: 'Endian.Big'
    leistung_AC:
        type: num
        value: '0'
        modBusAddress: 40048
        #modBusDataType: 'uint16'        #(optional) default: uint16  
        modBusFactor: '0.001'           #(optional) default: 1
        modBusByteOrder: 'Endian.Little'   #(optional) default: 'Endian.Big'
        modBusWordOrder: 'Endian.Little'   #(optional) default: 'Endian.Big'
    leistung_DC:
        type: num
        value: ''
        modBusAddress: 40050
        modBusDataType: 'int16'         #(optional) default: uint16  
        modBusFactor: '0.001'           #(optional) default: 1
        modBusByteOrder: 'Endian.Little'   #(optional) default: 'Endian.Big'
        modBusWordOrder: 'Endian.Little'   #(optional) default: 'Endian.Big'
    temperatur:
        type: num
        value: ''
        modBusAddress: 40052
        modBusDataType: 'float32        #(optional) default: uint16  
        #modBusFactor: '1'               #(optional) default: 1
        modBusByteOrder: 'Endian.Little'   #(optional) default: 'Endian.Big'
        modBusWordOrder: 'Endian.Little'   #(optional) default: 'Endian.Big'

Changelog
---------
V1.0.1     slaveUnit zu plugin-Paramter hinzugefügt
V1.0.0     Initial plugin version


Web Interface
-------------

Das Plugin kann aus dem Admin Interface aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

.. image:: assets/tab1_readed.png
   :class: screenshot 