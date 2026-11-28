.. index:: Plugins; bark
.. index:: bark

====
bark
====

Das Plugin versendet Push-Benachrichtigungen an die iOS-App `Bark <https://github.com/Finb/Bark>`_.


Anforderungen
=============

Benötigt werden ein erreichbarer `Bark-Server <https://github.com/Finb/bark-server>`_ (selbst betrieben oder
öffentlich) und der Geräteschlüssel, den die App anzeigt.


Konfiguration
=============

Die Plugin Parameter, die Informationen zur Item-spezifischen Konfiguration des Plugins und zur Logik-spezifischen
Konfiguration sind unter :doc:`/plugins_doc/config/bark` beschrieben.

plugin.yaml
-----------

.. code-block:: yaml

    bark:
        plugin_name: bark
        server_url: http://192.168.1.10:8080
        device_key: <Geräteschlüssel>

Für mehrere Empfänger wird das Plugin mehrfach als eigene Instanz konfiguriert.


items.yaml
----------

Ein Item mit ``bark_text`` oder ``bark_values`` versendet bei jeder Wertänderung eine Benachrichtigung. Bei
Items mit ``enforce_updates`` wird auch bei unverändertem Wert gesendet.

``bark_values`` ordnet einzelnen Werten einen Text zu. Für alle anderen Werte gilt ``bark_text``; fehlt dieses,
wird nichts gesendet.

.. code-block:: yaml

    tor:
        type: bool
        bark_values:
            - true: 'Tor zu'
            - false: 'Tor offen'
        bark_url: 'http://visu.local/garage'

``VAL`` wird in ``bark_text``, ``bark_title`` und ``bark_url`` durch den Item-Wert ersetzt:

.. code-block:: yaml

    betriebsart:
        type: str
        bark_text: 'Heizung: VAL'

``bark_title`` setzt eine Überschrift über den Text. ``bark_url`` gibt die Adresse an, die beim Antippen der
Benachrichtigung geöffnet wird.


Funktionen
----------

``notify(body, title=None, url=None)`` versendet eine Benachrichtigung aus Logiken oder eval-Ausdrücken und
liefert ``True``, wenn der Server sie angenommen hat:

.. code-block:: python

    sh.plugins.bark.notify('Ablaufpumpe blockiert', 'Spülmaschine')

Der Name nach ``sh.plugins.`` ist der Abschnittsname in der ``plugin.yaml``.

Der Aufruf wartet auf die Antwort des Servers, bei nicht erreichbarem Server bis zu 5 Sekunden je
Netzwerkoperation.


Umstieg vom prowl Plugin
========================

.. list-table::
   :header-rows: 1

   * - prowl
     - bark
   * - ``prowl_text``, ``prowl_values``
     - ``bark_text``, ``bark_values``
   * - ``prowl_url``
     - ``bark_url``
   * - ``prowl_event``
     - ``bark_title``, nur wenn eine Überschrift gewünscht ist
   * - ``prowl_swap``
     - entfällt: Überschrift und Text werden beide angezeigt
   * - ``notify(event, description)``
     - ``notify(body, title)``
