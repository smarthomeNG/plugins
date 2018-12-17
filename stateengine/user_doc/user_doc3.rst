.. index:: Plugins; Stateengine; Objekt-Item
.. index:: Objekt-Item

Objekt-Item
###########

.. rubric:: Die Grundkonfiguration für eine Automatik: Das Objekt-Item
   :name: diegrundkonfiguration

Für jedes Objekt, dass mit dem StateEngine Plugin gesteuert werden
soll, ist ein Item erforderlich, dass alle Konfigurationsdaten für
dieses Objekt enthält. Dieses Item wird aus "Objekt-Item"
bezeichnet. Es können beliebig viele Objekt-Items und damit
beliebig viele Automatiken angelegt werden.

.. rubric:: Grundlegende Einstellungen
   :name: grundlegendeeinstellungen

Über die folgenden Attribute werden die grundlegenden
Einstellungen für eine Automatik festgelegt

.. code-block:: yaml

   beispiel:
           raffstore1:
               automatik:
                   rules:
                       type: bool
                       name: Automatik Raffstore 1
                       se_plugin: active
                       se_startup_delay: 30
                       se_laststate_item_id: beispiel.raffstore1.automatik.state_id
                       se_laststate_item_name: beispiel.raffstore1.automatik.state_name
                       se_repeat_actions: true
                       se_suspend_time: 7200


| **type (obligatorisch):**
| *Datentp des Items*

Für das Objekt-Item muss immer der Datentyp "bool" verwendet
werden

| **name (optional):**
| *Name des Items*

Wenn das Attribut nicht angegeben ist, wird die Id des Items als
Name verwendet.

| **se_plugin (obligatorisch):**
| *Kennzeichnet das Item als Objekt-Item des StateEngine-Plugins*

Der Wert dieses Attributs muss zwingend ``active`` sein, damit
das Plugin das Item berücksichtigt. Zu Debuggingzwecken kann der
Wert dieses Attributs auf einen anderen Wert geändert werden,
dadurch wird das Plugin das Objekt ignorieren.

| **se_startupdelay (optional):**
| *Startverzögerung der ersten Zustandsermittlung beim Start von
  smarthomeNG*

| Beim Starten von smarthomeNG dauert es üblicherweise einige
  Sekunden, bis alle Items initialisiert sind. Um zu verhindern,
  dass die erste Zustandsermittlung stattfindet, bevor alle Items
  ihren Initialwert haben, wird die erste Zustandsermittlung
  verzögert. Erst nach der ersten Zustandsermittlung werden alle
  Auslöser und Funktionen vollständig aktiviert.
  Zustandsermittlungen, die durch Items oder Timer vor Ablauf der
  Startverzögerung ausgelöst werden, werden nicht durchgeführt.
  Die zulässigen Werte für ``se_startup_delay`` sind identisch
  mit den zulässigen Werten für den Plugin-Parameter
  ``startup_delay_default``.
| Der Parameter verwendet den Datentyp AbValue

| **se_laststate_item_id (optional):**
| *Id des Items, in dem die Id des aktuellen Zustands abgelegt wird*

In das hier angegebene Item wird die Id des aktuellen Zustands
abgelegt. Das Item kann mit dem Attribut ``cache: yes``
versehen werden, dann bleibt der vorherige Zustand bei einem
Neustart von smarthomeNG erhalten. Wenn das Item
``se_laststate_item_id`` nicht angegeben ist, wird der aktuelle
Zustand nur im Plugin gespeichert und geht mit einem Neustart von
smarthomeNG verloren.

Sofern verwendet, sollte das Item für ``se_laststate_item_id``
wie folgt definiert werden

.. code-block:: yaml

   beispiel:
           raffstore1:
               automatik:
                   state_id:
                       type: str
                       name: Id des aktuellen Zustands
                       visu_acl: r
                       cache: yes


| **se_laststate_item_name (optional):**
| *Id des Items, in dem der Name des aktuellen Zustands abgelegt wird*

In das hier angegebene Item wird der Name des aktuellen Zustands
abgelegt. Das Item kann für Displayzwecke verwendet werden. Wenn
das Item ``se_laststate_item_name`` nicht angegeben ist, steht
der Name des aktuellen Zustands nicht zur Verfügung

Sofern verwendet, sollte das Item für ``se_laststate_item_name``
wie folgt definiert werden

.. code-block:: yaml

   beispiel:
           raffstore1:
               automatik:
                   state_name:
                       type: str
                       name: Name des aktuellen Zustands
                       visu_acl: r
                       cache: yes


| **se_repeat_actions (optional):**
| *Wiederholen der Aktionen bei unverändertem Zustand*

Im Normalfall werden Aktionen jedesmal ausgeführt wenn der
aktuelle Zustand neu ermittelt wurde. Dies ist unabhängig davon,
ob sich der Zustand bei der Neuermittlung geändert hat oder nicht.
Dieses Verhalten kann über die Angabe von
``se_repeat_actions: false`` umgestellt werden. Wenn das
Attribut auf ``false`` gesetzt ist, werden Aktionen nur
ausgeführt, wenn sich der Zustand tatsächlich geändert hat. Der
Parameter verwendet den Datentyp AbValue

| **se_suspendtime (optional):**
| *Zeit zur Unterbrechung der automatischen Steuerung nach
  manuellen Aktionen*

Nach manuellen Aktionen kann die Automatik für eine bestimmte Zeit
Unterbrochen werden. Die Dauer dieser Unterbrechungen wird hier
angegeben. Die Einheit für den Wert sind Sekunden. Wenn bei einem
Objekt-Item kein Wert angegeben ist, wird der in der
Pluginkonfiguration angegebene Standardwert
(se_suspend_time) verwendet. Der Parameter verwendet den
Datentyp AbValue

.. rubric:: Einstellungen zum Auslösen der Zustandsermittlung
   :name: einstellungenzumauslsenderzustandsermittlung

Eine Neuermittlung des aktuellen Zustands wird jedesmal
durchgeführt, wenn ein Wert für das Objekt-Item geschrieben wird.
Somit können die Standardmöglichkeiten von smarthomeNG wie
``cycle``, ``crontab`` und ``eval_trigger`` verwendet
werden, um die Neuermittlung des aktuellen Zustands auszulösen.

.. code-block:: yaml

   beispiel:
           rafffstore2:
               automatik:
                   rules:
                       <...>
                       cycle: 300
                       crontab:
                           - 0 5 * *
                           - 0 6 * *
                       eval_trigger:
                           - beispiel.trigger.raffstore
                           - beispiel.raffstore2.automatik.anwesenheit


Details zu diesen Attributen können der `smarthomeNG
Dokumentation <https://www.smarthomeng.de/user/konfiguration/items_standard_attribute.html>`_
entnommen werden.

Um die Konfiguration einfach zu halten, verändert das Plugin
einige Einstellungen des Objekt-Items. Folgende Erleichterungen
werden dabei vorgenommen:

-  Es ist nicht erforderlich mit ``cycle`` bzw. ``crontab``
   Werte anzugeben. Das StateEngine Plugin ergänzt diese
   automatisch, sofern erforderlich. Statt ``cycle: 300 = 1`` ist
   es ausreichend, wenn man ``cycle: 300`` angibt.

-  Es ist nicht erforderlich das Attribut ``eval = (irgendwas)``
   anzugeben, wenn ``eval_trigger`` verwendet wird. Das
   StateEngine plugin ergänzt dies automatisch, sofern
   erforderlich.

-  ``crontab: init`` funktioniert nicht für das StateEngine
   Plugin. Die Neuberechnung des ersten Zustands nach dem Start
   von smarthomeNG wird über das Attribut ``se_startup_delay``
   gesteuert.

Es ist auch möglich andere Wege zu verwenden, um den Wert des
Objekt-Items zu setzen:

-  Zuweisung einer hörenden KNX Gruppenadresse zum Objekt-Item und
   Senden eines Wertes auf diese Gruppenadresse.

-  Setzen des Werts des Objekt-Items aus einer Logik, einer
   anderen Automatik oder sogar aus der selben Automatik (ggf. mit
   Verzögerung).
