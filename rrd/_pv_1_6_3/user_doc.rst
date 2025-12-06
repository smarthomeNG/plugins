.. index:: Plugins; rrd
.. index:: rrd

===
rrd
===

Das `RRDTool <https://oss.oetiker.ch/rrdtool/>`_  ist ein weitverbreitetes Tool um Zeitreihen von Messdaten aufzuzeichnen.
Dieses Plugin stellt die Möglichkeit bereit Itemwerte an das RRDTool weiterzugeben.

Anforderungen
=============

Notwendige Software
-------------------

Das Paket Rrdtool und die entsprechenden Python Libraries müssen installiert sein.

.. code:: bash

    sudo apt-get install librrd-dev libpython3-dev


Vergleich zwischen Datenbank-Plugin, InfluxDB und rrdtool:
----------------------------------------------------------

RRD
+ ein stabiles, zuverlässiges Werkzeug
+ wird in vielen Datenprotokollierungs- und Grafiktools verwendet
- zähe Weiterentwicklung in den letzten Jahren
- Werte werden nur in bestimmten Abständen aufgezeichnet und nicht dann, wenn eine Änderung eintritt

Datenbank-Plugin
+ Unterstützung für viele verschiedene Datenbanken wie SQLite, MySQL/MariaDB usw.
+ genaue Protokollierung der Änderungszeiten
+ mehr Analysefunktionalität
+ im SmartHomeNG Kern gut integriert
- keine einstellbare Datenreduktion, nur Zeitbegrenzung der Aufzeichnung

InfluxDB-Plugin
+ Unterstützung für Influx Datenbank
+ speziell entwickelt für Zeitreihen
+ genaue Protokollierung der Änderungszeiten
+ unter Verwendung von Grafana sehr gute Analysefunktionalität
+ Datenreduktion voreinstellbar

Das RRD-Plugin und das Datenbank-Plugin können nur dann zusammen für ein Item verwendet werden,
wenn beim RRD Plugin die Bereitstellung der Series Funktion unterdrückt wird.


Konfiguration
=============

Die Plugin Parameter und die Informationen zur Item-spezifischen Konfiguration des Plugins sind
unter :doc:`/plugins_doc/config/rrd` beschrieben.


Funktionen
----------

Das Plugin stellt für jedes Item das für die Verwendung mit dem Plugin konfiguriert wurde eine Datenbankfunktion bereit.

``sh.item.db(function, start, end='now')``

Diese Funktion liefert Werte unter Berücksichtigung der nachfolgend erläuterten Funktion und dem Zeitrahmen ``start`` und ``end``.

Unterstützte Funktionen für die Datenaufbereitung sind:

   * `avg`: Durchschnittswert
   * `max`: Maximalwert
   * `min`: Minimalwert
   * `last`: Letzter eingetragener Wert

Für das Zeitintervall müssen *relative* Anfangs- und Endzeitpunkte zum aktuellen Zeitpunkt angegeben werde.
Der Vorgabewert für das Ende ist ``now`` was einer relativen Verschiebung um ``0`` entspricht.

Die relativen Start- und Endzeitpunkte werden definiert durch ``<Nummer><Intervalleinheit>``
Für die Intervalleinheit können folgende Kennzeichnungen verwendet werden:

   * `i`: minute
   * `h`: hour
   * `d`: day
   * `w`: week
   * `m`: month
   * `y`: year


Beispiele
=========

.. code-block:: yaml

    Aussen:
        name: Aussen
        Temperatur:
            type: num
            rrd: init
            rrd_min: 'yes'
            rrd_max: 'yes'

    Wohnzimmer:
        Temperatur:
            type: num
            rrd: 'yes'

    Versorgung:
        Wasser:
            type: num
            rrd_type: counter

Um das Minimum der letzten 24 Stunden zu ermitteln:

.. code-block:: python

    sh.Aussen.Temperatur.db('min', '1d')

Um die Durchschnittstemperatur einer Woche zu ermitteln die vor genau 7 Tagen endete:

.. code-block:: python

    sh.Aussen.Temperatur.db('avg', '2w', '1w')


Web Interface
=============

Aktuell hat das Plugin kein Webinterface
