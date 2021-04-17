.. index:: Plugins; Casambi (Casambi Unterstützung)
.. index:: Casambi

========
casambi
========

Casambi plugin, mit Unterstützung für Casambi Produkte und Occhio Air.

Gateway plugin for controlling and reading Casambi devices via the Casambi backend API.
Casambi devices are based on Bluetooth Low Energy (BLE) radio and integrated into many products such as
Occhio lights.

Official Casambi API documentation: 
https://developer.casambi.com/


Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/casambi` beschrieben.

Gateway Hardware
=============

According to the Casambi concept, a mobile device (cell phone or tablet) is used as hardware gateway between local 
BLE network and Casambi backend. 

Requirements
=============

The plugin needs a valid Casambi API key which can be obtained from Casambi under: 
support@casambi.com


Beispiele
=============

Example for dimmer (Occhio Sento) with dimming and additional up/down fading feature.
Item tree:

    readinglight:
        casambi_id: 2
        enforce_updates: True
        
        light:
            type: bool
            casambi_rx_key: ON
            casambi_tx_key: ON
            visu_acl: rw
            enforce_updates: True

            level:
                type: num
                value: 0
                casambi_rx_key: DIMMER
                casambi_tx_key: DIMMER
                visu_acl: rw
                enforce_updates: True

            vertical:
                type: num
                value: 0
                casambi_rx_key: VERTICAL
                casambi_tx_key: VERTICAL
                visu_acl: rw
                enforce_updates: True




Web Interface
=============

Das casambi Plugin verfügt über ein Webinterface, auf dem die Casambi items dargestellt werden.

.. important::

   Das Webinterface des Plugins kann mit SmartHomeNG v1.4.2 und davor **nicht** genutzt werden.
   Es wird dann nicht geladen. Diese Einschränkung gilt nur für das Webinterface. Ansonsten gilt
   für das Plugin die in den Metadaten angegebene minimale SmartHomeNG Version.


Aufruf des Webinterfaces
------------------------

Das Plugin kann aus dem Admin Interface aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

Außerdem kann das Webinterface direkt über ``http://smarthome.local:8383/casambi`` aufgerufen werden.


Beispiele
---------

Folgende Informationen können im Webinterface angezeigt werden:

Oben rechts werden allgemeine Parameter zum Plugin wie die Verbindung zum Casambi Backend und die Anzahl der gefundenen Casambi Netzwerke angezeigt.

Im ersten Tab werden die Items angezeigt, die das Casambi Plugin nutzen:

.. image:: assets/webif1.jpg
   :class: screenshot

