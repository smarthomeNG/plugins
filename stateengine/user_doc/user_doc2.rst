.. index:: Plugins; Stateengine; Pluginkonfiguration
.. index:: Pluginkonfiguration

Pluginkonfiguration
###################

.. rubric:: Konfiguration des Plugins
   :name: konfigurationdesplugins

Um das StateEngine Plugin zu verwenden müssen die folgenden Zeilen
in die plugin.yaml Datei der smarthomeNG Installation eingetragen
werden.

.. code-block:: yaml

   stateengine:
           class_name: StateEngine
           class_path: plugins.stateengine
           #startup_delay_default: 10
           #suspend_time_default: 3600
           #log_level: 0
           #log_directory: var/log/StateEngine/
           #log_maxage: 0


Auskommentierte Attribute sind Vorgabewerte, die nach den eigenen
Bedürfnissen angepasst werden können.

| **startup_delay_default (optional):**
| *Vorgabewert für die Startverzögerung der ersten
  Zustandsermittlung beim Start von smarthomeNG*

Beim Starten von smarthomeNG dauert es üblicherweise einige
Sekunden, bis alle Items initialisiert sind. Um zu verhindern,
dass die erste Zustandsermittlung stattfindet, bevor alle Items
ihren Initialwert haben, wird die erste Zustandsermittlung
verzögert. Die Dauer der Verzögerung kann bei den Objekt-Items
angegeben werden. Wenn bei einem Objekt-Item kein Wert angegeben
ist, wird der hier angegebene Standardwert verwendet. Wenn kein
abweichender Standardwert in der Plugin-Konfiguration angegeben
ist, ist der Vorgabewert 10 Sekunden.

Folgende Werte sind möglich:

| *Zahl größer 0:*
| Angabe der Startverzögerung in Sekunden. Während der
  Startverzögerung sind die Auslöser der Zustandsermittlung
  inaktiv. Sie werden erst nach Ablauf der Startverzögerung und
  der ersten Zustandsermittlung aktiviert.

| *0:*
| Keine Startverzögerung. Die erste Zustandsermittlung wird direkt
  nach der Initialisierung des Objekt-Items durchgeführt.
  Anschließend werden die Auslöser für die Zustandsermittung
  aktiviert.

| *-1:*
| Es wird keine erste Zustandsermittlung durchgeführt. Nach der
  Initialisierung des Objekt-Items sind alle Auslöser für die
  Zustandsermittlung aktiv.

| **suspend_time_default (optional):**
| *Vorgabezeit zur Unterbrechung der automatischen Steuerung nach
  manuellen Aktionen*

Nach manuellen Aktionen kann die Automatik für eine bestimmte Zeit
Unterbrochen werden. Die Dauer dieser Unterbrechungen kann bei den
Objekt-Items angegeben werden. Die Einheit für den Wert sind
Sekunden. Wenn bei einem Objekt-Item kein Wert angegeben ist, wird
der hier angegebene Standardwert verwendet. Wenn kein abweichender
Standardwert in der Plugin-Konfiguration angegeben ist, ist der
Vorgabewert 3600 Sekunden (1 Stunde)

| **log_level(optional):**
| *Erweiterte Protokollierung: Loglevel (0: aus, 1: Info, 2:
  Debug*

Die erweiterte Protokollierung wird über das Setzen des Loglevels
auf 1 (Info) oder 2 (Debug) aktiviert. Wenn der Parameter nicht
angegeben ist, ist die erweiterte Protokollierung deaktiviert.

| **log_directory (optional):**
| *Erweiterte Protokollierung: Verzeichnis für die
  Protokolldateien*

| Die Logdateien der erweiterten Protokollierung werden in das
  hier angegebene Verzeichnis geschrieben.
| Wenn der angegebene Verzeichnisname mit "/" beginnt wird er als
  absoluter Verzeichnisname behandelt. Alle anderen
  Verzeichnisnamen werden als Unterverzeichnisse des smarthomeNG
  Basisverzeichnisses behandelt. Das angegebene Verzeichnis wird
  angelegt, wenn es nicht existiert.
| Wenn hier kein abweichendes Verzeichnis angegeben ist, wird das
  Verzeichnis ``<smarthome_base_directory>/var/log/AutoState/``
  verwendet.

| **log_maxage (optional):**
| *Erweiterte Protokollierung: Anzahl der Tage, nach der die
  Dateien im Verzeichnis ``log_directory`` wieder gelöscht
  werden sollen*

| Alte Protokolldateien können nach einer bestimmten Zeit
  automatisch gelöscht werden. Diesen Parameter wird die Anzahl
  der Tage festgelegt, nachdem die Dateien gelöscht werden sollen.
  Das Löschen ist ausgesetzt solange der Parameter den Wert 0 hat.
  Wenn der Parameter auf einen anderen Wert gesetzt wird, wird das
  Alter der Dateien im Protokollverzeichnis ``log_directory``
  täglich geprüft und überalterte Dateien werden gelöscht.

.. important::

  Die Löschfunktionalität prüft und löscht alle
  Dateien im Protokollverzeichnis, ob sie Protokolldateien sind
  oder nicht. Daher sollten keine anderen Dateien in diesem
  Verzeichnis abgelegt werden!
