yamahayxc
#########

Ein Plugin zur Steuerung von Yamaha MusicCast-kompatiblen Geräten (Receiver, Streaminglautsprecher u.ä.), z.B. An/Aus, Eingangswahl, Lautstärke und Mute, Play/Pause, aktuellen Status lesen

Die Grundlage für das Plugin wurde schamlos bei Raoul Thill geklaut, dem Autor des yamaha-Plugins für ältere Yamaha-Receiver in SmartHomeNG.


Anmerkungen
===========

Das Plugin wird nach Bedarf weiterentwickelt und unterstützt noch längst nicht alle möglichen Funktionen, die im Yamaha Extended Control (YXC)-Standard definiert sind. Ich nutze es aber selbst täglich. Die genutzten und getesteten Geräte sind RX-V483, ISX-18D und WX-010.
Das Plugin nutzt die YXC API, welche auf dem Austausch von JSON-formatierten Daten basiert. Es abonniert die Daten der konfigurierten Geräte, um laufend mit Statusmeldungen versorgt zu werden. Diese werden per UDP verteilt, solange eine Kommunikation zwischen Client (Plugin) und Gerät erfolgt, und 10 Minuten nach der letzten Kommunikation. Das Plugin kann mit mehreren Verbindungen gleichzeitig umgehen. Bisher habe ich keine Fehler feststellen können, aber ich habe nur 5 Geräte zum Testen.

Items können nach eigenen Vorstellungen eingerichtet werden; sie werden vom Plugin durch das Item-Attribut ``yamahayxc_cmd`` identifiziert. ``yamahayxc_host`` und ``yamahayxc_zone`` müssen nicht direkt im Steuerungs-/Statusitems stehen - das Plugin sucht sie in den Vorfahren-Items nach oben. Dadurch können Items beliebig tief verschachtelt werden, z.B. um Fähigkeits-Items als Unteritems ihres jeweiligen Werte-Items abzulegen.

Das ``update``-Item (in Struct ``yamahayxc.amp``) hat keine eigene Funktion, sondern fragt beim Setzen aktiv den kompletten Status des Geräts ab (alle Zonen + netusb + Tuner + Link + Alarm). Nach jedem Schreiben eines beliebigen anderen Items aktualisiert das Plugin ohnehin automatisch den betroffenen Bereich (z.B. nur die geänderte Zone bei einem Zonen-Item, nur netusb bei einem netusb-Item, usw.) - ein komplettes ``update`` ist also i.d.R. nicht nötig, außer beim Timeout des 10-Minuten-Abonnements. Für einen gezielten, aber nicht vollständigen Refresh gibt es zusätzlich ``update_dsp`` (in Struct ``dsp``/``dsp_content``), ``update_netusb`` (in ``media.netusb``/``netusb``) sowie ``update_tuner``/``update_link``.

Änderungen, Hinweise und Erweiterungen werden jederzeit angenommen, Wünsche können etwas dauern...

Neben `main` unterstützt das Plugin jetzt auch eigene Structs für `zone2`, `zone3` und `zone4` (``yamahayxc.zone2``/``yamahayxc.zone3``/``yamahayxc.zone4``, jeweils mit ``power``/``volume``/``mute``/``sleep``/``input``/``wakeup``/``update`` sowie den zonenspezifischen Link-Reglern ``link_control``/``link_audio_delay``/``link_audio_quality`` - inhaltlich dasselbe wie ``amp``, nur für die jeweils andere Zone). Jedes dieser drei Structs bringt zusätzlich ein ``present``-Item (r/o, bool) mit: erst ``True``, wenn das Gerät die Zone laut ``getFeatures`` tatsächlich meldet - so kann eine Visu Zonen-Regler ein-/ausblenden, ohne raten zu müssen. ``amp`` (main) hat kein ``present``, da main immer existiert. `netusb`-Funktionen (Wiedergabe, Presets, Titel/Interpret) sind weiterhin geräteweit (nicht zonenspezifisch), wie es der YXC-Standard vorsieht. Da mir keine Mehrzonen-Hardware zum Testen zur Verfügung steht, ist dieser Teil nur gegen die offizielle YXC-Spezifikation entwickelt, nicht gegen echte Geräte getestet - Rückmeldungen sind willkommen.

Der Tuner (AM/FM) wird jetzt ebenfalls unterstützt: Band/Frequenz einstellen, Sendersuchlauf, Presets abrufen/speichern/löschen/durchschalten (siehe Struct ``yamahayxc.tuner``). DAB und das Umsortieren von Presets (``movePreset``) sind bewusst nicht implementiert - DAB, weil ich keine Testgeräte habe, ``movePreset`` weil es zwei Parameter (Quell- und Zielposition) braucht und sich nicht in das Ein-Item-ein-Wert-Schema des Plugins einfügt; über ``passthru`` bleibt es trotzdem erreichbar.

Klangfeld/DSP-Funktionen (Sound Program, 3D Surround, Direct, Pure Direct, Enhancer, Klangregelung, Equalizer, Balance) sind jetzt ebenfalls verfügbar (siehe Struct ``yamahayxc.dsp``), zonenspezifisch und je nach Gerät unterschiedlich verfügbar. Für die Bool-Werte (``surround_3d``/``direct``/``pure_direct``/``enhancer``) folgt das Plugin dem in der YXC-Spezifikation dokumentierten Typ (JSON-Bool); konnte ich für diese neuen Items nicht an echter Hardware verifizieren - Rückmeldungen sind willkommen. ``mute``/die Alarm-Items akzeptieren seit einem Bugfix beide Repräsentationen (natives JSON-Bool *und* String ``"true"``/``"false"``) - ein Gerät, das ein natives Bool sendet, ließ das Item nach jedem Schreiben durch den synchronen Zonen-Refresh sofort wieder auf ``False`` zurückfallen, da bis dahin nur der String-Vergleich unterstützt wurde. Im Struct sind Bass/Höhen/Balance unter ``tone`` gruppiert (``tone.bass``/``tone.treble``/``tone.balance``) und Equalizer-Bänder unter ``equalizer`` (``equalizer.low``/``equalizer.mid``/``equalizer.high``); ``tone_control_mode``/``equalizer_mode`` bleiben eigenständige Geschwister-Items, da sie für die jeweilige Gruppe insgesamt gelten. Zusätzlich gibt es ``dsp.available`` (r/o, bool): true, sobald die Zone laut ``getFeatures`` irgendeine DSP-Fähigkeit meldet (Sound Program oder einen der Klangfeld-Funktionsnamen) - praktisch z.B. um in einer Visu ein DSP-Popup nur anzuzeigen, wenn es auch etwas zu bedienen gibt.

**Breaking Change / Migration:** Vor dieser Umstellung lagen ``tone_bass``/``tone_treble``/``eq_low``/``eq_mid``/``eq_high``/``balance`` als flache Items direkt unter dem Geräteitem. Wer das Struct ``yamahayxc.dsp`` nutzt, muss vorhandene Item-Referenzen (Visu-Widgets, Logiken) auf die neuen Pfade umstellen. Für einen schrittweisen Umzug ohne Ausfallzeit gibt es das Struct ``yamahayxc.dsp_bridge``: es bindet ``yamahayxc.dsp`` (neue Pfade) ein und ergänzt zusätzlich die sechs alten flachen Items - beide Pfad-Sätze sind dann gleichzeitig live (dasselbe ``yamahayxc_cmd`` kann jetzt auf mehrere Items gleichzeitig registriert werden, alle erhalten Updates). Nach dem Umzug der Referenzen die sechs alten Items aus der eigenen Konfiguration entfernen bzw. zurück auf ``yamahayxc.dsp`` wechseln. ``volume`` selbst ist **nicht** betroffen - der Pfad ist unverändert, es kamen nur Unteritems hinzu.

**Weitere Struct-Umstellung - ``basic`` wurde zu ``amp`` + ``netusb`` aufgeteilt:** Das bisherige Struct ``basic`` vermischte zonenspezifische Verstärkersteuerung (power/volume/mute/sleep/input) mit geräteweiter netusb-Wiedergabe (track/artist/albumart/playback/preset/curtime/totaltime/passthru/playing/standby) - bei Mehrzonen-Geräten führte das dazu, dass die netusb-Items bei jeder zusätzlich mit ``basic`` ausgestatteten Zone dupliziert wurden. Neu:

- ``yamahayxc.amp`` - Verstärker-/Zonenkern (power/volume/mute/sleep/input) plus die zonenspezifischen Link-Regler (``link_control``/``link_audio_delay``/``link_audio_quality``), Ersatz für ``basic``. Zusätzlich ``input.sources`` (Liste der vom Gerät gemeldeten gültigen Eingänge, per ``getFeatures``, analog zu ``volume.min``/``max``). Für `zone2`/`zone3`/`zone4` gibt es die inhaltlich identischen Structs ``yamahayxc.zone2``/``zone3``/``zone4`` (siehe oben, inkl. ``present``).
- ``yamahayxc.netusb`` - die bisherigen netusb-Items, jetzt eigenständig; kombinieren mit ``amp`` wie gehabt: ``struct: [yamahayxc.amp, yamahayxc.netusb]`` (``playing``/``standby`` benötigen ``power`` aus ``amp``, um korrekt aufzulösen).
- ``yamahayxc.alarm`` ist jetzt ebenfalls eigenständig (nur die drei Alarm-Items) statt automatisch ``basic`` einzubinden - kombinieren wie ``dsp``/``tuner``/``link``: ``struct: [yamahayxc.amp, yamahayxc.alarm]``.
- ``yamahayxc.tuner``/``link``/``netusb`` sind jetzt alle Aliase auf Unterbäume eines gemeinsamen, selbst nicht direkt zu verwendenden Structs ``yamahayxc.media`` (``media.tuner``/``media.netusb``/``media.link``) - inhaltlich unverändert (bis auf die drei Link-Regler, siehe unten), nur intern anders organisiert. ``media`` heißt so (vormals ``zone``), weil es inzwischen wirklich rein geräteweit ist und beliebig oft/einmal pro Host kombiniert werden kann, ohne dass etwas dupliziert.
- ``yamahayxc.dsp`` ist jetzt ebenfalls ein eigenständiger Alias (auf ``dsp_content``) statt Teil des alten ``zone``-Structs - DSP ist wie ``amp`` zonenspezifisch, gehörte also nie wirklich zu den geräteweiten netusb/tuner/link-Funktionen.

**Weitere Breaking Change:** ``struct: yamahayxc.link`` allein (ohne ``amp`` kombiniert) enthält ``link_control``/``link_audio_delay``/``link_audio_quality`` nicht mehr - die kommen jetzt aus ``amp``/``zone2``/``zone3``/``zone4``, da sie laut Spezifikation zonenspezifisch sind (anders als der Rest von Link). Jedes dokumentierte Beispiel kombiniert ohnehin bereits ``[amp, ..., link]``, wo die Items am selben Pfad landen wie vorher (nur aus einem anderen Struct stammend) - betroffen ist also nur eine alleinstehende ``link``-Nutzung, nicht der übliche Fall.

Migration wie beim DSP-Umzug: ``yamahayxc.legacy_basic`` ist ein eingefrorener Schnappschuss des alten ``basic``-Structs (identische Item-Pfade, keine Anpassung nötig), ``yamahayxc.legacy_alarm`` entsprechend für das alte ``alarm``. Wer ``struct: yamahayxc.basic`` bzw. ``yamahayxc.alarm`` verwendet, kann einfach auf ``yamahayxc.legacy_basic``/``yamahayxc.legacy_alarm`` umbenennen und später in Ruhe auf ``[yamahayxc.amp, yamahayxc.netusb]`` umstellen.

**MusicCast Link (Multiroom) - inzwischen an echter Mehrgeräte-Hardware getestet (Grundfunktionen), Details siehe unten.** Struct ``yamahayxc.link`` bietet eine vereinfachte Sicht auf die rohen YXC ``dist/*``-Primitiven:

- ``linked`` (r/o, bool) ist das primäre "bin ich überhaupt gruppiert?"-Signal, abgeleitet aus ``group_id``. Laut YXC-Spezifikation (Advanced) wird ``group_id`` beim Trennen auf eine 32-stellige Null-Hex-ID ("000...") zurückgesetzt - das ist offiziell dokumentiertes Verhalten, kein Gerätefehler.
- ``role`` (r/o, 'server'/'client'/'none') wird auf ``linked`` abgestimmt: sobald ``linked`` false ist, liefert das Item **immer** 'none', unabhängig davon, was das Gerät selbst gerade meldet. Grund: An echter Hardware (bestätigt sowohl über einen ``leave`` dieses Plugins als auch unabhängig über die MusicCast-App) wurde beobachtet, dass ein Gerät nach dem Trennen weiterhin ``role: client`` meldet, während ``group_id`` bereits korrekt auf Null steht - ``role`` allein ist also kein verlässliches Signal, ``group_id``/``linked`` sind es.
- ``available_devices`` (r/o, Liste) listet alle Hosts, für die dieses Plugin mindestens ein Item konfiguriert hat (reines Plugin-Bookkeeping, kein Gerätestatus) - gedacht als Grundlage für eine Visu-Dropdown-Auswahl für ``client.join``/``server.add_device``. Steht bereits direkt nach dem Plugin-Start zur Verfügung, unabhängig davon, ob das Gerät erreichbar ist, und bleibt auch danach aktuell: Wird zur Laufzeit ein Item (Admin-UI) mit ``yamahayxc_host`` angelegt, bearbeitet (z.B. Hostname geändert) oder gelöscht, aktualisiert sich die Liste auf allen betroffenen Geräten sofort, ohne auf die nächste Geräteabfrage zu warten - sobald das letzte Item für einen Host verschwindet, wird auch dessen Eintrag entfernt.
- Server- und Client-Aktionen/-Infos sind in ``server``/``client`` unterverschachtelt - beide Gruppen existieren auf jedem Gerät gleichzeitig (welche gerade zutrifft, zeigt ``role``):

  - ``server.linked_devices`` (r/o, Liste der Client-IPs) ist nur gefüllt, während ``role`` 'server' ist - ein Client kennt laut Spezifikation seine Mitspieler nicht, nur der Server führt die Liste.
  - ``server.add_device``/``server.remove_device`` (als/werde Server, Ziel-Host als Client hinzufügen/entfernen), ``server.disband`` (eigene Rolle komplett aufgeben, Verteilung endet damit).
  - ``client.join`` (Wert = Ziel-Host, wird Client davon), ``client.leave`` (die Gruppe verlassen).

  Alle fünf sind bool- oder String-Trigger-Items: ``enforce_updates`` ist gesetzt, und die reinen bool-Trigger (``server.disband``/``client.leave``/``update``) setzen sich nach getaner Aktion selbst auf ``False`` zurück (kein manuelles Aus-/Wieder-Einschalten nötig, um sie erneut auszulösen) - ``client.join``/``server.add_device``/``server.remove_device`` behalten ihren zuletzt geschriebenen Zielwert. Ein reines "Verteilung pausieren, Gruppe behalten" (YXC ``stopDistribution``) gibt es bewusst nicht als eigenes Item - dafür fehlt ein klarer Wiederaufnahme-Weg und ein praktischer Anwendungsfall; bei Bedarf später nachrüstbar.
- Selten benötigte/rohe Felder (``group_id``, ``group_name``, ``server_zone``, ``audio_dropout``, ``control``, ``audio_delay``, ``audio_quality``) liegen unter ``options`` - ``options.group_id`` insbesondere bleibt bewusst sichtbar, da ``linked`` genau davon abgeleitet wird.

Diese Orchestrierungs-Funktionen (``client.join``/``server.add_device``/``server.remove_device``/``client.leave``/``server.disband``) rufen mehrere API-Aufrufe über zwei Geräte hinweg auf (Client + Master), wie es die YXC-Spezifikation (Advanced) in Abschnitt 9.1 beschreibt. Zwei konkrete Unsicherheiten bleiben (unabhängig von den o.g. Grundfunktionen, die inzwischen getestet sind):

- Der ``num``-Parameter von ``startDistribution`` ("Link distribution number") ist in der Spezifikation nicht eindeutig definiert; das Plugin verwendet einen einfachen, pro Plugin-Instanz hochzählenden Zähler als bestmögliche Interpretation.
- Antwortcode 200/201 bedeutet laut Spezifikation "Linking/Unlinking in progress" - diese Vorgänge laufen also asynchron auf dem Gerät. Das Plugin wartet den Abschluss nicht ab, sondern verlässt sich auf die nächste Statusabfrage bzw. Push-Benachrichtigung.

Bitte weiterhin Rückmeldungen zu ungewöhnlichem Verhalten geben, insbesondere bei mehr als zwei Geräten oder verschachtelten Gruppen-Operationen - bisher nur mit zwei Geräten (1 Server, 1 Client) getestet.

Für Lautstärke und die Klangfeld-Wertebereiche (Bass/Höhen, Equalizer, Balance) liest das Plugin per ``getFeatures`` den vom Gerät gemeldeten min/max/step-Bereich aus und stellt ihn als read-only Unteritems bereit (z.B. ``volume.min``/``volume.max``/``volume.step``, ``tone.bass.min``/..., ``equalizer.low.min``/...). Da diese Werte beim Start einmalig abgefragt werden und sich zur Laufzeit nicht ändern, aktualisieren sie sich nicht laufend. ``volume`` selbst ist standardmäßig auf 0..100 Prozent skaliert (beschreibbar, Umrechnung anhand von ``volume.min``/``volume.max``, im Plugin selbst berechnet, nicht per eval-Struct) - die Lautstärke in reinen Gerätewerten liegt unter ``volume.raw``. Damit kann eine Visu ``volume`` immer mit einer festen 0..100-Skala verwenden, unabhängig vom tatsächlichen Gerätebereich.

Genauso liest das Plugin für jedes Item mit einer festen Werteliste (statt eines Zahlenbereichs) die vom Gerät tatsächlich unterstützten Werte per ``getFeatures`` aus und stellt sie als read-only Listen-Unteritem ``<item>.values`` bereit: ``input.sources`` (bereits länger vorhanden), sowie neu ``sound_program.values``, ``tone_control_mode.values``, ``equalizer_mode.values``, ``link_control.values``, ``link_audio_delay.values`` und ``link_audio_quality.values``. Meldet ein Gerät eine bestimmte Liste nicht (modellabhängig - z.B. ``tone_control_mode_list``/``equalizer_mode_list`` fehlen auf manchen Geräten ganz), bleibt das jeweilige ``.values``-Item einfach leer (``[]``), statt einen Platzhalter oder Fehler zu erzeugen.

Beim Start fragt das Plugin pro Gerät ``getFeatures`` ab und merkt sich, welche Befehle (power/volume/mute) und Eingänge in der jeweiligen Zone tatsächlich unterstützt werden. Nicht unterstützte Befehle/Eingänge werden abgelehnt (mit Logmeldung), Lautstärkewerte werden auf den vom Gerät gemeldeten Bereich (min/max/step) begrenzt. Ist das Gerät beim Start nicht erreichbar, wird diese Prüfung übersprungen und wie bisher ungeprüft gesendet.

Inhalte durchsuchen (UPnP/USB/DLNA, z.B. um wie in der MusicCast-App durch USB-Ordner oder einen Medienserver zu navigieren) ist jetzt ebenfalls möglich, über ``getListInfo``/``setListControl`` (siehe Struct ``media.netusb``/``netusb``, Unteritem ``browse``): ``browse.list`` liefert die aktuelle Seite (bis zu 8 Einträge je ``getListInfo``-Aufruf, ``.attribute`` je Eintrag zeigt u.a. an, ob er auswählbar (Ordner) und/oder abspielbar (Datei) ist), ``browse.page`` fordert eine bestimmte Seite an (wird intern auf ein Vielfaches von 8 abgerundet), ``browse.select``/``browse.play`` nehmen den absoluten Index eines Eintrags (``browse.index`` + Position in ``browse.list``), ``browse.return`` wechselt eine Ebene nach oben (bool-Trigger, setzt sich selbst zurück). Zwei Dinge sind dabei laut Spezifikation zu beachten, nicht nur Implementierungsdetails dieses Plugins: Die Navigationsposition ist geräteweit **eine** geteilte Cursor-Position, nicht pro Client/Zone getrennt - parallele Nutzung über die MusicCast-App oder eine zweite Visu-Sitzung überschneidet sich also. Und ``getListInfo`` kann das Gerät laut Spezifikation bis zu 30 Sekunden lang blockieren (keine andere Anfrage wird währenddessen angenommen) - deutlich länger als der sonstige Standard-Timeout des Plugins, ``browse.busy`` zeigt an, während ein Abruf läuft. ``browse.play`` spielt vorerst immer in Zone "main" ab (Suche über ``setSearchString`` ist noch nicht implementiert). Gegen die offizielle YXC-Spezifikation entwickelt, noch nicht an echter Hardware getestet - Rückmeldungen sind willkommen.

Zusätzlich zu select/play/return unterstützt ``browse`` jetzt auch die vier Aktionen aus dem "..."-Kontextmenü der echten MusicCast-App: ``browse.play_now`` (sofort abspielen, unterbricht laufende Wiedergabe), ``browse.play_next`` (nach aktuellem Titel einreihen), ``browse.queue_add`` (ans Ende der Warteschlange anhängen) und ``browse.playlist_add`` (einer der bis zu 5 benannten MusicCast-Playlisten hinzufügen - welche, wird vorher über ``browse.playlist_bank`` gewählt, 1-5, gerätespezifisch, muss vor dem ersten ``playlist_add`` gesetzt sein). Alle vier nehmen wie ``browse.select``/``browse.play`` den absoluten Index eines Eintrags. **Wichtig:** Diese vier sind nicht Teil der offiziellen YXC-Spezifikation - ``getListInfo``s ``list_info[].attribute``-Bitmaske zeigt zwar pro Eintrag an, ob er dafür geeignet ist (Bits 23-26: Play Now / Play Next / Add Play Queue / Add MusicCast Playlist), aber weder ``setListControl`` noch ``managePlay``/``manageList`` dokumentieren dafür einen ``type``-Wert - die Spezifikation kennt bei ``manageList`` nur Streaming-Dienst-spezifisches Bookmarking (``add_bookmark``/``add_track``/``add_to_playlist``/... für Napster/Pandora/JUKE/Qobuz/TIDAL/Deezer). Die tatsächlich verwendeten Werte (``play_now``/``play_next``/``add_to_queue``/``add_to_mc_playlist``, alle über ``manageList``) stammen aus einem Netzwerkmitschnitt der echten App - siehe ``_build_cmd_manage_list()`` im Plugincode. Entsprechend unklar/unbestätigt: ob diese Werte über alle netusb-Quellen (USB/Server/Streaming-Dienste) hinweg gleich funktionieren, oder Geräte-/Firmware-abhängig variieren. Rückmeldungen zu abweichendem Verhalten sind besonders hier willkommen. ``browse.play_now`` funktioniert dabei nicht nur auf einzelnen Titeln, sondern genauso auf Ordner-/Album-Einträgen (per Mitschnitt bestätigt) - spielt dann offenbar das ganze Album/den ganzen Ordner ab dem ersten Titel.

Ebenfalls per Mitschnitt gefunden und implementiert: die eigentliche Wiedergabe-Warteschlange, komplett unter ``media.netusb``/``netusb``, Unteritem ``queue`` - taucht in der Spezifikation nicht einmal als "Reserved" auf (nur ``getStatus.play_queue`` und ``getPlayInfo.play_queue_type`` deuten überhaupt an, dass es sowas gibt). ``queue.list``/``queue.max_line``/``queue.playing_index`` (per ``getPlayQueue``) zeigen die aktuelle Warteschlange - **eigener Index-Raum**, nicht derselbe wie ``browse.index``/``browse.list``: ``queue.play``/``queue.delete`` beziehen sich auf die Position *in der Warteschlange*, nicht auf die Position in der gerade durchsuchten Liste (``delete`` statt ``remove``, da letzteres mit ``Item.remove()`` kollidiert). ``queue.save_playlist`` (bool-Trigger) sichert die *komplette* Warteschlange als über ``browse.playlist_bank`` gewählte Playliste - dieselbe Bank-Auswahl wie ``browse.playlist_add``, aber ganze Warteschlange statt einzelnem Eintrag. ``queue.clear`` leert sie, ``queue.update`` fragt sie manuell neu ab. Anders als ``browse.list`` (feste 8er-Seiten laut Spezifikation) lieferte ein einzelner Abruf im Mitschnitt alle 21 Einträge einer Warteschlange auf einmal zurück - das Plugin implementiert deshalb (noch) keine Seitenweise-Abfrage für ``queue.list``, Verhalten bei sehr langen Warteschlangen ist unbestätigt. ``queue_type`` (auf ``netusb``-Ebene, neben ``repeat``/``shuffle``) zeigt die Art der aktuellen Warteschlange (beobachteter Wert: ``"user"``).

Ergänzend zu ``playlist_bank``/``playlist_add`` (Playlisten-Verwaltung, ebenfalls per Mitschnitt gefunden, nicht in der Spezifikation - nicht mal als "Reserved"): ``browse.playlist_names`` liefert die Namen aller 5 Playlisten (``getMcPlaylistName``, Index 0 = Bank 1, per Mitschnitt bestätigt - Umbenennen von Bank 1 änderte ``name_list[0]``), ``browse.playlist_rename`` benennt die über ``playlist_bank`` gewählte Playliste um (``setMcPlaylistName``, aktualisiert ``playlist_names`` danach automatisch), ``browse.playlist_clear`` leert sie (``clearMcPlaylist``, Name bleibt erhalten). ``playlist_names`` wird nicht laufend abgefragt (ändert sich selten) - neben der automatischen Aktualisierung nach ``playlist_rename`` lässt sich das gemeinsame ``media.netusb.update`` (bzw. ``update_netusb``) jederzeit manuell dafür nutzen, es aktualisiert jetzt beides (Wiedergabestatus und Playlistennamen).

Wiederhol- und Zufallswiedergabemodus sind ebenfalls verfügbar: ``media.netusb``/``netusb`` bekommt neu ``repeat`` (Werte ``off``/``one``/``all``) und ``shuffle`` (Werte ``off``/``on``/``songs``/``albums``, geräteabhängig), beide beschreibbar über ``setRepeat``/``setShuffle``. Die jeweils gültigen Werte liefert das Gerät ohnehin bei jeder ``getPlayInfo``-Abfrage mit, verfügbar als read-only ``repeat_available``/``shuffle_available`` - keine zusätzliche Abfrage nötig. Anders als bei ``input``/``sound_program`` etc. werden geschriebene Werte hier nicht gegen die Werteliste geprüft (die stammt aus ``getPlayInfo``, nicht aus dem sonst für ``list_check`` genutzten zonenbezogenen ``getFeatures``) - ein ungültiger Wert wird einfach ans Gerät weitergereicht und von dort ggf. mit einem Fehler-``response_code`` abgelehnt (im Log als Warnung sichtbar).

Seit SmartHomeNG v1.7 werden Item-Structs bereitgestellt, mit denen die Funktionalitäten eines einfachen Players und zusätzlich Weckerfunktionen genutzt werden können.


Anforderungen
=============

Das folgende Python-Modul muss vorhanden sein:

  - requests

Dies wird normalerweise durch SmartHomeNG automatisch installiert. Wer es manuell installieren möchte, kann das über das PIP-Tool oder über die Distribution tun:

.. code-block:: bash

    # Python
    pip3 install requests

    # Debian based
    sudo apt-get install python3-requests

    # Arch Linux
    sudo pacman -S python-requests

    # Fedora
    sudo dnf install python3-requests


Konfiguration
=============

plugin.yaml
-----------

.. code-block:: yaml

    yamahayxc:
        plugin_name = YamahaYXC


items.yaml
----------

.. code-block:: yaml

    media:
        wx010:
            yamahayxc_host: 192.168.2.211
            yamahayxc_zone: main

            struct: [yamahayxc.amp, yamahayxc.netusb]


Zweite Zone desselben Geräts (z.B. Receiver mit `main` + `zone2`): einfach ein zweites Geräte-Item mit derselben ``yamahayxc_host``, aber anderer ``yamahayxc_zone`` anlegen, und dafür ``yamahayxc.zone2``/``zone3``/``zone4`` statt ``yamahayxc.amp`` verwenden (inhaltlich identisch, inklusive ``present``). ``netusb`` nur bei **einer** der Zonen einbinden (netusb ist geräteweit, nicht zonenspezifisch - würde sonst pro Zone dupliziert):

.. code-block:: yaml

    media:
        avr_main:
            yamahayxc_host: 192.168.2.212
            yamahayxc_zone: main

            struct: [yamahayxc.amp, yamahayxc.netusb]

        avr_zone2:
            yamahayxc_host: 192.168.2.212
            yamahayxc_zone: zone2

            struct: yamahayxc.zone2


oder ohne Item-Structs (mit identischem Resultat zu ``[yamahayxc.amp, yamahayxc.netusb]`` kombiniert auf einem Item - die ``amp``-Items direkt unter dem Geräteitem, die ``netusb``-Items ab dem Track-Abschnitt weiter unten):

.. code-block:: yaml

    media:

        wx010:
            yamahayxc_host: 192.168.2.211
            yamahayxc_zone: main

    # writable items to control device/playback
            # True = power on, False = standby
            power:
                type: bool
                yamahayxc_cmd: power
                enforce_updates: 'True'

            # numeric volume. Range is 0..60 on my devices. May vary
            volume:
                type: num
                yamahayxc_cmd: volume
                enforce_updates: 'True'

                # optional: device-reported range, fetched once via getFeatures
                min:
                    type: num
                    yamahayxc_cmd: volume_min
                    visu_acl: ro
                max:
                    type: num
                    yamahayxc_cmd: volume_max
                    visu_acl: ro
                step:
                    type: num
                    yamahayxc_cmd: volume_step
                    visu_acl: ro
                # optional: r/w volume scaled to 0..100 using min/max above
                percent:
                    type: num
                    yamahayxc_cmd: volume_percent
                    visu_acl: rw
                    enforce_updates: 'True'

            # True = mute enable, False = mute disable
            mute:
                type: bool
                yamahayxc_cmd: mute
                enforce_updates: 'True'

            # input source as string. Heavily dependent on device.
            input:
                type: str
                yamahayxc_cmd: input
                enforce_updates: 'True'

                # optional: device-reported list of valid input values,
                # fetched once via getFeatures
                sources:
                    type: list
                    yamahayxc_cmd: input_sources
                    visu_acl: ro

            # possible values are 'play', 'stop', 'pause', 'previous', 'next'...
            # (netusb from here on - device-global, not zone-specific)
            playback:
                type: str
                yamahayxc_cmd: playback
                enforce_updates: 'True'

            # repeat mode, valid values in repeat_available below ('off'/'one'/'all')
            repeat:
                type: str
                yamahayxc_cmd: repeat
                enforce_updates: 'True'

            # shuffle mode, valid values in shuffle_available below
            # ('off'/'on'/'songs'/'albums')
            shuffle:
                type: str
                yamahayxc_cmd: shuffle
                enforce_updates: 'True'

            # values are numeric and can (as of now) not be queried by the plugin
            preset:
                type: num
                yamahayxc_cmd: preset
                enforce_updates: 'True'

            # values are numeric and can be 0 / 30 / 60 / 90 / 120 [minutes]
            sleep:
                type: num
                yamahayxc_cmd: sleep
                enforce_updates: 'True'
                
    # read-only items to monitor device/playback status
            # name of current track, if available
            track:
                type: str
                yamahayxc_cmd: track

            # name of current artist, if available. Radio station name for net_radio
            artist:
                type: str
                yamahayxc_cmd: artist

            # this is the URL of current album art image, if supported / supplied
            # it is hosted on the respective yamaha device
            albumart:
                type: str
                yamahayxc_cmd: albumart

            # current time of playback in percent of total_time
            # -1 if total_time is not available
            play_pos:
                type: num
                yamahayxc_cmd: play_time

            # total time of playback in seconds. 0 if not applicable / available
            totaltime:
                type: num
                yamahayxc_cmd: total_time

            # currently valid values for repeat/shuffle above, straight off
            # getPlayInfo (not a separate query)
            repeat_available:
                type: list
                yamahayxc_cmd: repeat_available

            shuffle_available:
                type: list
                yamahayxc_cmd: shuffle_available

    # write-only item to pass arbitrary command. Use at own discretion
            passthru:
                type: str
                yamahayxc_cmd: passthru
                enforce_updates: 'True'

    # write-only item to force a full refresh (all zones + netusb + tuner +
    # link + alarm). See notes above - update_dsp/update_netusb/update_tuner/
    # update_link give a narrower, category-scoped refresh instead.
             update:
                type: bool
                yamahayxc_cmd: state
                enforce_updates: 'True'


    # the following items are only valid for devices with alarm clock functions
    # these are included in addition to the others from the 'alarm' struct:

            # enable / disable alarm function
            alarm_on:
                type: bool
                yamahayxc_cmd: alarm_on
                enforce_updates: 'True'

            # enable / disable alarm beep (solo or in addition to music)
            alarm_beep:
                type: bool
                yamahayxc_cmd: alarm_beep
                enforce_updates: 'True'

            # get/set alarm time. Formatted as 4 digit 24 hour string
            alarm_time:
                type: str
                yamahayxc_cmd: alarm_time
                enforce_updates: 'True'


    # the following items are only valid for devices with a tuner (AM/FM);
    # also available as struct 'yamahayxc.tuner' (alias for media.tuner),
    # device-global (nicht zonenspezifisch). Item-Namen ohne 'tuner_'-Präfix,
    # der Pfad (tuner.band statt tuner_band) gibt den Kontext bereits vor.
            tuner:

                # band auswählen, 'am' oder 'fm'
                band:
                    type: str
                    yamahayxc_cmd: tuner_band
                    enforce_updates: 'True'

                # Frequenz direkt einstellen, in kHz (z.B. 87500 = 87,5 MHz)
                freq:
                    type: num
                    yamahayxc_cmd: tuner_freq
                    enforce_updates: 'True'

                # Sendersuchlauf: 'up' / 'down' / 'cancel' / 'auto_up' / 'auto_down' / 'tp_up' / 'tp_down'
                seek:
                    type: str
                    yamahayxc_cmd: tuner_seek
                    enforce_updates: 'True'

                # aktuell empfangen? (read-only)
                tuned:
                    type: bool
                    yamahayxc_cmd: tuner_tuned

                # Sendername/RDS-Text, falls verfügbar (read-only)
                station:
                    type: str
                    yamahayxc_cmd: tuner_station

                # Preset abrufen (Nummer je nach Gerät)
                preset:
                    type: num
                    yamahayxc_cmd: tuner_preset
                    enforce_updates: 'True'

                # aktuellen Sender auf Preset-Nummer speichern
                preset_store:
                    type: num
                    yamahayxc_cmd: tuner_preset_store
                    enforce_updates: 'True'

                # Preset-Nummer löschen
                preset_clear:
                    type: num
                    yamahayxc_cmd: tuner_preset_clear
                    enforce_updates: 'True'

                # zum nächsten/vorherigen Preset wechseln: 'next' / 'previous'
                preset_switch:
                    type: str
                    yamahayxc_cmd: tuner_preset_switch
                    enforce_updates: 'True'


    # die folgenden Items steuern Klangfeld/DSP-Funktionen (geräteabhängig);
    # auch als Struct 'yamahayxc.dsp' verfügbar, zonenspezifisch

            # Sound Program auswählen (z.B. 'munich', 'straight', ... - geräteabhängig)
            sound_program:
                type: str
                yamahayxc_cmd: sound_program
                enforce_updates: 'True'

            # 3D Surround an/aus
            surround_3d:
                type: bool
                yamahayxc_cmd: surround_3d
                enforce_updates: 'True'

            # Direct-Modus an/aus
            direct:
                type: bool
                yamahayxc_cmd: direct
                enforce_updates: 'True'

            # Pure-Direct-Modus an/aus
            pure_direct:
                type: bool
                yamahayxc_cmd: pure_direct
                enforce_updates: 'True'

            # Enhancer an/aus
            enhancer:
                type: bool
                yamahayxc_cmd: enhancer
                enforce_updates: 'True'

            # Klangregelungs-Modus, z.B. 'manual' / 'auto' / 'bypass' (geräteabhängig)
            tone_control_mode:
                type: str
                yamahayxc_cmd: tone_control_mode
                enforce_updates: 'True'

            # tone/bass/höhen/balance gruppiert unter 'tone', jeweils mit
            # optionalem min/max/step-Unteritem (gerätespezifischer Bereich,
            # via getFeatures)
            tone:

                # Bass-Wert (nur wirksam bei tone_control_mode=manual)
                bass:
                    type: num
                    yamahayxc_cmd: tone_bass
                    enforce_updates: 'True'
                    min:
                        type: num
                        yamahayxc_cmd: tone_bass_min
                        visu_acl: ro
                    max:
                        type: num
                        yamahayxc_cmd: tone_bass_max
                        visu_acl: ro
                    step:
                        type: num
                        yamahayxc_cmd: tone_bass_step
                        visu_acl: ro

                # Höhen-Wert (nur wirksam bei tone_control_mode=manual)
                treble:
                    type: num
                    yamahayxc_cmd: tone_treble
                    enforce_updates: 'True'
                    min:
                        type: num
                        yamahayxc_cmd: tone_treble_min
                        visu_acl: ro
                    max:
                        type: num
                        yamahayxc_cmd: tone_treble_max
                        visu_acl: ro
                    step:
                        type: num
                        yamahayxc_cmd: tone_treble_step
                        visu_acl: ro

                # L/R-Balance, negativ=links, positiv=rechts
                balance:
                    type: num
                    yamahayxc_cmd: balance
                    enforce_updates: 'True'
                    min:
                        type: num
                        yamahayxc_cmd: balance_min
                        visu_acl: ro
                    max:
                        type: num
                        yamahayxc_cmd: balance_max
                        visu_acl: ro
                    step:
                        type: num
                        yamahayxc_cmd: balance_step
                        visu_acl: ro

            # Equalizer-Modus, z.B. 'manual' / 'auto' / 'bypass' (geräteabhängig)
            equalizer_mode:
                type: str
                yamahayxc_cmd: equalizer_mode
                enforce_updates: 'True'

            # Equalizer-Bänder gruppiert unter 'equalizer', jeweils mit
            # optionalem min/max/step-Unteritem
            equalizer:

                # Equalizer tiefe Frequenzen (nur wirksam bei equalizer_mode=manual)
                low:
                    type: num
                    yamahayxc_cmd: eq_low
                    enforce_updates: 'True'
                    min:
                        type: num
                        yamahayxc_cmd: eq_low_min
                        visu_acl: ro
                    max:
                        type: num
                        yamahayxc_cmd: eq_low_max
                        visu_acl: ro
                    step:
                        type: num
                        yamahayxc_cmd: eq_low_step
                        visu_acl: ro

                # Equalizer mittlere Frequenzen (nur wirksam bei equalizer_mode=manual)
                mid:
                    type: num
                    yamahayxc_cmd: eq_mid
                    enforce_updates: 'True'
                    min:
                        type: num
                        yamahayxc_cmd: eq_mid_min
                        visu_acl: ro
                    max:
                        type: num
                        yamahayxc_cmd: eq_mid_max
                        visu_acl: ro
                    step:
                        type: num
                        yamahayxc_cmd: eq_mid_step
                        visu_acl: ro

                # Equalizer hohe Frequenzen (nur wirksam bei equalizer_mode=manual)
                high:
                    type: num
                    yamahayxc_cmd: eq_high
                    enforce_updates: 'True'
                    min:
                        type: num
                        yamahayxc_cmd: eq_high_min
                        visu_acl: ro
                    max:
                        type: num
                        yamahayxc_cmd: eq_high_max
                        visu_acl: ro
                    step:
                        type: num
                        yamahayxc_cmd: eq_high_step
                        visu_acl: ro


    # die folgenden Items steuern MusicCast Link (Multiroom), geräteabhängig;
    # auch als Struct 'yamahayxc.link' (Alias für media.link) verfügbar.
    # Grundfunktionen an echter Mehrgeräte-Hardware getestet, siehe Hinweise
    # weiter oben in diesem Dokument. Vereinfachte UI über die rohen YXC
    # dist/*-Primitiven - 'linked'/'role' sind die primären Signale, Rohdaten
    # liegen unter 'options'. link_control/link_audio_delay/
    # link_audio_quality liegen NICHT hier, sondern in 'amp'/'zone2'/'zone3'/
    # 'zone4' (zonenspezifisch, siehe oben).
            link:

                # primäres "bin ich gruppiert?"-Signal, aus group_id
                # abgeleitet (read-only)
                linked:
                    type: bool
                    yamahayxc_cmd: link_linked

                # 'server' / 'client' / 'none' - wird auf 'none' erzwungen,
                # sobald 'linked' false ist, auch wenn das Gerät selbst noch
                # einen älteren Wert meldet (read-only)
                role:
                    type: str
                    yamahayxc_cmd: link_role

                # alle Hosts, für die dieses Plugin mindestens ein Item
                # konfiguriert hat (Plugin-Bookkeeping, kein Gerätestatus) -
                # z.B. für eine Visu-Dropdown-Auswahl (read-only). Steht
                # bereits direkt nach dem Start zur Verfügung.
                available_devices:
                    type: list
                    yamahayxc_cmd: link_hosts

                # Aktionen/Infos, die nur als Gruppen-Server Sinn ergeben
                server:

                    # IP-Adressen der Gruppen-Clients, nur gefüllt während
                    # role=server (read-only)
                    linked_devices:
                        type: list
                        yamahayxc_cmd: link_devices

                    # (als/werde Server) den angegebenen Host/IP als Client
                    # hinzufügen
                    add_device:
                        type: str
                        yamahayxc_cmd: link_add_client
                        enforce_updates: 'True'

                    # den angegebenen Host/IP aus der Gruppe entfernen
                    remove_device:
                        type: str
                        yamahayxc_cmd: link_remove_client
                        enforce_updates: 'True'

                    # eigene Rolle komplett aufgeben (kein separates
                    # "pausieren, Gruppe behalten" - kein klarer
                    # Wiederaufnahme-Weg, kein praktischer Anwendungsfall)
                    disband:
                        type: bool
                        yamahayxc_cmd: link_disband
                        enforce_updates: 'True'

                # Aktionen, die nur als Gruppen-Client Sinn ergeben
                client:

                    # als Client des angegebenen Host/IP einer Gruppe
                    # beitreten
                    join:
                        type: str
                        yamahayxc_cmd: link_join
                        enforce_updates: 'True'

                    # die Gruppe verlassen
                    leave:
                        type: bool
                        yamahayxc_cmd: link_leave
                        enforce_updates: 'True'

                # selten benötigte/rohe Felder
                options:

                    # Gruppen-ID, 32-stelliger Hex-String (read-only) - das
                    # ist, wovon 'linked' abgeleitet wird
                    group_id:
                        type: str
                        yamahayxc_cmd: link_group_id

                    # Gruppenname setzen/lesen (nur im flüchtigen Speicher
                    # des Geräts)
                    group_name:
                        type: str
                        yamahayxc_cmd: link_group_name
                        enforce_updates: 'True'

                    # Zone, die als Master dient, falls role=server (read-only)
                    server_zone:
                        type: str
                        yamahayxc_cmd: link_server_zone

                    # Tonaussetzer während Distribution erkannt? (read-only)
                    audio_dropout:
                        type: bool
                        yamahayxc_cmd: link_audio_dropout

    # link_control ('normal'/'stability_boost'), link_audio_delay
    # ('lip_sync'/'audio_sync_on'/'audio_sync_off'/'balanced') und
    # link_audio_quality ('compressed'/'uncompressed') sind zonenspezifisch
    # (Spezifikations-Ausnahme innerhalb von Link) und liegen deshalb in
    # 'amp'/'zone2'/'zone3'/'zone4', nicht hier:
            link_control:
                type: str
                yamahayxc_cmd: link_control
                enforce_updates: 'True'

            link_audio_delay:
                type: str
                yamahayxc_cmd: link_audio_delay
                enforce_updates: 'True'

            link_audio_quality:
                type: str
                yamahayxc_cmd: link_audio_quality
                enforce_updates: 'True'



Beispiel der Nutzung per CLI-Plugin
-----------------------------------

.. code-block::

    > up media.wx010.power=True
    > up media.wx010.input=net_radio
    > up media.wx010.volume=15
    > up media.wx010.mute=True
    > up media.wx010.mute=False
    > up media.wx010.playback=play
    > up media.wx010.power=False
    > up media.wx010.passthru='v1/Main/setPower?power=off'
    > up media.wx010.alarm_time='1430'
    > up media.avr.tuner.band=fm
    > up media.avr.tuner.freq=87500
    > up media.avr.tuner.preset=5
    > up media.avr.sound_program=munich
    > up media.avr.tone.bass=3
    > up media.avr.tone.balance=-5
    > up media.avr.volume=50
    > up media.avr.volume.raw=35
    > up media.roomA.link.client.join=192.168.2.212
    > up media.roomA.link.client.leave=True


:PS: Das war gelogen. Der WX-010 hat gar keine Wecker-Funktionen...