.. index:: Plugins; Casambi (Casambi Unterstützung)
.. index:: Casambi

========
casambi
========

Casambi plugin, mit Unterstützung für Casambi Produkte und Occhio Air.

Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/casambi` beschrieben.


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

