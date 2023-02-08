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

Folgende Python Pakete werden vom Plugin benötigt und automatisch bei der ersten Verwendung installiert:
 * xmltodict>=0.11.0
 * tinytag>=0.18.0
 * gtts

Weiterhin braucht das Basisframework SoCo diese python Pakete. Diese werden auch bei der ersten Verwendung installiert:
 * ifaddr
 * appdirs
 * lxml

Unterstützte Geräte
-------------------

Es werden alle Sonos Lautsprecher unterstützt.
Offizielle Sonos Seite: ``https://www.sonos.com/``
Das Plugin basiert auf dem Sonos SoCo github projekt: ``https://github.com/SoCo/SoCo``

Konfiguration
=============

plugin.yaml
-----------

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.

1) Sonos Speaker automatisch im Netzwerk suchen:


2) Sonos Speaker manuell konfigurieren:

In manchen Situation sollten die verfügbaren Sonos Speaker statisch über Ihre IP Adressen konfiguriert werden. Dies
ist zum Beispiel erforderlich, wenn das lokale Netzwerk Multicast und/oder UDP nicht unterstützt, was für die automatische Detektion
unter 1) benötigt wird. ddresses of your speakers statically to avoid using the internal discover function.

Folgendermaßen werden Speaker statisch in der plugin.yaml konfiguriert:

```yaml
Sonos:
    class_name: Sonos
    class_path: plugins.sonos
    speaker_ips:                       
      - 192.168.1.10                    
      - 192.168.1.77
      - 192.168.1.78
```


items.yaml
----------

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


logic.yaml
----------

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


Funktionen
----------

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


Unterstütze Eigenschaften/Funktionen
====================================

*bass*
```read``` ```write```

Dieses Attribut steuert die Basslautstärke eines Speakers. Der Wert muss ein ganzahliger Wert zwischen -10 und 10 sein.
Diese Eigenschaft ist KEIN Gruuppenbefehl. Trotzdem kann ein untergeordnetes item `group_command` auf True gesetzt werden,
um anschließend die Basslautstärke gemeinsam für alle Speaker einer Gruppe zu setzen.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*coordinator*
```read```

Gibt die UID des Speakers zurück, der aktuell der Koordinator der Gruppe ist. Die UID ist ein String. Ist ein Speaker nicht groupiert, ist der Speaker
per Definition immer selber Koordinator. Das Item gibt in diesem Fall die eigene UID zurück.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*cross_fade*
```read``` ```write```

Setzt bzw. liest den Cross-Fade Modues eines Speakers. Das Item ist vom Typ Boolean. 'True' bedeutet Cross-Fade eingeschaltet, 'False' ausgeschaltet.
Das Setzen ist ein Gruppenbefehl und wird für alle Speaker einer Gruppe angewendet. 
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*current_track*
```read```

Gibt die Indexposition des aktuell gespielten Tracks innerhalb der Playliste zurück. Das Item ist vom Typ Integer.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*current_track_duration*
```read```

Gibt die aktuelle Spiellänge des Tracks im Format HH:mm:ss an.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*current_transport_actions*
```read``` ```visu```

Gibt die möglichen Transport Actions für den aktuellen Track wieder.
Mögliche Werte sind: Set, Stop, Pause, Play, X_DLNA_SeekTime, Next, Previous, X_DLNA_SeekTrackNr.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*current_valid_play_modes*
```read```

Gibt alle validen Abspielmodi für den aktuellen Zustand zurück. Die Modi werden als String (mit Kommata getrennt) ausgegeben.
Einer der Modi kann dem 'play_mode' Befehl übergeben werden. 
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*dialog_mode*
```read``` ```write```

Nur unterstützt von Sonos Playbars. 
Setzt bzw. liest den Dialog Modus einer Playbar. 'True' bdeutet Dialog Modus ein, 'False' Modus aus. 
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an (zu bestätigen).

*household_id*
```read```

Gibt die Household ID des Speakers zurück.

*is_coordiantor*
```read```

Gibt den Status zurück, ob ein Speaker Koordinator eine Gruppe ist, oder nicht. Das Item ist vom Typ Boolean.
Rückgabe von 'True' falls der Speaker der Koordinator ist, 'False' falls der Koordinator ein anderer Speaker ist.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*is_initialized*
```read```

Gibt den Status zurück, ob ein Speaker initialisiert und erreichbar ist. Das Item ist vom Typ Boolean.
'True' bedeutet, dass der Speaker initialisiert und erreichbar ist. Bei 'False' ist der Speaker entweder offline oder nicht vollständig initialisiert. 
Nutze dieses item in Logiken oder Szenen bevor weitere Kommendos an den Speaker gesendet werden, siehe Beispiel 3).

*join*
```write```

Verbindet einen Speaker mit einem anderen Speaker oder Gruppe per Übergabe der UID eines Geräts,
welches sich schon in der Gruppe befindet. Zusätzlich sollte für das Item das smarthomeNG item Attribut ```enforce_update: True```
gesetzt werden.

*load_sonos_playlist*
```write```

Lädt eine Sonos playlist über ihren Namen. Die Funktion ```sonos_playlists``` zeigt alle verfügbaren Playlisten an. 
Dies ist ein Gruppenbefehl, der auf jeden Speaker einer Gruppe angewandt werden kann. 
 
_child item_ ```start_after```:
Wird ein untergeordnetes item vom Typ Boolean mit dem Attribut ```sonos_attrib: start_after``` angelegt, kann das Verhalten
nach Laden der Playliste bestimmt werden. Wird das Item auf ```True``` gesetzt, startet der Speaker direkt die Wiedergabe.
Wird das Item auf ```False``` gesetzt, wird nur die Playliste geladen und es erfolgt keine direkte Wiedergabe.
Wird dieses Item weggelassen, ist der Standardverhalten 'False'.

_child item_ ```clear_queue```:
Wird ein untergeordnetes item vom Typ Boolean mit dem Attribut ```sonos_attrib: clear_queue``` angelegt, wird bei Wert
''True'' die bestehende Sonos Playlist gelöscht bevor die neue Playlist geladen wird. Bei Wert ```False``` bleibt die bestehende Liste
erhalten und die Songs der neu zu ladenen Playliste werden angehängt.
Wird dieses Item weggelassen, ist der Standardverhalten 'False'.
 
_child item_ ```start_track```:
Wird ein untergeordnetes item vom Typ Number mit dem Attribut ```sonos_attrib: start_track``` angelegt, kann die Indexposition
innerhalb der geladen Playliste definiert werden, von wo die Wiedergabe startet. Der erste Song in der Playliste entspricht der
Indexposition '0'. 
Wird dieses Item weggelassen, ist der Standardverhalten ein Start bei Indixposition '0'.

*loudness*
```read``` ```write```

Setzt oder liest den Modus Lautstärkeabsekung eines Speakers. Das Item ist vom Typ Boolean. Bei Wert ```True```
wird die Lautstärke und Bass abgesenkt, bei ```False``` nicht.
Diese Eigenschaft ist kein Gruppenbefehl. Nichtestotrotz kann über ein untergeordnetes Item mit dem Attribut
```group_command: True``` ein Gruppenbefehl erzwungen werden, d.h. die Lautstärkenabsenkung wird für alle Speaker innerhalb der Gruppe gesetzt. 
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*streamtype*
```read``` ```visu```

Gibt den aktuellen Streamtyp zurück. Das Item ist vom Typ String. Mögliche Werte sind
'music' (Standard, z.B. beim Spielen eines Songs aus dem Netzwerk), 'radio', 'tv' (falls der Audio Output einer Playbar 
auf 'TV' gesetzt ist, oder 'line-in' (z.B. beim Sonos Play5).
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*mute*
```read``` ```write``` ```visu```

Stellt einen Speaker auf lautlos. Das Item ist vom Typ Boolean. Der Wert 'True' bedeutet lautlos (mute),
'False' bedeutet laut (un-mute).
Der Befehl ist ein Gruppenbefehl und wird für alle Speaker einer Gruppe angewendet. 
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*next*
```write``` ```visu```

Wechselt zum nächsten Song der aktuellen Playliste. Das Item ist vom Typ Boolean. Der Wert 'True'
bedeutet Sprung zum nächsten Track. Ein Setzen auf 'False' hat keinen Effekt. Zusätzlich muss
für das Item das smarthomeNG item Attribut ```enforce_update: True``` gesetzt werden.
Der Befehl ist ein Gruppenbefehl und wird für alle Speaker einer Gruppe angewendet. 

*night_mode*
```read``` ```write```

Nur von der Sonos Playbar unterstütz. 
Setzt oder liest den Nachmodus einer Sonos Playbar. Das Item ist vom Typ Boolean. Wert 'True' zeigt Nachmodus aktiv an, 
Wert 'False' bedeutet Nachtmodus aus.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an (bisher ungetestet).

*number_of_tracks*
```read```

Gibt die komplette Anzahl an Tracks in der aktuellen Playliste zurück.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*pause*
```read``` ```write``` ```visu```

Pausiert die Wiedergabe. Das Item ist vom Typ Boolean. Wert 'True' bedeutet pausieren, 'False' führt die Wiedergabe fort. 
Der Befehl ist ein Gruppenbefehl und wird für alle Speaker einer Gruppe angewendet.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*play*
```read``` ```write``` ```visu```

Startet die Wiedergabe.  Das Item ist vom Typ Boolean. Der Wert 'True' bedeutet Wiedergabe, 'False' bedeutet pausieren. 
Der Befehl ist ein Gruppenbefehl und wird für alle Speaker einer Gruppe angewendet.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*player_name*
```read```

Gibt den Namen des Speakers zurück. Das Item ist vom Typ String.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*play_mode*
```read``` ```write```

Setzt oder liest den Abspielmodus für einen Speaker. Das Item ist vom Typ String.
Erlaubte Werte sind 'NORMAL', 'REPEAT_ALL', 'SHUFFLE', 'SHUFFLE_NOREPEAT', 'SHUFFLE_REPEAT_ONE', 'REPEAT_ONE'.
Der Befehl ist ein Gruppenbefehl und wird für alle Speaker einer Gruppe angewendet.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.

*play_snippet*
```write```

Spielt ein Audio Snippet über einen Audiodateinamen ab (z.B. 'alarm.mp3'). Das Item ist vom Typ String.
Voraussetzung ist, dass in der ```plugin.yaml``` die Attribute ```tts``` und der ```local_webservice_path``` gesetzt sind. 
Die Audiodatei muss in dem unter ```local_webservice_path``` oder ```local_webservice_path_snippet``` angegebenen Pfaden liegen. 
Folgende Dateiformate werden unterstütz: 'mp3', 'mp4', 'ogg', 'wav', 'aac' (tested only with 'mp3').
Der Befehl ist ein Gruppenbefehl und wird für alle Speaker einer Gruppe angewendet.

_child item_ ```snippet_volume```:
Wird ein untergeordnetes Item vom Typ Number mit Attribut ```sonos_attrib: snippet_volume``` definiert, 
kann die Laustärke explizit für das Abspielen von Snippets gesetzt werden. Diese Snippet Lautstärke beeinflusst nicht
die Lautstärke der normalen Wiedergabe, auf die nach Abspielen des Snippets zurückgewechelt wird.
Wird ein Snippet in einer Gruppe abgespielt, wird für jeden einzelnen Speaker die ursprüngliche Lautstärke wiederhergestellt. 

_child item_ ```snippet_fade_in```:
Wird ein untergeordnetes Item vom Typ Boolean mit Attribut ```sonos_attrib: snippet_fade_in``` definiert, wird die Lautstärke
nach dem Abspielen des Snippets von 0 auf das gewünschte Level schrittweise angehoben und eingeblendet. 

*play_tts*
```write```

Spielt eine definierte Nachticht ab (Text-to-Speech). Das Item ist vom Typ String. Aus der Nachricht im String wird von dem Google TTS API eine
Audiodatei erzeugt, die lokal gespeichert und abgespielt wird. 
Für die Nutzung dieses Features müssen mindestens zwei Parameter in der ``plugin.yaml``` gesetzt sein:
```tts``` und ```local_webservice_path```.
Der Befehl ist ein Gruppenbefehl und wird für alle Speaker einer Gruppe angewendet.

_child item_ ```tts_language```:
Wird ein untergeordnetes Item vom Typ String mit Attribut ```sonos_attrib: tts_language``` angelegt, kann die
Spracheinstellung der Google TTS API definiert werden. 
Gültige Werte sind 'en', 'de', 'es', 'fr', 'it'. Ist das Item nicht vorhanden, wird die Standardeinstellung 'de' verwendet.
 
_child item_ ```tts_volume```:
Wird ein untergeordnetes Item vom Typ Number mit Attribut ```sonos_attrib: tts_volume``` angelegt, kann die Lautstärke
für das Abspielen von Text-to-Speech separat dedfiniert werden. Die reguläre Lautstärke wird damit nicht beeinflusst.
Nach der Ansage wird die Lautstärke jedes Speakers individuell in der Gruppe wieder hergestellt.

_child item_ ```tts_fade_in```:
Wird ein untergeordnetes Item vom Typ Boolean mit Attribut ```sonos_attrib: tts_fade_in``` definiert, wird die Lautstärke
nach dem Abspielen der Nachricht von 0 auf das gewünschte Level schrittweise angehoben und eingeblendet. 

*play_tunein*
```write```

Spielt einen Radiosender anhand eines Namens. Das Item ist vom Typ String. Sonos sucht dazu in einer Datenbank nach potentiellen Radiostationen, die dem Namen entsprechen.
Wird mehr als ein zum Suchbegriff passender Radiosender gefunden, wird der erste Treffer verwendet. 
Der Befehl ist ein Gruppenbefehl und wird für alle Speaker einer Gruppe angewendet.

_child item_ ```start_after```:
If you add an child item (type ```bool```) with an attribute ```sonos_attrib: start_after``` you can control the behaviour
after the radio station was added to the Sonos speaker. If you set this item to ```True```, the speaker starts playing
immediately, ```False``` otherwise. (see example item configuration). You can omit this child item, the default
setting is 'True'. 

#### play_url
```write```

Plays a given url. 

_child item_ ```start_after```:
If you add an child item (type ```bool```) with an attribute ```sonos_attrib: start_after``` you can control the behaviour
after the url was added to the Sonos speaker. If you set this item to ```True```, the speaker starts playing
immediately, ```False``` otherwise. (see example item configuration). You can omit this child item, the default
setting is 'True'. This is a group command and effects all speakers in the group.

#### play_sharelink
```write```

Plays a given sharelink, e.g. a Spotify sharelink. You need a Spotify premium account to play links. The free account does not support sharelinks. 

_child item_ ```start_after```:
If you add an child item (type ```bool```) with an attribute ```sonos_attrib: start_after``` you can control the behaviour
after the sharelink was added to the Sonos speaker. If you set this item to ```True```, the speaker starts playing
immediately, ```False``` otherwise. (see example item configuration). You can omit this child item, the default
setting is 'True'. This is a group command and effects all speakers in the group.

#### previous
```write``` ```visu```

Go back to the previously played track. 'True' for previously played track, all other values have no effects. Be aware 
that you have to use the additional SmarthomeNG attribute ```enforce_updates: true``` for this item to make it working. 
This is a group command and effects all speakers in the group.

#### radio_station
```read``` ```visu```

Returns the name of the currently played radio station. If no radio broadcast is currently played (see item 
```streamtype```), the item is empty. This item is changed by Sonos events and should always be up-to-date.

#### radio_show
```read``` ```visu```

If available (it dependson the radio station), this item returns the name of the currently played radio show. If no 
radio broadcast is currently played (see item ```streamtype```), this item is always empty. This item is changed by 
Sonos events and should always be up-to-date.

#### snooze
```read``` ```write```

Sets / gets the snooze timer. It must be an integer between 0 - 86399 (in seconds). If this item is set to or is 0, the 
snooze timer is deactivated. This is a group command and effects all speakers in the group. The value is NOT updated in 
real-time. For each speaker discover cycle the item will be updated.
  
#### sonos_playlists
```read``` ```visu```


Returns a list of Sonos playlists. These playlists can be loaded by the ```load_sonos_playlist``` item. 

#### status_light
```read``` ```write```

Sets / gets the status light indicator of a speaker. 'True' to turn the light on, 'False' to turn it off. The value is 
NOT updated in real-time. For each speaker discover cycle the item will be updated.

#### buttons_enabled
```read``` ```write```

Sets / gets the state of the buttons/touch enabled feature of a speaker. 'True' to enable button/touch control, 'False' to disable it. The value is 
NOT updated in real-time. For each speaker discover cycle the item will be updated.


#### stop
```read``` ```write``` ```visu```

Stops the playback. 'True' for stop, 'False' to start the playback. This is a group command and effects all
speakers in the group. This item is changed by Sonos events and should always be up-to-date.

#### stream_content
```read``` ```visu```

Returns the content send by a radio station, e.g. the currently played track and artist. If no radio broadcast is 
currently played (see item```streamtype```), the item is empty. This item is changed by Sonos events and should always 
be up-to-date.

#### switch_line_in
```write```

Switches the audio input of a Sonos Play5 (or all other speakers with a line-in) to line-in. 'True' to switch to 
line-in, all other values have no effect.

#### switch_tv
```write```

Switch the playbar speaker's input to TV. 'True' to switch to TV, all other values have no effect. Only supported by 
Sonos Playbar.

#### track_album
```read``` ```visu```

Returns the album title of currently played track. This item is changed by Sonos events and should always be up-to-date.

#### track_album_art
```read``` ```visu```

Returns the album cover url of currently played track. This item is changed by Sonos events and should always be 
up-to-date.

#### track_artist
```read``` ```visu```

Returns the artist of the current track. This item is changed by Sonos events and should always be up-to-date.

#### track_title
```read``` ```visu```

Returns the title of the current track. This item is changed by Sonos events and should always be up-to-date.

#### track_uri
```read``` ```visu```

Returns the uri of currently played track. This item is changed by Sonos events and should always be up-to-date.

#### treble
```read``` ```write```

Sets / gets the treble level for a speaker. It must be an integer value between -10 and 10. This property is NOT a
group item, nevertheless you can set the child item ```group_command``` to 'True' to set the bass level to all members
of the group. This must be done before setting the treble item to a new value. This item is changed by Sonos events and 
should always be up-to-date.

*uid*
```read```

Gibt die eindeutige Speaker ID als String zurück.

*unjoin*
```write```

Entkoppelt ein Speaker aus einer Gruppe.

_child item_ ```start_after```:
Wird ein untergeordnetes Item vom Typ Boolean mit Attribut ```sonos_attrib: start_after``` definiert, wird das Verhalten nach Entkopplung definiert.
Ein Wert  bedeutet, der entkoppelte Speaker startet seine individuelle Wiedergabe, ```False``` startet keine Wiedergabe.
Dieses unteritem ist optional und kann weggelassen werden. In dem Fall greift das Standardverhalten als keine Wiedergabe.

*volume*
```read``` ```write``` ```visu```

Setzt bzw. liest den Lautstärkepegel eines Speakers. Das Item ist vom Typ Number und muss ein ganzzahliger Wert zwischen 0-100 sein.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.
Es wird empfolen, zusätzlich das Item Attribut ```enforce_updates: true``` zu setzen.

_child item_ ```group_command```:
Wird ein untergeordnetes Item vom Typ Boolean mit Attribut ```sonos_attrib: group_command``` definiert, wird die Lautstärke
auf alle Speaker innerhalb der Gruppe angewendet.

_child item_ ```max_volume```:
Wird ein untergeordnetes Item vom Typ Number mit Attribut ```sonos_attrib: max_volume``` definiert, wird der Wert der
maximal möglichen Lautstärke auf den Wert begrenzt. Wertebereich ist 0-100. Dies betrifft nicht das Setzen der Lautstärke via Sonos APP.
Wurde der obige ```group_command``` auf ```True``` gesetzt, betrifft die Begrenzung alle Speaker innerhalb der Gruppe.

_child item_ ```volume_dpt3```:
Um die Lautstärke inkrementell via KNX dpt3 ohne externe Logik zu verstellen, kann optional dieses untergeordnete Item definiert werden.
Hierzu wird ein untergeordnetes Item mit ```volume_dpt3``` angelegt, siehe Beispiel 4).

*zone_group_members*
```read```

Gibt eine Liste aller UIDs aus, die sich in der Gruppe des Speakers befinden. Die Liste enthält auch den aktuellen Speaker.
Das Item wird über Sonos Events aktualisiert und zeigt daher immer den aktuellen Status an.



Nicht echtzeitfähige Eigenschaften
----------------------------------

Einige Eigenschaften sind nicht Event basiert. Das bedeutet, das sie nicht direkt nach
Änderung über ein Event aktualisiert werden sondern die Änderung erst bei der nächsten
zyklischen Abfrage bei smarthomeNG ankommt.
Folgende Eigenschaften sind **nicht** Event basiert:
 * snooze
 * status_light


Beispiele
=========

1) Radiosender abspielen
------------------------

Ein Radiosender wird über play_tunein ausgewählt.

.. code-block:: text

    sh.Sonos.Speaker.play_tunein('WDR2')
    sh.Sonos.Speaker.play(True)
    sh.Sonos.Speaker.mute(False)

2) Sonos playlist abspielen
---------------------------

Eine Sonos Playliste wird über **load_sonos_playlist** ausgewaehlt.
Alle verfügbaren Playlists werden mit **sonos_playlist** angezeigt.

.. code-block:: text

    sh.Sonos.Speaker.load_sonos_playlist('NameDerPlaylist')

3) Nutzung der `is_initialized` Eigenschaft
-------------------------------------------

Nach Start dauert es etwas, bis alle Sonos Speaker im Netzwerk initialisiert sind. Es ist deshalb angeraten,
die Methode `is_initialized´ in Logiken zu verwenden. Gibt die Eigenschaft True zurück, so ist der Speaker
erreichbar und funktional. `False´ bedeutet, der Speaker is noch nicht initialisiert oder offline.

Beispiel:

```python
if sh.MySonosPlayer.is_initialized():
    do_something()
```

4) Lautstärke inkrementell verstellen (via KNX dpt3)
----------------------------------------------------

Dieses Beispiel zeigt die Verstellung der Laustärke inkrementell via dpt3:

```yaml
volume:
    ...
    ...
    volume_dpt3:
        type: list
        sonos_attrib: vol_dpt3
        sonos_dpt3_step: 2
        sonos_dpt3_time: 1
    
        helper:
            sonos_attrib: dpt3_helper
            type: num
            sonos_send: volume
```
Bitte sicherstellen, dass ein enstprechendes helper Item definiert wird. Über das Attribut ```sonos_dpt3_step```
werden die Laustärkeinkremente definiert und über ```sonos_dpt3_time``` die Zeit pro Inkrement. Beide Werte können
weggelassen werden. Dann werden die Standardwerte ```sonos_dpt3_step: 2``` und ```sonos_dpt3_step: 1``` verwendet.
Die Eigenschaften ```group_command``` und ```max_volume``` werden hierbei berücksichtigt.


Web Interface
=============

Das Plugin kann aus dem Admin Interface aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

Außerdem kann das Webinterface direkt über ``http://smarthome.local:8383/sonos`` aufgerufen werden.

Folgende Informationen können im Webinterface angezeigt werden:

Oben rechts werden allgemeine Parameter zum Plugin wie die verwendete SoCo Version angezeigt.
Weiterhin wird die Anzahl der Speaker angezeigt, die aktuell online und verwendbar sind.


SmartVisu Widget
================

Zur Nutzung des Sonos Widgets für SmartVisu die Dateien (html, css, js) unter
``plugins/sonos/sv_widget`` in den Ordner ``dropins/widgets`` der SmartVisu kopieren.

Sofern alle Sonos items gemäß Beispiel Struct definiert worden sind, wird das Widget so integriert:

```html
{% import "widget_sonos.html" as sonos %}
{% block content %}

<div class="block">
  <div class="set-2" data-role="collapsible-set" data-theme="c" data-content-theme="a" data-mini="true">
    <div data-role="collapsible" data-collapsed="false" >
      {{ sonos.player('sonos_kueche', 'Sonos.Kueche') }}
    </div>
  </div>
</div>

{% endblock %}


Version History
===============

