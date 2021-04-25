.. index:: Plugins; telegram
.. index:: telegram

telegram
########

Das Plugin dient zum Senden und Empfangen von Nachrichten über den
Nachrichten Dienst `Telegram  <https://telegram.org/>`_

Abhängigkeiten
--------------

Es wird die Bibliothek ``python-telegram-bot`` benötigt.
Diese ist in der ``requirements.txt`` enthalten. Ab SmartHomeNG 1.8 sollte die Bibliothek 
direkt beim Start von SmartHomeNG installiert werden. 

Es ist möglich die Installation auch manuell vorzunehmen mit 

``python -m pip install -r requirements.txt --user --upgrade`` innerhalb des
 Verzeichnisses ``/usr/local/smarthome/plugins/telegram``.

Konfiguration
-------------

Zuerst muss ein eigener Bot bei Telegram erstellt werden:

* An ``Botfather`` das Kommando ``/newbot`` senden.
* Dann muss ein **Bot Name** vergeben werden der noch nicht existiert.
* Weitere Bot Details können eingestellt werden, wenn das Kommando
  ``/mybots`` an den BotFather gesendet wird.

Der BotFather erstellt für den neuen Bot ein sogenanntes **token** also
einen einzigartigen Schlüssel.
Dieser muss in der ``plugin.yaml`` von SmartHomeNG eingetragen werden:

.. code::yaml

   telegram:
     plugin_name: telegram
     name: Mein Haus
     token: 123456789:BBCCfd78dsf98sd9ds-_HJKShh4z5z4zh22

* name: Eine Beschreibung des Bots
* token: Der oben beschriebene einzigartige Schlüssel mit dem der Bot bei
  Telegram identifiziert wird.

Jeder Chat, der auf den Bot zugreifen soll, muss SmartHomeNG bekannt gemacht werden.
Das geschieht über ein Item das das Schlüsselwort ``telegram_chat_ids`` hat und
als Wert ein Dictionary hat. Im Dictionary sind Paare von Chat Id und Berechtigung
gespeichert.

.. code::yaml

  Chat_Ids:
    type: dict
    telegram_chat_ids: True
    # cache bietet sich an um Änderungen an den trusted_chat_ids während der
    # Laufzeit von SmartHomeNG zu speichern und nach Neustart wieder zu laden
    # es wird dann der letzte Wert geladen
    cache: 'True'
    # Beispiel value: '{ 3234123342: 1, 9234123341: 0 }'
    # Ein Dictionary mit chat id und 1 für Lese und Schreibzugriff oder 0 für einen nur Lese-Zugriff
    # Nachfolgend ein Chat dem Lese- und Schreibrechte gewährt werden
    value: '{ 3234123342: 1 }'

Um die Chat Id zu bekommen, muss der Bot zunächst laufen.
Dazu wird SmartHomeNG (neu) gestartet.

Im Telegram Client wird der Bot als Chatpartner aufgerufen und das
Kommando ``/start`` an den Bot gesendet.

Der Bot reagiert mit einer Meldung, das die Chat ID noch nicht bekannt ist und
diese zunächst eingetragen werden muss. Mit der nun bekannten Chat ID wird
entweder über das Backend oder das Admin Interface bei den Items das Dictionary
aus dem vorherigen Beispiel erweitert.

Ein erneutes Kommando im Telegram Client an den Bot mit ``/start`` sollte nun
die Meldung ergeben, das der Chat bekannt ist und weiterhin, welche
Zugriffsrechte der Chat auf den Bot hat.

items.yaml
~~~~~~~~~~

telegram_chat_ids
^^^^^^^^^^^^^^^^^

Es muss ein Item angelegt werden mit dem Typ Dictionary. In ihm werden Chat Ids
und Zugriff auf den Bot gespeichert. Siehe obiges Beispiel.


telegram_message
^^^^^^^^^^^^^^^^

Senden einer Nachricht, wenn sich der Wert eines Items ändert. Es ist möglich Platzhalter
in der Nachricht zu verwenden.

Verfügbare Platzhalter:

[ID] [NAME] [VALUE] [CALLER] [SOURCE] [DEST]

Einfaches Beispiel
''''''''''''''''''

.. code:: yaml

   Tuerklingel:
       name: Türklingel (entprellt)
       type: bool
       knx_dpt: 1
       telegram_message: 'Es klingelt an der Tür'

Beispiel mit Platzhaltern
'''''''''''''''''''''''''

.. code:: yaml

   state_name:
       name: Name des aktuellen Zustands
       type: str
       visu_acl: r
       cache: 'on'
       telegram_message: 'Neuer Stateengine Status: [VALUE]'

telegram_condition
^^^^^^^^^^^^^^^^^^

Da es Situationen gibt die für Items ein ``enforce_updates: True`` benötigen, 
würde bei ``telegram_message`` bei jeder Aktualisierung des Items eine Nachricht verschickt werden.
Um das zu verhindern, kann einem Item das Attribut ``telegram_condition: on_change``
zugewiesen werden.

Einfaches Beispiel
''''''''''''''''''

.. code:: yaml

   Tuerklingel:
       type: bool
       knx_dpt: 1
       enforce_updates: True
       telegram_message: 'Es klingelt an der Tür'
       telegram_value_match_regex: (true|True|1)

Dadurch wird auf eine mehrfache Zuweisung des Items mit dem Wert ``True``
nur einmal mit einer Nachricht reagiert. Um eine weitere Nachricht zu generieren
muss das Item zunächst wieder den Wert ``False`` annehmen.
Das Attribut ``telegram_value_match_regex`` filtert den Wert so das es 
bei der Änderung des Itemwertes auf ``False`` zu keiner Meldung *Es klingelt an der Tür* kommt.


telegram_value_match_regex
^^^^^^^^^^^^^^^^^^^^^^^^^^

In manchen Fällen ist es sinnvoll einen Itemwert zunächst zu prüfen bevor eine
Meldung gesendet wird:

Beispiele
'''''''''

.. code:: yaml

    TestNum:
       type: num
       cache: True
       telegram_message: 'TestNum: [VALUE]'
       telegram_value_match_regex: '[0-1][0-9]'

Es wird bei Änderung des Items ``TestNum`` nur dann ein Mitteilung verschickt, wenn 
das Ergebnis der Umwandlung des Itemwertes in einen String dieser mit 
Zahlen von 0 - 19 beginnt.

.. code:: yaml

    Eingangstuer:
        verschlossen:
            type: bool
            cache: True
            telegram_message: "Eingangstür ist verschlossen"
            telegram_value_match_regex: (true|True|1)

Bei Änderung des Items ``Eingangstuer.verschlossen`` wird nur dann eine Nachricht 
gesendet, wenn das Item den Wert True annimmt.

telegram_info
^^^^^^^^^^^^^

Für alle Items mit diesem Keyword wird eine Liste mit Kommandos für den Bot erstellt.
Der Listeneintrag entspricht dabei dem Attributwert.
Wird das Kommando ``/info`` an den Bot gesendet, so erstellt der Bot ein
Tastaturmenü das jedes Attribut mindestens einmal als Kommando enthält.
Bei Auswahl eines dieser Kommandos im Telegram Client wird dann für jedes Item
das das Schlüsselwort ``telegram_info`` und als Attribut den Kommandonamen enthält
der Wert des Items ausgegeben.

Beispiel
''''''''

.. code:: yaml

   Aussentemperatur:
       name: Aussentemperatur in °C
       type: num
       knx_dpt: 9
       telegram_info: wetter

   Wind_kmh:
       name: Windgeschwindigkeit in km pro Stunde
       type: num
       knx_dpt: 9
       telegram_info: wetter

   Raumtemperatur:
       name: Raumtemperatur Wohnzimmer in °C
       type: num
       knx_dpt: 9
       telegram_info: rtr_ist

Das Kommando ``/info`` im Telegram Client veranlasst den Bot zu antworten mit zwei Tasten

.. code::

   [/wetter] [/rtr_ist]

Wählt man am Telegram Client daraufhin ``[/wetter]`` aus, so werden

.. code::

   Aussentemperatur = -10,6
   Wind_kmh = 12.6

ausgegeben. Bei der Auswahl des Kommandos ``[/rtr_ist]`` antwortet der Bot mit

.. code::

   Raumtemperatur = 22.6

telegram_text
^^^^^^^^^^^^^

Schreibt eine Mitteilung die von einem Telegram Client an den Bot gesendet wird
in das Item, das dieses Attribut besitzt.

Beispiel
''''''''

.. code:: yaml

   telegram_message:
       name: Textnachricht von Telegram
       type: str
       telegram_text: true

Nach der Eingabe von ``Hello world!`` am Telegram wird das Item ``telegram_message``
auf ``<Benutzername des chat Partners>: Hello world!`` gesetzt.
Ein John Doe ergäbe also ``John Doe: Hello world!``

Funktionen
==========

Das Plugin stellt derzeit zwei Funktionen zur Nutzung in Logiken bereit:


msg_broadcast
-------------

Argumente beim Funktionsaufruf:

**msg**: Die Nachricht, die verschickt werden soll

**chat_id**:
  Eine Chat Id oder eine Liste von Chat ids.
  Wird keine ID oder None angegeben,
  so wird an alle autorisierten Chats gesendet

photo_broadcast
---------------

Argumente beim Funktionsaufruf:

**path_or_URL**:
  - entweder ein lokaler Pfad, der auf eine Bilddatei zeigt log_directory oder
  - eine URL mit einem Link. Wenn der Link lokal ist,

**caption**:
  - Titel der Bilddatei, kann auch Dateiname sein oder Datum
  - Vorgabewert: None

**chat_id**:
  - eine Chat Id oder eine Liste von Chat ids. Wird keine ID oder None angegeben,
    so wird an alle autorisierten Chats gesendet
  - Vorgabewert: None

**local_prepare**
  - Ist für das zu sendende Bild eine URL angegeben, ruft das Plugin die
    Daten von der URL lokal ab und sendet die Daten dann an den Telegram Server.
    Beispiel dafür ist eine URL einer lokalen Webcam.
    Soll stattdessen eine im Internet frei zugängliche URL abgerufen werden,
    so wird dieses Argument auf False gesetzt und es wird nur die URL
    an Telegram geschickt und der lokale Rechner von den Daten entlastet.
    Aktuell kann das Plugin nicht mit Benutzername und Passwort geschützten
    URL umgehen.
  - Vorgabewert: True

Beispiel
--------

Die folgende Beispiellogik zeigt einige Nutzungsmöglichkeiten für die Funktionen:

.. code:: python

   # Eine Nachricht `Hello world!` wird an alle vertrauten Chat Ids gesendet
   msg = "Hello world!"
   sh.telegram.msg_broadcast(msg)

   # Ein Bild von einem externen Server soll gesendet werden.
   # Nur die URL wird an Telegram gesendet und keine Daten lokal aufbereitet
   sh.telegram.photo_broadcast("https://cdn.pixabay.com/photo/2018/10/09/16/20/dog-3735336_960_720.jpg", "A dog", None, False)

   # Bild auf lokalem Server mit aktueller Zeit an Telegram senden
   my_webcam_url = "http:// .... bitte lokale URL hier einfügen zum Test ..."
   sh.telegram.photo_broadcast(my_webcam_url, "My webcam at {:%Y-%m-%d %H:%M:%S}".format(sh.shtime.now()))

   # Bild senden aber den Inhalt lokal vorbereiten
   sh.telegram.photo_broadcast("https://cdn.pixabay.com/photo/2018/10/09/16/20/dog-3735336_960_720.jpg", "The dog again (data locally prepared)")

   local_file = "/usr/local/smarthome/var/ ... bitte eine lokal gespeicherte Datei angeben ..."
   sh.telegram.photo_broadcast(local_file, local_file)


ToDo - weitere Aufgaben
-----------------------

* Schnittstelle ins Logging schaffen um log Einträge direkt weiterzuleiten als Mitteilungen an Telegram
* Schreib- und Lesezugriff auf Itemwerte implementieren, ähnlich wie im cli Plugin
* Ein Menü dynamisch bereitstellen das die Item Baumstruktur abbildet mit zugehörigen Werten
