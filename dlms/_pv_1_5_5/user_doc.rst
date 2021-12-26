.. index:: Plugins; DLMS (Auslesung von Smartmetern via DLMS)
.. index:: DLMS

dlms
####

Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/dlms` beschrieben.


Web Interface
=============

Das dlms Plugin verfügt über ein Webinterface, mit dessen Hilfe die Items die das Plugin nutzen
übersichtlich dargestellt werden. 

.. important:: 

   Das Webinterface des Plugins kann mit SmartHomeNG v1.4.2 und davor **nicht** genutzt werden.
   Es wird dann nicht geladen. Diese Einschränkung gilt nur für das Webinterface. Ansonsten gilt 
   für das Plugin die in den Metadaten angegebene minimale SmartHomeNG Version.


Aufruf des Webinterfaces
------------------------

Das Plugin kann aus dem backend aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

Außerdem kann das Webinterface direkt über ``http://smarthome.local:8383/dlms`` bzw. 
``http://smarthome.local:8383/dlms_<Instanz>`` aufgerufen werden.


Beispiele
---------

Folgende Informationen können im Webinterface angezeigt werden:

Oben rechts werden allgemeine Parameter zum Plugin angezeigt. 

Im ersten Tab wird das Ergebnis der letzten Auslesung angezeigt:

.. image:: assets/webif1.png
   :class: screenshot

Im zweiten Tab werden items aufgelistet, die mit Informationen aus der letzten Auslesung befüllt werden:

.. image:: assets/webif2.png
   :class: screenshot
