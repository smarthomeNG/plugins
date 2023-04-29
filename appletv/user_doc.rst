.. index:: Plugins; appletv
.. index:: appletv

=======
appletv
=======

.. image:: webif/static/img/plugin_logo.png
   :alt: plugin logo
   :width: 400px
   :height: 308px
   :scale: 100 %
   :align: left

Mit diesem Plugin können Sie ein oder mehrere `Apple TVs <https://www.apple.com/tv/>`_ aller Generationen steuern. Jedes Apple TV benötigt eine eigene Plugin-Instanz. Es benutzt die `pyatv library <github.com/postlund/pyatv/tree/v0.3.9>`_ von Pierre Ståhl. Es bietet auch eine Web-Schnittstelle, die mit dem `http`-Modul verwendet werden kann.


Konfiguration
=============

Diese Plugin Parameter und die Informationen zur Item-spezifischen Konfiguration des Plugins sind
unter :doc:`/plugins_doc/config/appletv` beschrieben.


plugin.yaml
-----------

.. code-block:: yaml

    # etc/plugin.yaml
    appletv:
        plugin_name: appletv
        #instance: wohnzimmer
        #ip: 192.168.2.103
        #login_id: 00000000-0580-3568-6c73-86bd9b834320

Items
=====

name (String)
-------------
Enthält den Namen des Geräts, wird beim Starten des Plugins durch die automatische Erkennung gefüllt

artwork_url (String)
--------------------
Enthält eine URL zum Artwork der aktuell abgespielten Mediendatei (falls vorhanden).

play_state (Ganzzahl)
---------------------
Der aktuelle Abspielstatus als Integer. Derzeit unterstützte Abspielzustände:

* 0: Gerät befindet sich im Leerlaufzustand
* 1: Kein Medium wird gerade ausgewählt/abgespielt
* 2: Medium wird geladen/gepuffert
* 3: Medium ist pausiert
* 4: Medium wird abgespielt
* 5: Medien werden vorgespult
* 6: Medien werden zurückgespult

play_state_string (String)
----------------------------
Der aktuelle Status der Wiedergabe als Text.

playing (bool)
--------------
`True` wenn play\_state 4 ist (Medium wird abgespielt), `False` für alle anderen play_states.

media_type (Ganzzahl)
-----------------------
Der aktuelle Abspielstatus als Integer. Derzeit unterstützte Abspielzustände:

* 1: Medientyp ist unbekannt
* 2: Medientyp ist Video
* 3: Medientyp ist Musik
* 4: Medientyp ist TV

media_type_string (String)
----------------------------
Der aktuelle Medientyp als Text.

album (String)
--------------
Der Name des Albums. Nur relevant, wenn der Inhalt Musik ist.

artist (String)
---------------
Der Name des Interpreten. Nur relevant, wenn der Inhalt Musik ist.

genre (String)
--------------
Das Genre der Musik. Nur relevant, wenn der Inhalt Musik ist.

title (String)
--------------
Der Titel des aktuellen Mediums.

position (Ganzzahl)
-------------------
Die aktuelle Position innerhalb des abspielenden Mediums in Sekunden.

total_time (Ganzzahl)
-----------------------
Die tatsächliche Abspielzeit des Mediums in Sekunden.

position_percent (Ganzzahl)
-----------------------------
Die aktuelle Position innerhalb des abspielenden Mediums in %.

repeat (Ganzzahl)
-------------------
Der aktuelle Status des ausgewählten Wiederholungsmodus. Derzeit unterstützte Wiederholungsmodi:

* 0: Keine Wiederholung
* 1: Wiederholung des aktuellen Titels
* 2: Alle Spuren wiederholen

repeat_string (String)
----------------------
Der aktuell gewählte Typ des Wiederholungsmodus als String.

shuffle (bool)
--------------
`True` wenn shuffle aktiviert ist, `False` wenn nicht.

rc_top_menu (bool)
------------------
Setzt diesen Punkt auf `True`, um zum Home-Menü zurückzukehren.
Das Plugin setzt diesen Eintrag nach der Befehlsausführung auf `False` zurück.

rc_menu (bool)
--------------
Setzt diesen Punkt auf `True`, um zum Menü zurückzukehren.
Das Plugin setzt dieses Element nach der Ausführung des Befehls auf `False` zurück.

rc_select (bool)
----------------
Setzt diesen Punkt auf `True` um die 'select' Taste zu drücken.
Das Plugin setzt diesen Punkt nach der Ausführung des Befehls auf `False` zurück.

rc_left, rc_up, rc_right, rc_down (bools)
-----------------------------------------
Setzt eines dieser Elemente auf `True`, um den Cursor in die entsprechende Richtung zu bewegen.
Das Plugin setzt diese Werte nach der Befehlsausführung auf `False` zurück.

rc_previous (bool)
------------------
Setzen Sie dieses Element auf `True`, um die 'previous'-Taste zu drücken.
Das Plugin setzt diesen Punkt nach der Befehlsausführung auf `False` zurück.

rc_play (bool)
--------------
Setzt dieses Element auf `True`, um die 'play'-Taste zu drücken.
Das Plugin setzt dieses Element nach der Ausführung des Befehls auf `False` zurück.

rc_pause (bool)
---------------
Setzt dieses Element auf `True`, um die 'Pause'-Taste zu drücken.
Das Plugin setzt dieses Element nach der Ausführung des Befehls auf `False` zurück.

rc_stop (bool)
--------------
Setzt dieses Element auf `True`, um die 'stop'-Taste zu drücken.
Das Plugin setzt dieses Element nach der Ausführung des Befehls auf `False` zurück.

rc_next (bool)
--------------
Setze dieses Element auf `True`, um die 'next'-Taste zu drücken.
Das Plugin setzt dieses Element nach der Ausführung des Befehls auf `False` zurück.


Struct Vorlagen
===============

Ab smarthomeNG 1.6 können Vorlagen aus dem Plugin einfach eingebunden werden. Dabei stehen folgende Vorlagen zur Verfügung:

- device: Informationen zur IP, MAC-Adresse, Einschaltzustand, etc.
- playing: Informationen zum aktuell gespielten Titel wie Artist, Album, etc. sowie Ansteuern des Abspielmodus und mehr
- control: verschiedene Fernbedienungsfunktionen wie Menü, Play/Pause, etc.


Funktionen
==========

is_playing()
------------
Gibt `true` oder `false` zurück und zeigt an, ob das Apple TV gerade Medien abspielt.
Beispiel: `playing = sh.appletv.is_playing()`

play()
------
Sendet einen Abspielbefehl an das Gerät.
Beispiel: `sh.appletv.play()`

pause()
-------
Sendet einen Pausenbefehl an das Gerät.
Beispiel: `sh.appletv.pause()`

play_url(url)
-------------
Spielt ein Medium unter Verwendung der angegebenen URL ab. Das Medium muss natürlich mit dem Apple TV Gerät kompatibel sein. Damit dies funktioniert, muss SHNG zuerst beim Gerät authentifiziert werden. Dies geschieht über die Schaltfläche "Authentifizieren" in der Weboberfläche. Anschließend muss ein PIN-Code, der auf dem Fernsehbildschirm angezeigt wird, in die Weboberfläche eingegeben werden. Dieser sollte nur einmal benötigt werden und für immer gültig sein.
Beispiel: `sh.appletv.play_url('http://distribution.bbb3d.renderfarming.net/video/mp4/bbb_sunflower_1080p_60fps_normal.mp4')`

SmartVISU
=========
Wenn SmartVISU als Visualisierung verwendet wird, kann folgender HTML-Code in einer der Seiten verwendet werden:

.. code-block:: HTML

    <div class="block">
        <div class="set-2" data-role="collapsible-set" data-theme="c" data-content-theme="a" data-mini="true">
            <div data-role="collapsible" data-collapsed="false">
                <h3>Apple TV {{ basic.print('', 'atv.wohnzimmer.name') }} ({{ basic.print('', 'atv.wohnzimmer.media_type_string') }} {{ basic.print('', 'atv.wohnzimmer.play_state_string') }})</h3>
                <table width="100%">
                    <tr>
                        <td>
                            {{ basic.stateswitch('', 'atv.wohnzimmer.rc_top_menu', '', '1', 'jquery_home.svg', '') }}
                            {{ basic.stateswitch('', 'atv.wohnzimmer.rc_menu', '', '1', 'control_return.svg', '') }}
                        </td>
                        <td>
                            {{ basic.stateswitch('', 'atv.wohnzimmer.rc_up', '', '1', 'control_arrow_up.svg', '') }}
                        </td>
                    </tr>
                    <tr>
                        <td>
                            {{ basic.stateswitch('', 'atv.wohnzimmer.shuffle', '', '', 'audio_shuffle.svg', '') }}
                            {{ basic.stateswitch('', 'atv.wohnzimmer.repeat', '', [0,1,2], ['audio_repeat.svg','audio_repeat_song.svg','audio_repeat.svg'], '', ['icon0','icon1','icon1']) }}
                        </td>
                        <td>
                            {{ basic.stateswitch('', 'atv.wohnzimmer.rc_left', '', '1', 'control_arrow_left.svg', '') }}
                            {{ basic.stateswitch('', 'atv.wohnzimmer.rc_select', '', '1', 'control_ok.svg', '') }}
                            {{ basic.stateswitch('', 'atv.wohnzimmer.rc_right', '', '1', 'control_arrow_right.svg', '') }}
                        </td>
                    </tr>
                    <tr>
                        <td>&nbsp;</td>
                        <td>
                            {{ basic.stateswitch('', 'atv.wohnzimmer.rc_down', '', '1', 'control_arrow_down.svg', '') }}
                        </td>
                    </tr>
                    <tr>
                        <td colspan="2">&nbsp;</td>
                    </tr>
                    <tr>
                        <td colspan="2">
                            {{ basic.print('', 'atv.wohnzimmer.artist') }} - {{ basic.print('', 'atv.wohnzimmer.album') }}
                        </td>
                    </tr>
                    <tr>
                        <td colspan="2">
                            {{ basic.print('', 'atv.wohnzimmer.title') }} ({{ basic.print('', 'atv.wohnzimmer.genre') }})
                        </td>
                    </tr>
                    <tr>
                        <td colspan="2">{{ basic.slider('', 'atv.wohnzimmer.position_percent', 0, 100, 1, 'horizontal', 'none') }}</td>
                    </tr>
                    <tr>
                        <td colspan="2">
                            <div data-role="controlgroup" data-type="horizontal">
                                {{ basic.stateswitch('', 'atv.wohnzimmer.rc_previous', '', '1', 'audio_rew.svg', '') }}
                                {{ basic.stateswitch('', 'atv.wohnzimmer.rc_play', '', '1', 'audio_play.svg', '') }}
                                {{ basic.stateswitch('', 'atv.wohnzimmer.rc_pause', '', '1', 'audio_pause.svg', '') }}
                                {{ basic.stateswitch('', 'atv.wohnzimmer.rc_next', '', '1', 'audio_ff.svg', '') }}
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td colspan="2">
                            {{ basic.print ('', 'atv.wohnzimmer.artwork_url', 'html', '\'<img src="\' + VAR1 + \'" height="150" />\'') }}
                        </td>
                    </tr>
                </table>
            </div>
        </div>
    </div>

Web Interface
=============

Das Webinterface kann genutzt werden, um die Items und deren Werte auf einen Blick zu sehen,
die dem Plugin zugeordnet sind. Außerdem können erkannte Geräte eingesehen und gekoppelt werden.
Für jedes erkannte Gerät gibt es zudem eine Übersicht mit den aktuellen Informationen wie Status,
Abspielposition, Künstler, etc.

.. image:: assets/webif_appletv1.png
   :height: 1612px
   :width: 3312px
   :scale: 25%
   :alt: Web Interface
   :align: center
