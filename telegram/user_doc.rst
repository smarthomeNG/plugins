.. index:: Plugins; telegram
.. index:: telegram

telegram
########

Das Plugin dient zum Senden und Empfangen von Nachrichten über den
`Telegram Nachrichten Dienst <https://telegram.org/>`_

Abhängigkeiten
--------------

Es wird die Bibliothek ``python-telegram-bot`` benötigt.
Diese ist in der ``requirements.txt`` enthalten.
Bevor das Plugin genutzt werden kann, muß die Bibliothek installiert werden:

* Entweder mit ``sudo pip install -r requirements.txt``

oder

* unter Benutzung von ``pip install -r requirements.txt`` innerhalb
  des Verzeichnisses ``/usr/local/smarthome/plugins/telegram``.

Konfiguration
-------------

Zuerst muß ein eigener Bot bei Telegram erstellt werden:

* An ``Botfather`` das Kommando ``/newbot`` senden.
* Dann muß ein **Bot Name** vergeben werden der noch nicht existiert.
* Weitere Bot Details können eingestellt werden, wenn das Kommando
  ``/mybots`` an den BotFather gesendet wird.

Der BotFather erstellt für den neuen Bot ein sogenanntes **token** also
einen einzigartigen Schlüssel.
Dieser muß in der ``plugin.yaml`` von SmartHomeNG eingetragen werden:

.. code::yaml

   telegram:
     plugin_name: telegram
     name: Mein Haus
     token: 123456789:BBCCfd78dsf98sd9ds-_HJKShh4z5z4zh22

* name: Eine Beschreibung des Bots
* token: Der oben beschriebene einzigartige Schlüssel mit dem der Bot bei
  Telegram identifiziert wird.

Jeder Chat, der auf den Bot zugreifen soll, muß SmartHomeNG bekannt gemacht werden.
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

Um die Chat Id zu bekommen, muß der Bot zunächst laufen.
Dazu wird SmartHomeNG (neu) gestartet.

Im Telegram Client wird der Bot als Chatpartner aufgerufen und das
Kommando ``/start`` an den Bot gesendet.

Der Bot reagiert mit einer Meldung, das die Chat ID noch nicht bekannt ist und
diese zunächst eingetragen werden muß. Mit der nun bekannten Chat ID wird
entweder über das Backend oder das Admin Interface bei den Items das Dictionary
aus dem vorherigen Beispiel erweitert.

Ein erneutes Kommando im Telegram Client an den Bot mit ``/start`` sollte nun
die Meldung ergeben, das der Chat bekannt ist und weiterhin, welche
Zugriffsrechte der Chat auf den Bot hat.

items.yaml
~~~~~~~~~~

telegram_chat_ids
^^^^^^^^^^^^^^^^^

Es muß ein Item angelegt werden mit dem Typ Dictionary. In ihm werden Chat Ids
und Zugriff auf den Bot gespeichert. Siehe obiges Beispiel.


telegram_message
^^^^^^^^^^^^^^^^

Senden einer Nachricht, wenn sich ein Item ändert. Es ist möglich Platzhalter
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
       telegram_message: 'New AutoBlind state: [VALUE]'

telegram_value_match_regex
^^^^^^^^^^^^^^^^^^^^^^^^^^

In manchen Fälles ist es sinnvoll einen Itemwert zunächst zu prüfen bevor eine
Meldung gesendet wird:

Beispiel
''''''''

.. code:: yaml

   TestNum:
       type: num
       cache: True
       telegram_message: 'TestNum: [VALUE]'
       telegram_value_match_regex: '[0-1][0-9]' # nur Nachrichten senden wenn Zahlen von 0 - 19
   TestBool:
       type: bool
       cache: True
       telegram_message: TestBool: [VALUE]
       telegram_value_match_regex: 1            # nur Nachricht senden wenn 1 (True)

telegram_info
^^^^^^^^^^^^^

Für alle Items mit diesem Keyword wird eine Liste mit Kommandos für den Bot erstellt.
Der Listeneintrag entspricht dabei dem Attributwert.
Wird das Kommando ``/info`` an den Bot gesendet, so erstellt der Bot ein
Tastaturmenü das jedes Attribut mindestens einmal als Kommando enthält.
Bei Auswahl eines dieser Kommandos im Telegram Client wird dann für jedes Item
das das Schlüsselwort telegram_info und als Attribut den Kommandonamen enthält
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
       name: Windgeschwindigkeit in kmh
       type: num
       knx_dpt: 9
       telegram_info: wetter

   Raumtemperatur:
       name: Raumtemperatur Wohnzimmer in °C
       type: num
       knx_dpt: 9
       telegram_info: rtr_ist

Das Kommando ``/info`` veranlasst den Bot zu antworten mit

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
auf ``<Benutzername des chat Partners>:Hello world!`` gesetzt.
Ein John Doe ergäbe also ``John Doe:Hello world!``

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
