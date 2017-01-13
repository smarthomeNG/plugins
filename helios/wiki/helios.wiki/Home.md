# Wozu dieses Projekt?

Ziel ist das Lesen, Schreiben und Visualisieren von Daten einer Kontrollierten Wohnraumlüftung (KWL) der Firmen Helios und Vallox im Browser, sowie die Einstellung und Schaltung von Parametern.

Im Gegensatz zu den neueren Modellen dieser Hersteller gibt es für die hier unterstützten Geräte weder eine App noch ein Web-Interface; dafür sind sie nie gebaut worden.

Das Projekt besteht aus 2 Teilen:

* einer Erweiterung für [SmartHomeNG](https://github.com/smarthomeNG/smarthome/wiki) zur Datenanbindung („Plugin“),
* einer Erweiterung für die [smartVISU](https://github.com/Martin-Gleiss/smartvisu/wiki) zur Darstellung im Browserfenster („Widget“).

Welcher Browser zur Visualisierung der KWL verwendet wird, ist dabei egal; so kann z.B. auch ein iPad oder Android-Handy die KWL über WLAN steuern.

Plugin und Widget sind keine kommerziellen Produkte, sondern ein kostenfreies Hobbyprojekt - Benutzung somit immer auf eigene Gefahr, es wird keine Gewährleistung übernommen!

<center>![test](https://cloud.githubusercontent.com/assets/20954551/21942760/9c3e407c-d9ce-11e6-8897-18c34fc321a5.png)</center>

# Wie funktioniert das?

Die KWL ist mit ihrer Fernbedienung über ein RS485-Kabel verbunden. Dieses standardisierte 2-Draht-Bussystem wird „angezapft“.

Das Plugin simuliert eine zusätzliche Fernbedienung und kann mittels vordefinierter Befehle KWL-Daten anfordern und senden. Die Daten werden in SmartHomeNG in sogenannten „Items“ gespeichert und können jederzeit abgerufen, modifiziert, ausgewertet und für Berechnungen verwendet werden.

Über eine Standard-Schnittstelle übergibt SmartHomeNG Daten an die smartVISU zur Anzeige.

Für die KWL wurde diese Visu um ein zusätzliches "Widget" (vordefinierter Code und Layout) erweitert. Somit lässt sich mit einer einzigen HTML-Zeile die komplette KWL-Visualisierung an beliebiger Stelle in die Visu integrieren.

Zusätzlich zur Auslieferung der HTML-Seiten an den Browser stellt die smartVISU eine Echtzeit-Verbindung zum Endgerät her, so dass die angezeigten Werte auch ohne Refresh („F5“) im Browser aktualisiert werden.

<Bild>

# Unterstützte KWL-Typen

Zur Zeit werden folgende Anlagen unterstützt:

* Helios EC x00 Pro („altes“ Modell vor 2014)
* Vallox xx SE (getestet: Vallox 90SE)

Erkennbar sind die unterstützten Geräte an der Fernbedienung; diese sieht wie [hier abgebildet](https://shop.strato.de/WebRoot/Store11/Shops/219750/47C5/A3C6/79BF/8402/7A17/C0A8/28B9/AED0/KWL300Fernbedienung.jpg) aus.

Die Helios Eco-Modelle (bzw. Vallox SC-Modelle) können leider nicht unterstützt werden, da diesen die notwendige Steuerelektronik, Sensorik und der RS485-Bus fehlen (erkennbar am 4-Stufen-Schalter, der die Lüftungsstufe über verschiedene Widerstandswerte regelt). Hier gibt es aber einige Bastelprojekte im Internet, um diese Geräte zumindest rudimentär an ein Bussystem (z.B. KNX) zu bringen.

Ebenfalls nicht unterstützt werden die W-Modelle von Helios ab 2014, da diese zwar RS485 haben, aber ein völlig anderes Protokoll verwenden (sie „sprechen“ sozusagen eine andere Sprache - ModBus TCP). Es gibt aber immer wieder Bestrebungen, ein extra Plugin für diese zu programmieren - bis jetzt ist aber leider noch keines fertig geworden.