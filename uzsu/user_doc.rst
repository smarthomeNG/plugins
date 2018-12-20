.. index:: Plugins; UZSU
.. index:: UZSU

UZSU
####

Konfiguration
=============

In der etc/plugin.yaml muss das Plugin standardmäßig eingebunden werden. Falls remove_duplicates auf True gesetzt ist (default), werden Einträge mit exakt den selben Einstellungen, aber unterschiedlichem Wert durch einen neu getätigten Eintrag ersetzt. Da diese Funktionalität nur gewährleistet ist, wenn die Einträge abgesehen vom zu setzenden Wert identisch sind, werden vom Plugin nicht unterstützte Dictionary-Keys, die evtl. durch das UZSU Widget der SmartVISU hinzugefügt wurden, beim Pluginstart ab v1.5.3 gelöscht.

.. code-block:: yaml

    # etc/plugin.yaml
    uzsu:
        class_name: UZSU
        class_path: plugins.uzsu
        #remove_duplicates: True

Im items Ordner ist pro Item, das geschaltet werden soll, ein UZSU Item mit ``type: dict`` zu erstellen. Die Hierarchie spielt dabei keine Rolle, es wird allerdings empfohlen, das UZSU Item als Kind des zu schaltenden Items zu deklarieren und die relative Item-Referenzierung ``'..'`` für den Parameter ``uzsu_item`` zu nutzen. Es wird dringend empfohlen, das ``cache: True`` zu setzen, damit die Einstellungen bei einem Neustart nicht verloren gehen.

.. code-block:: yaml

    # items/my.yaml
    someroom:

        someitem:
            type: num

            UZSU:
                type: dict
                uzsu_item: someroom.someitem #Ab smarthomeNG 1.6 ist es möglich, einfach nur '..' zu nutzen, um auf das Parent-Item zu verweisen.
                cache: 'True'

                active: # Dieser Eintrag kann genutzt werden, um die UZSU durch einen einfachen Item Call zu (de)aktivieren.
                    type: bool
                    eval: sh...activate(value)
                    visu_acl: rw


Datenformat
===========

Jedes USZU Item wird als dict-Typ gespeichert. Jeder Listen-Eintrag ist wiederum ein dict, das aus Key und Value-Paaren besteht. Im Folgenden werden die möglichen Dictionary-Keys gelistet. Nutzt man das USZU Widget der SmartVISU, muss man sich um diese Einträge nicht kümmern.

-  **dtstart**: Ein datetime Objekt, das den exakten Startwert für den rrule Algorithmus besimmt. Dieser Parameter ist besonder bei FREQ=MINUTELY rrules relevant.

-  **value**: Der Wert, auf den das uzsu_item gesetzt werden soll.

-  **active**: ``True`` wenn die UZSU aktiviert ist, ``False`` wenn keine Aktualisierungen vorgenommen werden sollen. Dieser Wert kann über die Pluginfunktion activate gesteuert werden.

-  **time**: Zeit als String. Entweder eine direkte Zeitangabe wie ``17:00`` oder eine Kombination mit Sonnenauf- und Untergang wie bei einem crontab, z.B. ``17:00<sunset``, ``sunrise>8:00``, ``17:00<sunset``.

-  **rrule**: Hier können Wiederholungsregeln wie in `rrule <https://dateutil.readthedocs.io/en/stable/rrule.html>`_ beschrieben festgelegt werden.


Interpolation
=============

.. important::

      Wenn die Interpolation aktiviert ist, wird das UZUS Item im gegebenen Intervall aktualisiert, auch wenn der nächste UZSU Eintrag über die Tagesgrenze hinaus geht. Gibt es beispielsweise heute um 23:00 einen Eintrag mit dem Wert 100 und morgen um 1:00 einen Eintrag mit dem Wert 0, wird zwischen den beiden Zeitpunkten der Wert kontinuierlich abnehmen. Bei linearer Interpolation wird um Mitternacht der Wert 50 geschrieben.

Interpolation ist ein eigenes Dict innerhalb des UZSU Dictionary mit folgenden Einträgen:

-  **type**: string, setzt die mathematische Interpolationsfunktion cubic, linear oder none. Ist der Wert cubic oder linear gesetzt, wird der für die aktuelle Zeit interpolierte Wert sowohl beim Pluginstart als auch im entsprechenden Intervall gesetzt.

-  **interval**: integer, setzt den zeitlichen Abstand (in Sekunden) der automatischen UZSU Auslösungen

-  **initage**: integer, definiert die Anzahl Sekunden, innerhalb der beim Pluginstart etwaige versäumte UZSU Einträge gesucht werden sollen. Diese Einstellung ist obsolet, wenn die Interpolation nicht auf none ist, weil dann beim Pluginstart der errechnete Wert automatisch gesetzt wird.

-  **itemtype**: Der Item-Typ des uzsu_item, das durch die UZSU gesetzt werden soll. Dieser Wert wird beim Pluginstart automatisch ermittelt und sollte nicht verändert werden.

-  **initizialized**: bool, wird beim Pluginstart automatisch gesetzt, sobald ein gültiger Eintrag innerhalb der initage Zeit gefunden wurde und diese Initialisierung tatsächlich ausgeführt wurde.


Funktionen
==========

UZSU Items können über folgende Funktion z.B. in Logiken oder eval-Aufrufen abgefragt oder verändert werden.

.. code-block:: python

    # Abfrage des nächsten Aktualisierungszeitpunkts
    sh.eg.wohnen.kugellampe.uzsu.planned()

    # Abfrage, ob die uzsu aktiv ist oder nicht.
    sh.eg.wohnen.kugellampe.uzsu.activate()

    # Setzen, ob die uzsu aktiv ist oder nicht. True: aktivieren, False: deaktivieren
    sh.eg.wohnen.kugellampe.uzsu.activate(True/False)

    # Abfrage der Interpolationseinstellungen
    sh.eg.wohnen.kugellampe.uzsu.interpolation()

    # Setzen der Interpolationseinstellungen
    sh.eg.wohnen.kugellampe.uzsu.interpolation(type='linear/none/cubic', interval=5, backintime=0)

    # Beim Aufrufen mit dem Parameter True werden die Einträge der UZSU gelöscht. VORSICHT!
    sh.eg.wohnen.kugellampe.uzsu.clear(True)


Webinterface
============

Das Webinterface bietet folgende Informationen:

-  **UZSUs**: Liste aller UZSU Items mit farbkodierter Information über den Status (inaktiv, aktiv, Problem)

-  **UZSU Items**: Info zu den Items, die über die UZSU geschaltet werden (inkl. Typ)

-  **UZSU Item Werte**: Aktueller Wert des UZSU Items, geplanter nächster Wert und Zeitpunkt der Schaltung

-  **UZSU Interpolation**: Interpolationstyp und Intervall

-  **UZSU Init**: Back in Time bz.w init age Wert

-  **UZSU dict**: Durch Klicken auf eine Zeile wird das gesamte Dictionary einer UZSU angezeigt.

.. image:: uzsu_webif.png
   :height: 1632px
   :width: 3286px
   :scale: 25%
   :alt: Web Interface
   :align: center


Beispiel
========

Folgender Python Aufruf bzw. Dictionary Eintrag schaltet das Licht jeden zweiten Tag um 16:30 auf den Wert 100% und deaktiviert es um 17:30 Uhr. Dazwischen wird im Abstand von 5 Minuten der Wert linear interpoliert. Um 17:00 Uhr ist er somit bei 50%.

.. code:: python

   sh.eg.wohnen.leuchte.uzsu({'active':True, 'list':[
   {'value':100, 'active':True, 'rrule':'FREQ=DAILY;INTERVAL=2', 'time': '16:30'},
   {'value':0, 'active':True, 'rrule':'FREQ=DAILY;INTERVAL=2', 'time': '17:30'}],
   {'interval': 5, 'type': 'cubic', 'initialized': False, 'itemtype': 'num', 'initage': 0}
   })


Weitere Infos
=============

Beispiele und zusätzliche Infos können im `SmarthomeNG Blog <https://www.smarthomeng.de/tag/uzsu>`_ gefunden werden.


SmartVISU
=========

Das UZSU plugin wird durch die smartVISU2.9 sowohl in Form eines Popups als auch einer grafischen Darstellung unterstützt.
