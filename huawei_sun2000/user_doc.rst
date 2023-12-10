.. index:: Plugins; huawei_sun2000
.. index:: huawei_sun2000

==============
huawei_sun2000
==============

SmartHomeNG - Plugin zur Einbindung der Huawei SUN2000 Wechselrichterserie, sowie angebundener Speicher.


Anforderungen
=============

Notwendige Software
-------------------

* python >= 3.10
* huawei-solar >= 2.2.9
* pymodbus, Version abhängig von der verwendeten huawei-solar - Version

Unterstützte Geräte
-------------------

* getestet mit Huawei SUN2000-10KTL-M1
* getestet mit Huawei LUNA2000-15-S0
* weitere Wechselrichter der SUN2000-Serie und LUNA2000-Serie sollten funktionieren

Konfiguration
=============

Die Plugin Parameter und die Informationen zur Item-spezifischen Konfiguration des Plugins sind
unter :doc:`/plugins_doc/config/sample` beschrieben.

plugin.yaml
-----------

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


items.yaml
----------

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


logic.yaml
----------

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


Funktionen
----------

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.

|

Beispiele
=========

Hier können ausführlichere Beispiele und Anwendungsfälle beschrieben werden. (Sonst ist der Abschnitt zu löschen)

|

Web Interface
=============

Die Datei ``dev/sample_plugin/webif/templates/index.html`` sollte als Grundlage für Webinterfaces genutzt werden. Um Tabelleninhalte nach Spalten filtern und sortieren zu können, muss der entsprechende Code Block mit Referenz auf die relevante Table ID eingefügt werden (siehe Doku).

SmartHomeNG liefert eine Reihe Komponenten von Drittherstellern mit, die für die Gestaltung des Webinterfaces genutzt werden können. Erweiterungen dieser Komponenten usw. finden sich im Ordner ``/modules/http/webif/gstatic``.

Wenn das Plugin darüber hinaus noch Komponenten benötigt, werden diese im Ordner ``webif/static`` des Plugins abgelegt.

|

Version History
===============

0.2.0
- grundlegende Funktionen sind implentiert


