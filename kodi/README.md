# Kodi

## Changelog

### v1.5.0
* Einbinden von Makros (Abfolgen von Befehlen)
* Befehle werden in eine Warteschleife gelegt, die in der korrekten Reihenfolge abgearbeitet werden
* Weitere Parameter zum Einstellen von Verbindungsversuchen, etc.
* Befehle werden erneut gesendet, wenn eine direkte Antwort nicht mit dem Befehl übereinstimmt (sofern es sich um keine Fehlermeldung handelt)
* Beim Verbindungsaufbau werden Initialisierungsbefehle gesendet, auch nachdem die Verbindung unterbrochen wurde
* Bug Fix: on_off, Mute, etc. funktionieren nun sowohl mit True als auch False Werten
* Sendet Kodi mehrere Antworten gleichzeitig, werden diese nacheinander abgearbeitet (führte früher zu einem Freeze des Plugins)
* Optimierungen von Logging und Code
* zusätzliche Kommandos
