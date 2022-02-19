.. index:: Plugins; influxdb2
.. index:: influxdb2

=========
influxdb2
=========

.. image:: webif/static/img/plugin_logo.png
   :alt: plugin logo
   :width: 300px
   :height: 300px
   :scale: 50 %
   :align: left

InfluxDB ist ein Open Source Datenbankmanagementsystem (DBMS), speziell für Zeitreihen (engl. time series).
Es wird von der Firma InfluxData entwickelt und vertrieben.

Das influxdb2 Plugin ist eine Neuentwicklung, die auf InfluxDB v2.x aufsetzt. Soll noch eine alte InfluxDB
Software (v1.8 und davor) eingesetzt werden, kann dieses Plugin nicht verwendet werden.


Einführung
==========

...

Anforderungen
=============

.. Anforderungen des Plugins auflisten. Werden spezielle Soft- oder Hardwarekomponenten benötigt?

Um das Plugin zu nutzen, muss eine InfluxDB Datenbank der Version 2.x installiert und zur Nutzung durch SmartHomeNG
konfiguriert sein.


.. Installation benötigter Software
.. ================================

Installation der InfluxDB Software
==================================

In der Navigation links sind Seiten mit weiteren Informationen zu InfluxDB, der Installation und zur Konfiguration
der InfluxDB Software zur Nutzung mit SmartHomeNG verlinkt.

.. toctree::
  :hidden:

  user_doc/influxdb_einfuehrung.rst
  user_doc/influxdb_installation.rst
  user_doc/influxdb_konfiguration.rst


.. Unterstützte Geräte
.. -------------------
..
.. * die
.. * unterstütze
.. * Hardware
.. * auflisten


Konfiguration
=============

Die Konfiguration der InfluxDB Software ist weiter oben im Abschnitt **Installation der InfluxDB Software** beschrieben.

Die Plugin Parameter und die Informationen zur Item-spezifischen Konfiguration des Plugins sind
unter :doc:`/plugins_doc/config/influxdb2` nachzulesen.


Beispiele
---------

Hier können ausführlichere Beispiele und Anwendungsfälle beschrieben werden.


Web Interface
=============

Die Datei ``dev/sample_plugin/webif/templates/index.html`` sollte als Grundlage für Webinterfaces genutzt werden. Um Tabelleninhalte nach Spalten filtern und sortieren zu können, muss der entsprechende Code Block mit Referenz auf die relevante Table ID eingefügt werden (siehe Doku).

SmartHomeNG liefert eine Reihe Komponenten von Drittherstellern mit, die für die Gestaltung des Webinterfaces genutzt werden können. Erweiterungen dieser Komponenten usw. finden sich im Ordner ``/modules/http/webif/gstatic``.

Wenn das Plugin darüber hinaus noch Komponenten benötigt, werden diese im Ordner ``webif/static`` des Plugins abgelegt.
