# Installation von sHNG, RS485, smartVISU

Bitte hab Verständnis dafür, dass hier nicht weiter auf Installation, Konfiguration und Inbetriebnahme des Grundsystems eingegangen wird. Diese Doku setzt voraus, dass SmartHomeNG, RS485-Schnittstelle und smartVISU fertig installiert und konfiguriert sind und bereits „laufen“. Individuellen Support gibt die Community in den jeweiligen Foren.

# Installation und Inbetriebnahme des Plugins (SmartHomeNG)

> Tip: Vor der Installation sollte das Betriebssystem und seine Komponenten
> per Kommandozeile auf den letzten Stand gebracht werden
> (Achtung - dies kann manchmal eine ziemliche Weile dauern):
>
> ```bash
> sudo apt-get update
> sudo apt-get upgrade
> ```
>
***
>
> Tip: (Nur für Update einer bestehenden Installation):
> Es wird empfohlen, das Verzeichnis /usr/local/smarthome/plugins/helios
> vor der Installation manuell zu leeren, da sich hier auch ein
> Cache-Verzeichnis des vorhandenen Plugins befindet.

## Installation

Zuerst muss die Python-Unterstützung für serielle Schnittstellen installiert werden:

```bash
sudo apt-get install python-serial
```

Alle notwendigen Dateien sowohl für das Plugin als auch für das Widget befinden sich in einer helios.zip Datei. Der letzte „öffentliche“ Stand ist immer [hier](www.kramkiste.net/helios.zip) zu finden. Das Unterverzeichnis „smarthome“ enthält bereits die notwendige Ordnerstruktur. Im Normalfall müssen diese Dateien in die gleichen Verzeichnisse unter

```bash
/usr/local/smarthome
```
kopiert werden (oder halt dorthin, wo SmartHomeNG alternativ installiert wurde). Abschließend sind noch einige Einträge in drei Konfigurationsdateien vorzunehmen.

## /usr/local/smarthome/etc/plugin.conf

Bitte die folgenden Zeilen hinzufügen:

```python
[helios]
    class_name = helios
    class_path = plugins.helios
    tty = /dev/ttyUSB0               # put your serial port here (usually /dev/ttyUSB0 or /dev/ttyAMA0)
    cycle = 60                       # update interval in seconds; ex-default: 300
```
Den Eintrag tty= auf die tatsächlich verwendete serielle Schnittstelle anpassen.

> **Tip:** Die serielle Schnittstelle kann vom Betriebssystem in den meisten Fällen über /dev/ttyUSB0 oder /dev/ttyAMA0 angesprochen werden. Befinden sich mehrere serielle Schnittstellen im System, kann der Port auch ein anderer sein. Über den Befehl

> ```bash
> lsusb
> ```
> werden alle installierten USB-Einheiten angezeigt. Über

> ```bash
> ls -l /dev/ttyUSB0
> ```
> lässt sich abfragen, ob eine bestimmte Schnittstelle existiert (hier: ttyUSB0). Und mit dem Befehl

> ```bash
> cat /dev/ttyUSB0
> ```

> wird angezeigt, was dort gerade empfangen wird. (Achtung - Binärdaten; kann und wird zu 'kryptischen' Anzeigen führen. Wenn nichts angezeigt wird, ggf. mehrfach ausführen. Mit Ctrl-D beenden, wenn es nicht automatisch beendet wird.)

> Und: Ist der RS485-Bus noch nicht angeschlossen, wird natürlich auch nichts empfangen. ;-)

## /usr/local/smarthome/etc/logic.conf

Bitte die folgenden Zeilen hinzufügen:

```python
[fanspeed_uzsu_logic]
    filename = helios_logics.py
    watch_item = ventilation.fanspeed.fanspeed_uzsu

[booster_logic]
    filename = helios_logics.py	
    watch_item = ventilation.booster_mode.logics.switch
```

## /usr/local/smarthome/items/helios.conf

Um korrekte Werte anzeigen zu können, benötigt das Plugin einige Angaben zu Deinem Haus und Deiner Anlage. Hierzu die Datei öffnen und im Abschnitt [[ settings ]] den Eintrag "value =" für folgende Werte bearbeiten:

```text
[[[house_volume]]]          Welches Volumen durchströmt die Luft der KWL in Deinem Haus? (siehe Hauspläne)
[[[aNE]]]                   Welche Fläche durchströmt die Luft der KWL in Deinem Haus? (siehe Hauspläne)
[[[fWS]]]                   Dämmungsfaktor nach DIN (gedämmt=0.3, sonst 0.4)
[[[max_airflow]]]           Wie hoch ist der maximale Volumenstrom Deiner KWL? (siehe Handbuch)
[[[fanspeed_levels]]]       Wieviele Stufen hat die KWL (meist von 1…8, also 8) (siehe Handbuch)
[[[preheating_consumtion]]] Stromverbrauch des Vor-/Nachheizregisters (siehe Handbuch)
[[[consumption_per_mode]]]  fanspeed_levels + 1 (also 9) Werte für den jeweiligen Stromverbrauch (siehe Handbuch)
[[[airflow_per_mode]]]      fanspeed_levels + 1 (also 9) Werte für den jeweiligen Volumenstrom  (siehe Handbuch)
```

**Hinweis:** Die letzten beiden Werte und die daraus resultierenden Ergebnisse von einigen Berechnungen können immer nur Schätzungen sein. Sie werden u.a. auch vom Druckverlust der Anlage („Ventilatorkurve“, siehe Handbuch und frag Google), dem Zustand der Filter (z.B. Verschmutzung) und der Verwendung von Staub-/Hütchenfiltern auf den Abluftventilen beeinflußt.

## Neustart und Ablesen erster Werte

Wenn SmartHome NG als Dienst läuft, diesen bitte in der Kommandozeile mit

```bash
service smarthome stop
service smarthome start
```

neu starten. Wer sich nicht sicher ist - ein

```bash
reboot
```

startet das komplette System neu.

Ist das Backend-Plugin installiert (was in der Regel der Fall ist), erscheinen in diesem nach dem Neustart die sogenannten „Items“ in einer Baustruktur. Wenn alles auf Anhieb geklappt hat, kann man dort z.B. unter „ventilation > RS485 > _fanspeed“ die aktuelle Lüfterstufe der KWL ablesen.

## Troubleshooting

Die meisten Supportfälle im Forum hatten bisher drei Ursachen:

**Problem: Keine Daten**

Lösung: Bitte nochmal die Anschlusskabel prüfen und ggf. mal „A“ und „B“ bzw. „+“ und „-“ vertauschen (sollte eigentlich keine Rolle spielen; tut es aber manchmal trotzdem). Wenn es das war, erscheinen nach spätestens 60s ohne Neustart die Werte im Backend.

**Problem: Immer noch keine Daten, trotz 100% korrekter Verkabelung**

Lösung: Es wurde vergessen, die Datei plugin.conf zu bearbeiten, oder der Port ist dort falsch angegeben.
Achtung: Änderungen an der plugin.conf erfordern einen Neustart von SmartHomeNG.

**Problem: Immer noch keine oder fehlerhafte Daten**

Lösung: Auf einigen Systemen machen die Standardeinstellungen des USB-Ports Probleme. Dies kommt kurioserweise nur auf einigen wenigen Systemen vor und hängt vermutlich mit dem verwendeten Seriell-USB-Konverter zusammen.

Hilfestellung bietet die kurze 4-Punkte-Checkliste [hier](https://knx-user-forum.de/forum/supportforen/smarthome-py/40092-erweiterung-helios-vallox-plugin?p=650305#post650305). Ansonsten auch bitte mal [diesen](https://knx-user-forum.de/forum/supportforen/smarthome-py/37489-helios-kwl-200-pro-per-usb-rs485-adapter-steuern?p=609365#post609365) und [diesen](http://www.netzmafia.de/skripten/hardware/RasPi/RasPi_Serial.html) Beitrag durcharbeiten, dort werden weitere Hinweise gegeben, wie man die USB-Schnittstelle zum Laufen bekommt.

# Installation und Inbetriebnahme des Widgets (smartVISU)

> Tip:
> Grundsätzlich empfiehlt es sich, vor Installation des Helios-Widgets
> die UZSU (Universelle Zeitschaltuhr) betriebsfertig zu haben.
> Weitere Informationen dazu sind [hier](https://github.com/mworion/uzsu_widget) zu finden.

## Installation

Das Unterverzeichnis „smartVISU“ in der heruntergeladenen helios.zip enthält bereits die notwendige Ordnerstruktur.

Im Normalfall müssen diese Dateien unter /var/www/smartVISU kopiert werden (oder halt dort, wo die smartVISU alternativ installiert wurde; meist liegt sie im www-root des installierten Webservers). Weitere Anpassungen sind nicht erforderlich

## Einbindung des Widgets in Deine Webseite

Die Webseiten liegen üblicherweise unter /var/www/smartVISU/pages/<name>. Durch Aufruf der Visu und Auswahl des Settings-Icons im Menü oben lassen sich diese umschalten.

Um  das Widget in einer beliebigen HTML-Seite einzubinden, bitte folgende Zeilen an der gewünschten Stelle in den HTML-Code setzen:

```html
{% import "widget_uzsu.html" as uzsu %}
{% import "helios.html" as helios %}
{{ helios.show_widget('EC300Pro', true, 'Kontrollierte Wohnraumlüftung') }}
```

Die ersten beiden Zeilen binden die Widgets für UZSU und Helios/Vallox zur Benutzung in den HTML-Code ein. Der eigentliche Aufruf erfolgt in der dritten Zeile. Folgende Parameter können beim Aufruf angegeben werden:

```html
{{ helios.show_widget(id, use_uzsu, title) }}

id          Eine in dieser HTML-Datei _eindeutige_ (!) Bezeichnung für das Widget
            (keine Leerzeichen verwenden!).
use_uzsu    True / False (UZSU benutzen oder nicht?
title       (Optionaler) Titel für das Fenster.
```

## Interne Schalter

In der Datei /var/www/smartVISU/widgets/helios.html können im Kopf noch folgende Einstellungen vorgenommen werden:

```html
{% set debug_mode = false %}	      True = Anzeige von Zusatzinformationen (für Entwickler gedacht).
{% set documentation_mode = false %}  True = Anzeige aller Icons (für Entwickler gedacht).
```

Diese Einstellungen sind eigentlich nur für die Entwickler interessant, um schnell Zugriff auf bestimmte Informationen zu haben und diese Dokumentation erstellen zu können. 

Bitte ändere diese Punkte nur, wenn Du weißt, was Du tust - sie verändern / verfälschen die Anzeige des Widgets.

Da aber schon häufiger Fragen zu diesen Einträgen kamen, habe ich diese Zeilen in die Doku mit aufgenommen.

## Troubleshooting

[ToDo]