.. index:: Plugins; KNX (KNX Bus Unterstützung)
.. index:: KNX

knx
###

Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/knx` beschrieben.


Webinterface
============

Das Plugin Webinterface kann aus dem Admin Interface aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

Außerdem kann das Webinterface direkt über ``http://smarthome.local:8383/knx`` bzw.
``http://smarthome.local:8383/knx_<Instanz>`` aufgerufen werden.

Folgende Informationen können im Webinterface angezeigt werden:

Oben rechts werden allgemeine Parameter zum Plugin angezeigt.

Im Webinterface werden unter dem ersten Tab  die Items die das Plugin nutzen übersichtlich dargestellt:

.. image:: assets/tab1_knx_items.png
   :class: screenshot


Der zweite TAB zeigt Statistiken zu den Gruppenadressen:

.. image:: assets/tab2_ga_statistics.png
   :class: screenshot

Der dritte TAB zeigt Statistiken zu den physikalischen Adressen:

.. image:: assets/tab3_pa_statistics.png
   :class: screenshot

Mit der neuesten Release ist noch die Möglichkeit dazugekommen über das Webinterface eine Projektdatei aus der ETS hochzuladen.
Kompatibel sind Exportdateien aus der ETS5 (\*.knxproj) oder ETS4 (\*.esf = OPC).
Wenn eine gültige Datei hochgeladen wurde, so wird ein vierter TAB angezeigt.
Hier wird dann der Vergleich zwischen den definierten Gruppenadressen aus der ETS mit den in SmartHomeNG konfigurierten 
Items und deren knx spezifischen Attributen dargestellt. 
Gibt es eine Gruppenadresse, die in der ETS definiert wurde aber keine Entsprechung in SmartHomeNG hat,
so erscheint in der rechten Spalte *nicht zugewiesen*.

.. image:: assets/tab4_project.png
   :class: screenshot

Alle Tabellen im Webinterface haben rechts oben eine Filter- bzw. Suchmöglichkeit vorgesehen. 
Damit lassen sich die angezeigten Daten begrenzen. So kann z.B. gezielt nach bestimmten 
Gruppenadressen, Attributen oder nicht zugewiesenen Gruppenadressen  gesucht werden.

.. important::

   Das Webinterface des Plugins kann mit SmartHomeNG v1.4.2 und davor **nicht** genutzt werden.
   Es wird dann nicht geladen. Diese Einschränkung gilt nur für das Webinterface. Ansonsten gilt
   für das Plugin die in den Metadaten angegebene minimale SmartHomeNG Version.

