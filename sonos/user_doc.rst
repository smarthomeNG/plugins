.. index:: Plugins; sonos
.. index:: sonos

=====
sonos
=====

.. image:: webif/static/img/plugin_logo.png
   :alt: plugin logo
   :width: 300px
   :height: 300px
   :scale: 50 %
   :align: left


Anforderungen
=============


Notwendige Software
-------------------

Folgende Python Pakete werden vom Plugin benötigt und automatisch installiert:
xmltodict>=0.11.0
tinytag>=0.18.0
gtts

Weiterhin braucht das Basisframework SoCo diese python Pakete:
ifaddr
appdirs
lxml

Unterstützte Geräte
-------------------

Es werden alle Sonos Lautsprecher unterstützt.
Offizielle Sonos Seite:
https://www.sonos.com/
Das Plugin basiert auf dem Sonos SoCo github projekt:
https://github.com/SoCo/SoCo

Konfiguration
=============

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


Beispiele
=========

Radiosender abspielen
~~~~~~~~

Ein Radiosender wird ueber play_tunein ausgewaehlt.

.. code-block:: text

    sh.Sonos.Speaker.play_tunein('WDR2')
    sh.Sonos.Speaker.play(True)
    sh.Sonos.Speaker.mute(False)

Sonos playlist abspielen
~~~~~~~~

Eine Sonos Playliste wird uebereber load_sonos_playlist ausgewaehlt.
Alle verfuegbaren Playlists wird in sonos_playlist angezeigt.

.. code-block:: text

    sh.Sonos.Speaker.load_sonos_playlist('NameDerPlaylist')


Web Interface
=============

Das Plugin kann aus dem Admin Interface aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

Außerdem kann das Webinterface direkt über ``http://smarthome.local:8383/sonos`` aufgerufen werden.

Folgende Informationen kÃ¶nnen im Webinterface angezeigt werden:

Oben rechts werden allgemeine Parameter zum Plugin wie die aktuelle SoCo Version angezeigt.
Weiterhin wird die Anzahl der Speaker angezeigt, die akuell online und verwendbar sind.


Version History
===============

