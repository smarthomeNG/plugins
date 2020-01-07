Solarlog
========

Dieses Plugin kann eine Webseite vom SolarLog-Protokolliergerät lesen und Werte zurückgeben.
Es wurde 2013 von Niko Will erstellt und 2019 von Bernd Meiners zu einem SmartPlugin umgebaut.

Requirements
------------

Dieses Plugin hat keine Anforderungen oder Abhängigkeiten, arbeitet jedoch mit SolarLog und
Firmware <= 2.x zusammen.
Neuere SolarLog-Geräte mit Firmware> = 3.x sollten nur nach JSON-Daten abgefragt werden,
die innerhalb einer Logik analysiert werden können.

Todo
----

Webinterface mit den geparsten Daten aufbereiten

Konfiguration
-------------

plugin.yaml
~~~~~~~~~~~

.. code-block:: yaml
   :caption: logic.yaml

   Solarlog:
       plugin_name: solarlog
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

solarlog
^^^^^^^^

Dies ist das einzige Attribut für Items. Um Werte aus dem SolarLog-Datenformat abzurufen,
müssen lediglich die Variablennamen wie auf der oben beschriebenen Site verwendet werden.

Wenn Sie Werte aus einer Array-Struktur wie den PDC-Wert aus dem Sekundenstring des ersten Inverters verwenden möchten, müssen Sie den Variablennamen underscore inverter-1 underscore string-1 verwenden:

var [\ _ inverter [\ _ string]]

In diesem Beispiel sollten Details zur Verwendung erläutert werden:

.. code :: yaml

    pv:

        pac:
            type: num
            solarlog: Pac
            database: yes

        kwp:
            type: num
            solarlog: AnlagenKWP

            soll:
                type: num
                solarlog: SollYearKWP

        inverter1:

            online:
                type: bool
                solarlog: isOnline

            inverter1_pac:
                type: num
                solarlog: pac_0
                database: yes

            out:
                type: num
                solarlog: out_0
                database: yes

            string1:

                string1_pdc:
                    type: num
                    solarlog: pdc_0_0
                    database: yes

                string1_udc:
                    type: num
                    solarlog: udc_0_0
                    database: yes

            string2:

                string2_pdc:
                    type: num
                    solarlog: pdc_0_1
                    database: yes

                string2_udc:
                    type: num
                    solarlog: udc_0_1
                    database: yes


Das `` database: yes`` impliziert, dass auch ein Datenbank-Plugin konfiguriert ist.
Dienst zur Anzeige von Messwerten innerhalb einer Visu.

logic.yaml
~~~~~~~~~~

Derzeit gibt es keine Logik Konfiguration für dieses Plugin.

Funktionen
----------

Momentan werden von diesem Plugin keine Funktionen bereitgestellt.