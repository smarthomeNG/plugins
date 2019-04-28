.. index:: Plugins; squeezebox
.. index:: squeezebox

squeezebox
##########

Konfiguration
=============

.. important::

      Detaillierte Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/squeezebox` zu finden.


.. code-block:: yaml

    # etc/plugin.yaml
    squeezebox:
        plugin_name: squeezebox
        #host: 127.0.0.1
        #port: 9090
        #web_port: 9000

Kommandos
=========

Die Kommandos sind der technischen Logitech Dokumentation zum **Command Line Interface** zu entnehmen. Folgende Platzhalter können genutzt werden:
- <playerid>: Wird durch die im Parent-Item gesetzte Player-ID ersetzt
- {}: Der Wert des Items wird in diesen Platzhalter geschrieben (sollte nicht verwendet werden, wenn ein fixer oder kein Wert nötig ist).

Sämtliche Kommandos sollten manuell über die Telnet-Schnittstelle auf Port 9090 getestet werden.
Für Abfragen muss hierbei ein "?" am Ende des Befehls stehen, z.B. "<playerid> name ?.
Dieses Fragezeichen kann bei squeezebox_init Befehl weggelassen werden, da es vom Plugin hinzugefügt wird.


Struct Vorlagen
===============

Ab smarthomeNG 1.6 können Vorlagen aus dem Plugin einfach eingebunden werden. Dabei stehen folgende Vorlagen zur Verfügung:

- database: Datenbank-spezifische Kommandos wie Rescan, etc. sowie Statistikabfragen wie Anzahl Interpreten, Alben, etc.
- server: Server-spezifische Kommandos zum Abfragen der Alarmplaylisten und Anzahl angemeldeter Player
- player: Player-spezifische Kommandos wie Display, Power, Sync, Alarm, etc.
- info: Song-spezifische Kommandos zum Abfragen von Informationen zum aktuell gespielten Song wie Album, Interpret, Genre, Dauer, etc.
- controls: Abspiel-spezifische Kommandos wie Play, Stop, Skip, Spulen, Lautstärke, etc.
- playlist: Abspielliste-spezifische Kommandos wie Hinzufügen zu einer oder Abspeichern von einer Playliste, etc.
