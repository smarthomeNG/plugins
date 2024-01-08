.. index:: Plugins; byd_bat
.. index:: byd_bat

=======
byd_bat
=======

.. image:: webif/static/img/plugin_logo.png
   :alt: plugin logo
   :width: 300px
   :height: 300px
   :scale: 50 %
   :align: left

Anzeigen von Parametern eines BYD Energiespeichers. Die Parameter entsprechen den Daten, die in der Software Be_Connect_Plus_V2.0.2 angezeigt werden.

Es werden 1-3 Türme unterstützt.

Die Grunddaten werden alle 60 Sekunden aktualisiert. Die Diagnosedaten werden beim Start des Plugin und gemäss dem Parameter 'diag_cycle' abgerufen.

Die Spannungen und Temperaturen in den Modulen werden mit Hilfe von Heatmaps dargestellt. Diese werden im Web Interface angezeigt. Zusätzlich können diese Bilder auch in ein weiteres Verzeichnis kopiert werden (z.Bsp. für smartvisu).

Das Plugin benoetigt nur ein Item mit der folgenden Deklaration:

.. code-block:: yaml

    byd:
        struct: byd_bat.byd_struct

Alle verfügbaren Daten werden im Struct 'byd_struct' bereitgestellt. Diverse Parameter besitzen bereits die Eigenschaft 'database: init', so dass die Daten für die Visualisierung bereitgestellt werden.

Anforderungen
=============

Der BYD Energiespeicher muss mit dem LAN verbunden sind. Die IP-Adresse des BYD wird über DHCP zugewiesen und muss ermittelt werden. Diese IP-Adresse muss in der Plugin-Konfiguration gespeichert werden.

Notwendige Software
-------------------

* matplotlib

Unterstützte Geräte
-------------------

Folgende Typen werden unterstützt:

* HVS (noch nicht getestet)
* HVM (getestet mit HVM 19.3kWh und 2 Türmen)
* HVL (noch nicht getestet)
* LVS (noch nicht getestet)

Bitte Debug-Daten (level: DEBUG) von noch nicht getesteten BYD Energiespeichern an Plugin-Autor senden. Beim Start von smarthomeng werden die Diagnosedaten sofort ermittelt.

Konfiguration
=============

Detaillierte Information sind :doc:`/plugins_doc/config/byd_bat` zu entnehmen.


Web Interface
=============

Ein Web Interface ist implementiert und zeigt die eingelesenen Daten an.

Beispiele
=========

Oben rechts werden die wichtigsten Daten zum BYD Energiespeicher angezeigt.

Im Tab "BYD Home" sind die Grunddaten des Energiespeichers dargestellt:

.. image:: assets/home.png
   :class: screenshot

Im Tab "BYD Diagnose" werden Diagnosedaten angezeigt:

.. image:: assets/diag.png
   :class: screenshot

Im Tab "BYD Spannungen" werden die Spannungen der Module als Heatmap angezeigt:

.. image:: assets/volt.png
   :class: screenshot

Im Tab "BYD Temperaturen" werden die Temperaturen der Module als Heatmap angezeigt:

.. image:: assets/temp.png
   :class: screenshot
