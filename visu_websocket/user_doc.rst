.. index:: Plugins; visu_websocket (Websocket Protokoll Unterstützung)
.. index:: visu_websocket

visu_websocket
##############

Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/visu_websocket` beschrieben.


Web Interface
=============

Das visu_websocket Plugin verfügt über ein Webinterface, mit dessen Hilfe die Clients die das Plugin nutzen
übersichtlich dargestellt werden.

.. important:: 

   Das Webinterface des Plugins kann mit SmartHomeNG v1.4.2 und davor **nicht** genutzt werden.
   Es wird dann nicht geladen. Diese Einschränkung gilt nur für das Webinterface. Ansonsten gilt 
   für das Plugin die in den Metadaten angegebene minimale SmartHomeNG Version.


Aufruf des Webinterfaces
------------------------

Das Plugin kann aus dem backend aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

Außerdem kann das Webinterface direkt über ``http://smarthome.local:8383/visu_websocket`` bzw. 
``http://smarthome.local:8383/visu_websocket<Instanz>`` aufgerufen werden.


Beispiele
---------

Folgende Informationen können im Webinterface angezeigt werden:

Oben rechts werden allgemeine Parameter zum Plugin angezeigt. 

Im unteren Teil Tab werden Informationen zu den Clients angezeigt, die das Plugin nutzen.

.. image:: assets/webif1.jpg
   :class: screenshot


