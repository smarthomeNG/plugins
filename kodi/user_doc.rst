.. index:: Plugins; kodi
.. index:: kodi

kodi
####

Konfiguration
=============

.. important::

    Die Informationen zur Konfiguration des Plugins sind unter :doc:``/plugins_doc/config/kodi`` beschrieben.

.. code-block:: yaml

    # etc/plugin.yaml
    kodi:
        plugin_name: kodi
        host: 10.0.0.1
        #instance: kodi_one
        #autoreconnect: False
        #connect_retries: 10
        #connect_cycle: 5
        #send_retries: 5

Items
=====

kodi_item@[Instanz]: [Funktion]
-------------------------------
Folgende Funktionen werden aktuell unterstützt:
**on_off**
Item type ``bool``. Wird das Item auf "False" gesetzt, wird Kodi heruntergefahren. Bei einem "True" versucht das Plugin, eine Verbindung zu Kodi herzustellen (ohne Wake on LAN o.ä.)

**volume**
Item type ``num``. Einstellen der Lautstärke in Prozent, ein Wert zwischen 0 und 100.

**speed**
Item type ``num``. Einstellen der Abspielgeschwindigkeit. Muss einen gültigen geraden Wert enthalten, also zB 2, 4, etc. (oder 1 für Normalgeschwindigkeit)

**seek**
Item type ``num``. Zu einem bestimmten Punkt des aktuellen Mediums springen, in Prozent

**mute**
Item type ``bool``. Stummschalten.

**player**
Item type ``num``. Erhält automatisch die Player ID des aktuellen Players. Durch Schreiben eines Wert (empfohlen: 0) wird der aktuelle Player abgefragt. Achtung: Ohne aktiven Player sind die Befehle Play, Pause, etc. nicht funktionsfähig.

**title**
Item type ``str``. Der Titel des aktuell gespielten Elements. Wird vom Plugin automatisch bei Änderungen aktualisiert.

**media**
Item type ``str``. Der Medientyp des aktuell gespielten Elements. Wird vom Plugin automatisch bei Änderungen aktualisiert.

**macro**
Item type ``str``. Eine Abfolge von Befehlen. Aktuell werden folgende Makros unterstützt, die beim Abspielen eines Elements relevant sind:
- resume: Falls ein Medium eine gewisse Zeit gelaufen ist, ist es möglich, an der gleichen Stelle fortzusetzen.
- beginning: Auch wenn ein Medium bereits eine gewisse Zeit gelaufen ist, wird von vorne begonnen.

**state**
Item type ``str``. Informaation zum aktuellen Status von Kodi (Playing, Stopped, Screensaver,...).

**favourites**
Item type ``dict``. Die in Kodi definierten Favoriten werden als Dictionary in dieses Item gespeichert. Ein Ändern der Einträge ist nicht möglich.

**audiostream**
Item type ``foo``. Ändern der Tonspur, entweder next, previous oder eine Zahl zur Direktanwahl

**subtitle**
Item type ``list``. Einstellen des Untertitels als Liste. Der erste Wert muss die Untertitelspur deklarieren, der zweite ist True oder False

**input**
Item type ``str``. Diese Funktion ermöglicht die Kontrolle über Kodi wie mit einer Fernbedienung. Für dieses Item sollte ``enforce_updates`` aktiviert werden. Eine Übersicht über mögliche Aktion ist auf der `Kodi Wiki Seite <https://kodi.wiki/view/Action_IDs>`_
Ein Auszug der wichtigsten Aktionen:

- ``play`` Abspielen. Es muss ein aktiver Player vorhanden sein!
- ``pause`` Pausieren. Es muss ein aktiver Player vorhanden sein!
- ``playpause`` Umschalten zwischen Abspielen und Pause. Es muss ein aktiver Player vorhanden sein!
- ``stop`` Stoppen. Es muss ein aktiver Player vorhanden sein!
- ``osd`` On Screen Display anzeigen
- ``left`` Cursor nach links
- ``right`` Cursor nach rechts
- ``up`` Cursor nach oben
- ``down`` Cursor nach unten
- ``select`` Aktuelles Navigationselement aktivieren
- ``contextmenu`` Anzeigen des Kontextmenüs
- ``home`` Home Menu
- ``back`` Einen Schritt zurück
- ``volumeup`` Erhöhen der Lautstärke
- ``volumedown`` Verringern der Lautstärke

Struct Vorlagen
===============

Ab smarthomeNG 1.6 können Vorlagen aus dem Plugin einfach eingebunden werden. Dabei stehen folgende Vorlagen zur Verfügung:

- query: Enthält Funktionen, die zur Abfrage von Kodi Infos dienen.
- control: Enthält Funktionen, mit denen Kodi gesteuert werden kann.
