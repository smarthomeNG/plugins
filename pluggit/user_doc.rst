
.. index:: Plugins; pluggit
.. index:: pluggit Plugin

=======
pluggit
=======

.. image:: webif/static/img/plugin_logo.png
   :alt: plugin logo
   :width: 300px
   :height: 300px
   :scale: 50 %
   :align: left

Das pluggit plugin dient zur Ansteuerung einer Pluggit AP310 KWL.


.. Einführung
.. ==========

.. ...


Vorteile gegenüber der Plugin Version v1.2.3
============================================

- wesentlich mehr Parameter der pluggit können abgefragt werden
- einige Parameter lassen sich auch schreiben
- die Werte können intern auch konvertiert werden, sodass man eine vernünftige Ausgabe erhält


Es fehlen auch noch ein paar Dinge
==================================

- die Programmierung des Auto-Wochenprogramms ist noch nicht implementiert
- eine Dokumentation der Parameter


Anforderungen
=============

.. Anforderungen des Plugins auflisten. Werden spezielle Soft- oder Hardwarekomponenten benötigt?

Um das Plugin zu nutzen, muss eine InfluxDB Datenbank der Version 2.x installiert und zur Nutzung durch SmartHomeNG
konfiguriert sein.


.. Installation benötigter Software
.. ================================

Konfiguration
=============

Die Plugin Parameter und die Informationen zur Item-spezifischen Konfiguration des Plugins sind
unter :doc:`/plugins_doc/config/pluggit` nachzulesen.


Struct
======

Die zur Nutzung des Plugins benötigten Items können durch die Einbindung der struct **pluggit.pluggit** angelegt
werden.


.. Beispiele
.. ---------

.. Hier können ausführlichere Beispiele und Anwendungsfälle beschrieben werden.


.. Web Interface
.. =============

.. ...


Version History
===============

V2.0.3 - 25.10.2022
- Support für pymodbus 3.0

22.05.2022:
- Fehler mit manuellem Bypass behoben

16.02.2022:
- CurentUnitMode.ManualBypass dem Item-struct zugefügt
- Log-Level für verschiedene Ausgaben angepasst
- CurrentUnitMode.AwayMode repariert

24.02.2021:
- Item-struct um Zugriffe für SmartVISU erweitert
- item_attribut um pluggit_convert erweitert
- scheduler.remove eingebaut

29.08.2020:
 - bool-Werte konnten nicht geschrieben werden

