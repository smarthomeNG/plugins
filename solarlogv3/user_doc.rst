Solarlog
========

Dieses Plugin kann eine Webseite vom SolarLog-Protokolliergerät lesen und Werte zurückgeben.
Es wurde 2013 von Niko Will erstellt und 2019 von Bernd Meiners zu einem SmartPlugin umgebaut.
Es wurde 2017 von klab für SolarLog-Geräte mit Firmware >= 3.x neu geschrieben und 2020 von
Christian Michels in das alte Plugin integriert.

Requirements
------------

Dieses Plugin hat keine Anforderungen oder Abhängigkeiten, arbeitet jedoch mit SolarLog und
Firmware >= 3.x zusammen.

Todo
----

Webinterface mit den geparsten Daten aufbereiten

Konfiguration
-------------

plugin.yaml
~~~~~~~~~~~

.. code-block:: yaml
   :caption: logic.yaml

   SolarlogFw3:
       plugin_name: solarlogfw3
       host: http://solarlog.fritz.box/

Attribute
^^^^^^^^^

- `` host``: Gibt den Hostnamen des SolarLog an.
- `` cycle``: Bestimmt den Zyklus für die Abfrage des SolarLog.

items.yaml
~~~~~~~~~~

Die Format Details des SolarLog müssen bekannt sein, um die gültigen Werte für dieses Plugin zu definieren.
Das Plugin fordert lediglich die JavaScript-Dateien vom Gerät an und analysiert sie.
Ähnlich verhält es sich mit der Webseite, wenn die URL eines SolarLog im Browser aufgerufen wird.
Eine Beschreibung des Formats und der entsprechenden Variablen findet sich hier:
https://www.photonensammler.de/wiki/doku.php?id=solarlog_datenformat

solarlogfw3
^^^^^^^^

Dies ist das einzige Attribut für Items. Um Werte aus dem SolarLog-Datenformat abzurufen,
müssen lediglich die Variablennamen wie auf der oben beschriebenen Site verwendet werden.

Wenn Sie Werte aus einer Array-Struktur wie den PDC-Wert aus dem Sekundenstring des ersten Inverters verwenden möchten, müssen Sie den Variablennamen underscore inverter-1 underscore string-1 verwenden:

var [\ _ inverter [\ _ string]]

In diesem Beispiel sollten Details zur Verwendung erläutert werden:

.. code :: yaml
solarlog_v3:

    w_gesamt_zaehler:
        type: num
        cache: 'on'
        solarfw3: 101

    w_gesamt:
        type: num
        cache: 'on'
        solarfw3: 102

    spannung_ac:
        type: num
        cache: 'on'
        solarfw3: 103

    spannung_dc1:
        type: num
        cache: 'on'
        solarfw3: 104

    wh_heute:
        type: num
        solarfw3: 105
        cache: 'on'

    wh_gestern:
        type: num
        cache: 'on'
        solarfw3: 106

    wh_monat:
        type: num
        cache: 'on'
        solarfw3: 107

    wh_jahr:
        type: num
        cache: 'on'
        solarfw3: 108

    wh_gesamt:
        type: num
        cache: 'on'
        solarfw3: 109

    wp_generatorleistung:
        type: num
        cache: 'on'
        solarfw3: 116


logic.yaml
~~~~~~~~~~

Derzeit gibt es keine Logik Konfiguration für dieses Plugin.

Funktionen
----------

Momentan werden von diesem Plugin keine Funktionen bereitgestellt.
