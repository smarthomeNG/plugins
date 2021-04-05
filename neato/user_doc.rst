.. index:: Plugins; Neato (Neato und Vorwerk Unterstützung)
.. index:: Neato

=============
neato/vorwerk
=============

Neato plugin, mit Unterstützung für Neato und Vorwerk Saugroboter.

Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/neato` beschrieben.


Web Interface
=============

Das neato Plugin verfügt über ein Webinterface, um  für Vorwerk Saugroboter das OAuth2 Authentifizierungsverfahren direkt durchzuführen und bei Bedarf
den erhaltenen Token direkt in die Konfiguration (plugin.yaml) zu uebernehmen.

.. important::

   Das Webinterface des Plugins kann mit SmartHomeNG v1.4.2 und davor **nicht** genutzt werden.
   Es wird dann nicht geladen. Diese Einschränkung gilt nur für das Webinterface. Ansonsten gilt
   für das Plugin die in den Metadaten angegebene minimale SmartHomeNG Version.


Aufruf des Webinterfaces
------------------------

Das Plugin kann aus dem Admin Interface aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

Außerdem kann das Webinterface direkt über ``http://smarthome.local:8383/neato`` aufgerufen werden.


Beispiele
---------

Folgende Informationen können im Webinterface angezeigt werden:

Im ersten Tab Vorwerk OAuth2 findet sich direkt die Schritt fuer Schritt Anleitung zur OAuth2 Authentifizierung. Achtung: Diese wird aktuell nur von Vorwerk Robotern unterstuetzt:

.. image:: assets/webif1.jpg
   :class: screenshot

