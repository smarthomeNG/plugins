# SmartHomeNG

Dies ist das sozusagen das "Hauptsystem", das vom Helios/Vallox Plugin um eine spezifische Schnittstelle zur KWL erweitert wird.

Um Daten lesen und schreiben zu können, und um Drittsysteme wie z.B. KNX anzubinden, wird ein fertig installiertes und konfiguriertes SmartHomeNG benötigt (z.B. auf einem Raspberry Pi, einem NAS oder einem Intel NUC - [Details siehe Doku von SmartHomeNG](https://github.com/smarthomeNG/smarthome/wiki/Installation)).

SmartHomeNG ist Open Source Software, wird von einer aktiven Entwicklergemeinde gepflegt und kostet hauptsächlich zwei Dinge: Zeit und Willen zum Lernen. [Hier](https://github.com/smarthomeNG/smarthome/wiki) sind Quellcode, Installationsanleitung und Dokumentation zu finden, [hier](https://knx-user-forum.de/forum/supportforen/smarthome-py) das Support-Forum der Entwicklergemeinde.

**Tip:** Es gibt auch ein Abbild („Image“) eines bereits fertig installierten Systems für den Raspberry Pi, das auf eine SD-Karte kopiert und mit einigen wenigen Änderungen betriebsbereit gemacht werden kann. Weitere Informationen dazu findest Du [hier](https://knx-user-forum.de/forum/supportforen/smarthome-py/979095-smarthomeng-image-file). Das Image enthält übrigens neben vielen anderen Dingen auch bereits die weiter unten genannte smartVISU.
 
# RS485-Schnittstelle

Um den Bus "anzapfen" zu können, wird eine RS485-Schnittstelle benötigt. In den meisten Fällen nimmt man dafür einen Seriell-zu-USB Adapter (ich selbst habe z.B. einen 2014 auf Amazon erstandenen „Digitus DA-70157“, aber auch jeder andere RS485-Adapter sollte seinen Dienst tun).

Die Kommunikation über RS485 geschieht grundsätzlich über 2 Drähte; der Anschluß an den Klemmkasten ist z.B. [hier](http://www.tagol.de/blog/anschluss-raspberry-pi-kwl-helios-pro---rs485) beschrieben.

Mit einem fertig installierten und konfigurierten SmartHomeNG und der RS485-Schnittstelle können bereits Daten gelesen, geschrieben und an Drittsysteme wie z.B. KNX weitergegeben werden.

# smartVISU

Wer die Daten zusätzlich in einem beliebigen Browser anzeigen und die KWL auch bedienen möchte, benötigt die smartVISU. Für die smartVISU wurde eine KWL-spezifische Erweiterung („Widget“) geschrieben, die die Darstellung der Daten übernimmt.

In den meisten Fällen wird die Visu auf dem gleichen System wie SmartHomeNG installiert.

Auch die smartVISU ist Open Source, kostenlos und wird von einer aktiven Entwicklergemeinde gepflegt (überwiegend den gleichen Leuten wie bei SmartHomeNG). Das Projekt ist hier auf [hier](https://github.com/Martin-Gleiss/smartvisu/wiki) zu finden, der Support erfolgt wie bei SmartHomeNG im [KNX User Forum](https://knx-user-forum.de/forum/supportforen/smartvisu).

# Weitere Hinweise

* Ich empfehle dringend die Einrichtung von Samba auf dem System, wo SmartHomeNG läuft (Bestandteil der Komplettanleitung und des fertigen Images, siehe [hier](https://github.com/smarthomeNG/smarthome/wiki/Komplettanleitung#samba-einrichten)). Dann kann mit dem Windows Explorer direkt auf den Pi oder das NAS zugegriffen werden, bei mir z.B. über die Eingabe des Rasberry-Pi Rechnernamens \\kwlpi, oder über Durchklicken von der Netzwerkumgebung aus.

* Weiterhin wird ein Programm benötigt , umd vom PC eine Kommandozeile auf dem System öffnen zu können, auf dem SmartHomeNG installiert ist. [Putty](http://www.putty.org/) ist hier der Quasi-Standard.

* Und last but not least – auch ein guter Editor sollte auf dem PC installiert sein, da das Standardprogramm „Notepad“ Unix-Dateien nicht vernünftig bearbeiten kann. Hier empfiehlt sich [Notepad++](https://notepad-plus-plus.org/) (zur Benutzung: Datei anklicken, rechte Maustaste, Öffnen mit, Notepad++).